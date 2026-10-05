import collections,csv,io,json
from pathlib import Path
from clasher.native_assets import decode_logic_asset
HERE=Path(__file__).resolve().parent
BASE=Path.home()/'.cache/clasher-native-reference/runtime-update-15.535.86/csv_logic'
files={'spells_characters.csv':26,'spells_buildings.csv':27,'spells_other.csv':28,'spells_evolved.csv':13,'spells_hero_form.csv':203}
mapping={}
for name,kind in files.items():
 path=BASE/name
 if not path.exists():path=Path.home()/'.cache/clasher-native-reference/base-assets-1e505767/assets/csv_logic'/name
 rows=list(csv.reader(io.StringIO(decode_logic_asset(path.read_bytes()).decode())))
 names=[r[0] for r in rows[2:] if r and r[0]]
 mapping.update({kind*1000000+i:n for i,n in enumerate(names)})
rs=[json.loads(l) for l in open(HERE/'results-terminal-50.jsonl')]
seen=sorted(set(i[0] for r in rs for i in r['observed_card_data_ids'] if i[0]>0))
forms=collections.Counter(str(i//1000000) for i in seen)
out={'observed_id_count':len(seen),'observed_by_id_class':dict(forms),'observed_names':{str(i):mapping.get(i,'unmapped-hero-or-dynamic') for i in seen},'note':'Native spell IDs are not body identity; rich dataGlobalId and content-qualified catalog still required. Hero IDs use the native hero-form table. This is an observation inventory, not a final token contract.'}
(HERE/'vocabulary-inventory.json').write_text(json.dumps(out,indent=2)+'\n');print(forms)
