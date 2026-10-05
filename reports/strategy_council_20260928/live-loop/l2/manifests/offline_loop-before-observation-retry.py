"""L2 orchestrator. Truth is restricted to opponent/evaluation and never player calls."""
import argparse,json,os,sys,time,threading,subprocess,hashlib,traceback,gzip
from dataclasses import asdict,replace
from pathlib import Path
from types import SimpleNamespace
from bootstrap import setup,HERE,ROOT,COUNCIL

def append(path,row):
    with (gzip.open(path,'at') if path.suffix=='.gz' else path.open('a')) as f:f.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')
def progress(message):
    append(HERE/'events.jsonl',dict(time=time.time(),pid=os.getpid(),message=message))
    with (HERE/'PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S")}: {message}\n')
    print(message,flush=True)
def write(path,row):
    p=path.with_suffix(path.suffix+'.tmp');p.write_text(json.dumps(row,indent=2)+'\n');p.replace(path)
def storage_guard():
    size=sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
    if size>900*1024**2:raise RuntimeError('L2 storage stop at 900 MiB, preserving partial evidence')

def pixel_result(frame):
    """Provisional result from visible crown survivors, never native labels."""
    kings={s:sum(e.card=='KingTower' and e.player_id==s for e in frame.entities) for s in (0,1)}
    towers={s:sum(e.card=='Tower' and e.player_id==s for e in frame.entities) for s in (0,1)}
    if kings[0]==0 and kings[1]>0:return dict(winner=1,reason='enemy King absent',certified=False)
    if kings[1]==0 and kings[0]>0:return dict(winner=0,reason='own King absent',certified=False)
    if towers[0]!=towers[1]:return dict(winner=int(towers[1]>towers[0]),reason='visible surviving Princess count',certified=False)
    return dict(winner='unknown',reason='no certified pixel result glyph or HP tiebreak reader',certified=False)

def native_frame(obs,loader,names,seat):
    """Opponent control only. This function is forbidden in the pixel player."""
    from clasher.rl.live_inference_contract import PublicVisionFrame,VisionEntity
    player=next(p for p in obs['players'] if p['owner']==seat)
    hand=['']*4
    for c in player['hand']:hand[c['handIndex']]=names[c['cardId']]
    next_card=names[player['cycle'][0]['cardId']] if player['cycle'] else None
    entities=[]
    for o in obs['objects']:
        if o['hp'] is None or o['hp']<=0:continue
        if o['cardId']==-1:card='KingTower' if abs(o['x']-9000)<1000 else 'Tower';kind='building'
        else:
            action=names.get(o['cardId'])
            if action is None:continue
            stats=loader.get_card(action);raw=stats._raw_entry
            card=(raw.get('summonCharacterData') or {}).get('name',stats.name)
            kind='building' if str(stats.card_type).lower()=='building' else 'troop'
        entities.append(VisionEntity(str(o['nativeObjectId']),card,kind,o['owner'],max(0,min(18,o['x']/1000)),max(0,min(32,o['y']/1000)),1.,o['hp']/o['maxHp'],1.))
    tick=obs['tick'];clock=max(0,(3600-tick)/20) if tick<3600 else max(0,(6000-tick)/20)
    return PublicVisionFrame('opponent',str(tick),tick*50,clock,1.,player['elixir'],1.,tuple(hand),tuple(float(bool(c)) for c in hand),next_card,1.,tuple(entities),())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['c56','p16'],default='c56');ap.add_argument('--smoke',action='store_true');ap.add_argument('--limit',type=int);a=ap.parse_args()
    r,_=setup(a.mode)
    import cv2,numpy as np,torch
    from pixel_player import PixelSensor,PixelPlayer,PacketBuilder,model_hypothesis
    from clasher.vision.l1_stream import GrpcScreenStream
    from clasher.vision.l1_perception import serialize_frame,elixir_feature
    from collect_l1_rendered import ADB,BASE
    from smoke_reference_battle import request
    from certify_l1_timing_v3 import verify_owner
    from l1_native_capture_v3 import consistent_observation
    cv2.setNumThreads(1)
    owner=json.loads((HERE/'emulator/complete.json').read_text());verify_owner(owner)
    def call(command):
        for attempt in range(3):
            try:return request(owner['probe_port'],command)
            except (ConnectionRefusedError, ConnectionResetError, json.JSONDecodeError) as error:
                # Never blindly repeat a mutation after losing its response.
                readonly=command in ('status','observe','attest') or command.startswith('replay-schedule-status ')
                if attempt==2 or (not readonly and not isinstance(error,ConnectionRefusedError)):raise
                append(HERE/'forward-reconnections.jsonl',dict(time=time.time(),command=command.split()[0],attempt=attempt,error=repr(error)))
                mapping=subprocess.run([str(ADB),'forward','--list'],check=True,capture_output=True,text=True,timeout=10,close_fds=False).stdout
                entries=[line.split() for line in mapping.splitlines() if len(line.split())==3 and line.split()[1]==f"tcp:{owner['probe_port']}"]
                expected=[owner['serial'],f"tcp:{owner['probe_port']}",'tcp:26789']
                if entries and entries!=[expected]:raise RuntimeError('Probe port ownership changed; refuse to replace another mapping')
                if not entries:
                    subprocess.run([str(ADB),'-s',owner['serial'],'forward','--no-rebind',f"tcp:{owner['probe_port']}",'tcp:26789'],
                        check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=10,close_fds=False)
                time.sleep(.15)

    b=r.builder if a.mode=='c56' else r.loaded.builder
    loader=b.loader
    if a.mode=='p16':
        from clasher.rl.contract_v5 import ContractV5ObservationBuilder
        from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
        opponent_builder=ContractV5ObservationBuilder(card_loader=loader)
        bots={s:PublicScriptedOpponent(opponent_builder,style=s,card_scope='c56') for s in ('balanced','pressure','defense')}
    else:opponent_builder=b;bots=r.bots
    from clasher.rl.c56_scripted import C56_ADDED_CARDS
    from clasher.rl.native_public_observation import PUBLIC_REFERENCE_CARDS
    names={loader.get_card(c)._raw_entry['id']:c for c in set(PUBLIC_REFERENCE_CARDS)|C56_ADDED_CARDS}
    ids={n:i for i,n in names.items()}
    sensor=PixelSensor()
    from clasher.vision.l1 import public_pixels
    warm=public_pixels(cv2.imread(str(HERE/'preflight.png')))
    for k in range(2):sensor.read(warm,'excluded-warmup',k,100+k*100)
    matches=json.loads((HERE/'schedule.json').read_text())['matches']
    matches=[x for x in matches if x['mode']==a.mode]
    if a.smoke:
        matches=[dict(matches[0],pair=-1,seed=1967040401)]
    else:
        assert (HERE/'PREREG.md').exists() and (HERE/'manifest.json').exists()
    matches=matches[:a.limit]
    receipts=HERE/('smoke-'+a.mode+'-'+time.strftime('%H%M%S') if a.smoke else 'native');receipts.mkdir(exist_ok=True)
    for ep in matches:
        target=receipts/f"pair-{ep['pair']:02d}.json"
        if target.exists():continue
        storage_guard();verify_owner(owner)
        folder=receipts/f"pair-{ep['pair']:02d}"
        folder.mkdir(exist_ok=False)
        p16=None
        if a.mode=='p16':
            from tuning import Planner,Config
            prior=dict(decks=sum([json.loads(p.read_text())['decks'] for p in [COUNCIL/'m0/data/roles_v2/training.json',COUNCIL/'m0/data/roles_v2/development.json',COUNCIL/'pilot/hog26-deployment.json']],[]))
            p16=Planner(r,prior,Config('mixture',opponent='mixture'),seed=ep['seed']+31)
        player=PixelPlayer(r,a.mode,ep['seed']+31,p16_planner=p16)
        opackets=PacketBuilder(opponent_builder)
        config=json.loads(BASE.read_text())['config'];config.update(rndSeed=ep['seed'],endTick=7200)
        for side in (0,1):config['battle'][f'deck{side}']['sp']=[{'d':ids[n]} for n in ep['decks'][side]]
        seq=call('configure-native '+json.dumps(config,separators=(',',':')))['sequence']
        limit=time.perf_counter()+45
        while time.perf_counter()<limit:
            status=call('status')
            if status['nativeRenderLoaded']==seq and status['nativeRenderReady']:break
            time.sleep(.1)
        else:raise TimeoutError('renderer setup')
        tick=call('pause')['tick'];call('speed 1');call('render on')
        if tick<220:call(f'advance-native {220-tick}')
        initial=call('observe')
        prior_setup=HERE/'recovery-forward'/f"native-pair-{ep['pair']:02d}-partial"/'setup-evaluation-only.json'
        if prior_setup.exists():
            old_setup=json.loads(prior_setup.read_text())['initial']
            def opening(state):
                return [(p['owner'],[(c['handIndex'],c['cardId']) for c in p['hand']],
                    [c['cardId'] for c in p['cycle']],p['elixir']) for p in state['players']]
            if initial['tick']!=old_setup['tick'] or opening(initial)!=opening(old_setup):
                write(folder/'opening-mismatch.json',dict(old=opening(old_setup),new=opening(initial)))
                raise RuntimeError('Technical replay opening differs; do not reuse clean baseline')
            write(folder/'opening-replay-check.json',dict(equal=True,source=str(prior_setup),tick=initial['tick']))
        write(folder/'setup-evaluation-only.json',dict(config=config,initial=initial))
        stop=threading.Event();operror=[];truth=[];opactions=[];pending=[]
        def opponent():
            next_turn=0.;next_play=0.
            try:
                while not stop.is_set():
                    now=time.perf_counter()
                    if now<next_turn:stop.wait(min(.05,next_turn-now));continue
                    next_turn=now+.1
                    obs,fence=consistent_observation(call)
                    truth.append(obs)
                    append(folder/'evaluation-only.jsonl.gz',dict(time=time.perf_counter(),observation=obs,fence=fence))
                    for item in list(pending):
                        receipt=call(f"replay-schedule-status {item['sequence']}")
                        if receipt['state'] not in ('pending','queued'):
                            append(folder/'opponent-actions.jsonl',dict(item,receipt=receipt));pending.remove(item)
                    if obs['ended'] or now<next_play:continue
                    next_play=now+.5
                    frame=native_frame(obs,loader,names,0)
                    packet,_=opackets.build(frame,obs['tick'],seat=0)
                    packet=model_hypothesis(packet)
                    action=int(bots[ep['style']].select_action(packet))
                    if action>=2304:continue
                    card=frame.own_hand[action//576];tile=action%576;x=tile%18+.5;y=tile//18+.5
                    at=call('status')['tick']+8
                    try:receipt=call(f'replay-schedule-card 0 {ids[card]} {round(x*1000)} {round(y*1000)} {at}')
                    except ValueError as error:
                        append(folder/'opponent-rejections.jsonl',dict(action=action,card=card,error=str(error)));continue
                    item=dict(action=action,card=card,tick=at,sequence=receipt['sequence']);pending.append(item);opactions.append(item)
            except BaseException as e:operror.append(traceback.format_exc())
        discovery=Path.home()/f"Library/Caches/TemporaryItems/avd/running/pid_{owner['pid']}.ini"
        decisions=[];actions=[];last=0;index=0;next_decision=0.;missing_since=None;pixel_end=False
        begin=time.perf_counter();wall_origin=time.time();worker=threading.Thread(target=opponent,daemon=True)
        try:
            with GrpcScreenStream(owner['grpc_port'],HERE.parent/'l1/v1/grpc',discovery) as stream:
                last=stream.read().sequence
                call('resume');begin=time.perf_counter();wall_origin=time.time();worker.start()
                while time.perf_counter()-begin<(35 if a.smoke else 400):
                    if operror:raise RuntimeError(operror[0])
                    capture=stream.read(after_sequence=last,timeout=10);last=capture.sequence
                    timestamp=max(index+1,round((capture.decoded_at-begin)*1000));index+=1
                    public,cues=sensor.read(capture.pixels,f"l2-{ep['seed']}",index,timestamp)
                    append(folder/'public-frames.jsonl.gz',serialize_frame(public))
                    if player.started and public.visible_clock_seconds is None and elixir_feature(capture.pixels)<.005:
                        if missing_since is None:missing_since=time.perf_counter()
                        if time.perf_counter()-missing_since>.7:pixel_end=True;cv2.imwrite(str(folder/'terminal.jpg'),capture.pixels);break
                    else:missing_since=None
                    if public.visible_clock_seconds is None and not player.started:continue
                    public_tick=player.ingest(public,cues)
                    if time.perf_counter()<next_decision:continue
                    next_decision=time.perf_counter()+.5
                    action,diag=player.decide(public,public_tick)
                    action_start=time.perf_counter();before_wall=time.time()
                    row=dict(frame_id=public.frame_id,sequence=last,capture_produced_epoch=capture.produced_at,capture_received_mono=capture.decoded_at,
                        perceived_tick=public_tick,action=action,diag=diag,chosen_card=public.own_hand[action//576] if action<2304 else None)
                    if action<2304:
                        tile=action%576;x=18-(tile%18+.5);y=32-(tile//18+.5);slot=action//576
                        # Installed touch hook deliberately retains 1080x1920 input coordinates.
                        hand=[211,354,497,640][slot]
                        commands=[[str(ADB),'-s',owner['serial'],'shell','input','tap',str(hand),'1749'],
                            [str(ADB),'-s',owner['serial'],'shell','input','tap',str(round(111+x/18*856)),str(round(436+y/32*1230))]]
                        for cmd in commands:subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=5,close_fds=False)
                        row.update(tile=[x,y],slot=slot)
                    end=time.perf_counter();row.update(action_submit_mono=end,action_submit_epoch=time.time(),tap_ms=(end-action_start)*1000,
                        receive_to_action_ms=(end-capture.decoded_at)*1000,production_to_action_ms=(time.time()-capture.produced_at)*1000 if capture.produced_at is not None else None)
                    decisions.append(row);append(folder/'decisions.jsonl',row)
                    if action<2304:
                        actions.append(row)
                        if len(actions)<=3:cv2.imwrite(str(folder/f'action-{len(actions)}.jpg'),capture.pixels)
                    if index%100==0:storage_guard()
                else:cv2.imwrite(str(folder/'timeout.jpg'),capture.pixels)
        finally:
            stop.set()
            if worker.is_alive():worker.join(timeout=8)
            call('pause')
        visual_result=pixel_result(public)
        final=call('observe');write(folder/'terminal-evaluation-only.json',final)
        call('render off')
        if operror:raise RuntimeError(operror[0])
        if not a.smoke and not final['ended']:raise RuntimeError('Pixel lifecycle stopped before native terminal; incomplete game retained')
        record=dict(**ep,pixel_result=visual_result,pixel_end_detected=pixel_end,terminal=final['ended'],winner=final['winner'],native_tick=final['tick'],
            seconds=time.perf_counter()-begin,frames=index,decisions=len(decisions),actions=len(actions),opponent_actions=len(opactions),action_path='adb legacy-hook coordinates',
            score=.5 if final['winner'] is None else float(final['winner']==1),win=int(final['winner']==1),smoke=a.smoke,
            source_manifest=hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest() if (HERE/'manifest.json').exists() else None)
        write(target,record)
        progress(f"{'Smoke' if a.smoke else 'Native'} pair {ep['pair']} complete: frames={index}, actions={len(actions)}, terminal={final['ended']}, pixel_end={pixel_end}. No interim aggregate strength inspection.")
    progress(f"Native {a.mode} worker finished.")
if __name__=='__main__':
    try:main()
    except BaseException:
        progress('Worker exception; preserve all partial evidence. '+traceback.format_exc())
        raise
