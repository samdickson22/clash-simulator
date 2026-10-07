import gzip
import json
from pathlib import Path
import tempfile
import unittest
from fractions import Fraction
from common import write,append,sha

class ConverterTest(unittest.TestCase):
    def test_real_pts_and_event_roundtrip(self):
        import av
        import numpy as np
        from convert_v3 import convert,convert_corpus
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';source.mkdir()
            v=av.open(str(source/'video.mp4'),'w');s=v.add_stream('libx264',rate=20);s.width=540;s.height=1140;s.pix_fmt='yuv420p';s.options={'threads':'1'}
            s.time_base=Fraction(1,90000);s.codec_context.time_base=Fraction(1,90000)
            for i in range(21):
                f=av.VideoFrame.from_ndarray(np.zeros((1140,540,3),dtype=np.uint8),format='bgr24');f.pts=i*4500;f.time_base=Fraction(1,90000)
                for packet in s.encode(f):v.mux(packet)
                append(source/'frames.jsonl',dict(seq=i,produced_at=100+i*.05,produced_mono=10+i*.05,tick_lo=200+i,tick_hi=201+i))
            for packet in s.encode():v.mux(packet)
            v.close()
            with gzip.open(source/'evaluation-only.jsonl.gz','wt') as out:
                for i in range(21):out.write(json.dumps(dict(observed_at=10+i*.05,observation=dict(tick=200+i,players=[dict(owner=side,elixir=5,hand=[dict(handIndex=j,cardId=26000010) for j in range(4)],cycle=[dict(cardId=26000010)]) for side in (0,1)])))+'\n')
            append(source/'events.jsonl',dict(event_id='1',accepted=True,exec_tick=206,kind='troop',side=0,tile=[3.5,13.5],card='Skeletons',card_id=26000010))
            write(source/'receipt.json',dict(episode='test',seed=1,split='train',decks=[[],[]],files={p.name:sha(p) for p in source.iterdir()}))
            result=convert(source,Path(tmp)/'converted')
            import shutil
            second=Path(tmp)/'source2';shutil.copytree(source,second)
            r=json.loads((second/'receipt.json').read_text());r['episode']='test2';r['seed']=2;write(second/'receipt.json',r)
            corpus=convert_corpus([source,second],Path(tmp)/'corpus')
            self.assertEqual(corpus['matches'],2)
            self.assertEqual(len(json.loads((Path(tmp)/'corpus/manifest.json').read_text())['matches']),2)
            self.assertEqual(result['source_frames'],21);self.assertEqual(result['converted_frames'],11);self.assertEqual(result['events_roundtripped'],1)
if __name__=='__main__':unittest.main()
