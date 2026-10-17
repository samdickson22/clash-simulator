"""Read-only account and official-cost reconciliation; no account actions."""
import hashlib,json,pathlib,shutil,subprocess
ROOT=pathlib.Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2-levelgain-20261017')
OLD=pathlib.Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
SOURCE=pathlib.Path('/mpac/sdicks02/repos/clasher-live/reports/live/loop')
DECK=['Valkyrie','Archers','Bats','Cannon','Fireball','Zap','MiniPekka','Giant']
COMMON={'Archers','Bats','Cannon','Zap'}
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def main():
 collection=json.loads((SOURCE/'collection.json').read_text())
 table=json.loads((OLD/'official-upgrade-table.json').read_text())
 account=collection['_account'];assert account['gold']==28468 and account['gems']==410
 wild=account['wild_cards'];assert wild['common']==24 and wild['rare']==4
 rows=[]
 for card in DECK:
  c=collection[card];rarity='Common' if card in COMMON else 'Rare';t=table[rarity]
  index=c['level']-t['relativeLevel']-1
  needed=t['upgradeMaterialCount'][index];gold=t['upgradeCost'][index]
  assert needed==c['needed'],(card,needed,c)
  shortage=max(0,needed-c['copies']-wild[rarity.lower()])
  rows.append(dict(card=card,from_level=c['level'],to_level=c['level']+1,rarity=rarity,
   held_copies=c['copies'],needed=needed,wild_available=wild[rarity.lower()],
   extra_copies_needed=shortage,gold=gold,affordable=shortage==0 and gold<=account['gold']))
 assert not any(r['affordable'] for r in rows)
 for name in ('collection.json','ACCOUNT-LOG.md'):
  shutil.copyfile(SOURCE/name,ROOT/('input-'+name))
 result=dict(utc=utc(),gold=account['gold'],gems=account['gems'],wild_cards=wild,
  king_level=account['king_tower_level'],collection_source=str(SOURCE/'collection.json'),
  collection_sha256=sha(ROOT/'input-collection.json'),account_log_sha256=sha(ROOT/'input-ACCOUNT-LOG.md'),
  official_table_sha256=sha(OLD/'official-upgrade-table.json'),gamedata_sha256=sha(OLD/'upgrade-source-gamedata.json'),
  affordable=False,rows=rows,gold_spent=0,wild_cards_spent=0,gems_spent=0)
 (ROOT/'affordability.json').write_text(json.dumps(result,indent=2)+'\n')
 lines=['# Current deck upgrade affordability',f'Checked {result["utc"]}. No deck-card upgrade is affordable now. Gold is sufficient; card copies are the constraint.',
  'Inventory: 28,468 gold, 410 gems (not spent), 24 common / 4 rare wild cards. No spending or account action was performed.',
  '|Card|Next level|Held / needed|Wild cards available|Extra copies still needed|Gold cost|',
  '|---|---|---:|---:|---:|---:|']
 for r in rows:lines.append(f'|{r["card"]}|{r["from_level"]}→{r["to_level"]}|{r["held_copies"]}/{r["needed"]}|{r["wild_available"]} {r["rarity"]}|{r["extra_copies_needed"]}|{r["gold"]}|')
 lines += ['', 'Shortfalls apply independently, using all wild cards of that rarity for the listed card. The same wild cards cannot fund several rows at once.',
  'Closest rare targets: Valkyrie or Fireball need 16 additional rare copies. Closest common target: Bats needs 62 additional common copies; Cannon and Zap each need 76. Giant and MiniPekka need 46 rare copies each; Archers needs 257 common copies. These are copy distances, not a simulation ranking.',
  'Keep the wild cards until a chosen deck upgrade can be completed. Arrows is outside the deck and excluded. No gem purchase is included.',
  f'Sources: live collection plus read-only ACCOUNT-LOG, including the completed MiniPekka/Cannon upgrades and later free Cannon copies; official live16402c rarity-aware upgrade table, gamedata SHA `{result["gamedata_sha256"]}`.']
 (ROOT/'UPGRADES.md').write_text('\n\n'.join(lines[:3])+'\n\n'+'\n'.join(lines[3:])+'\n')
 print(json.dumps(result))
if __name__=='__main__':main()
