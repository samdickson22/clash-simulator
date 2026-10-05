import copy,json
from study import OUT,PORT,TEMPLATE,request,dump
from pathlib import Path
from read_native_public_levels import read_levels
rows=[]
for val in [0,1,9,13]:
 c=copy.deepcopy(json.load(open(TEMPLATE))['config']);c['battle']['lvlcap']=0;c['battle']['cardlvlmin']=0
 for owner in [0,1]:
  for card in c['battle'][f'deck{owner}']['sp']:card['l']=val
 request(PORT,'configure '+json.dumps(c,separators=(',',':')))
 f=request(PORT,'observe');card=next(v for v in f['players'][0]['hand'] if v['cardId']==26000003)
 ack=request(PORT,f"replay-schedule-card 0 {card['cardId']} 3500 10500 100")
 request(PORT,'step 140');after=request(PORT,'observe')
 levels=read_levels(Path.home()/'.cache/clasher-native-reference/android-sdk/platform-tools/adb',port=PORT,serial='emulator-5584',batched=True,persistent=True)
 rows.append({'verified_levels':levels,'l':val,'hand':card,'objects':after['objects'],'receipt':request(PORT,f"replay-schedule-status {ack['sequence']}")})
dump('levels-verified.json',rows)
for r in rows:print(r['l'],[(o['cardId'],o['hp'],o['maxHp']) for o in r['objects'] if o['cardId']>0])
