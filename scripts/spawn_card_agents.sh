#!/usr/bin/env bash
set -euo pipefail

# Configuration (override via env vars if desired)
MAX_TURNS="${MAX_TURNS:-40}"
WORKDIR="${WORKDIR:-/Users/sam/Desktop/code/clasher}"
TITLE_PREFIX="${TITLE_PREFIX:-CR Audit}" 
CARD_FILTER="${CARD_FILTER:-}"
SLEEP_BETWEEN="${SLEEP_BETWEEN:-0}"

# CLI args
TEST_MODE=0
for arg in "$@"; do
  case "$arg" in
    --test)
      TEST_MODE=1
      ;;
    -h|--help)
      cat <<USAGE
Usage: $(basename "$0") [--test]

Options:
  --test           Run a quick smoke test on a small card subset

Environment variables:
  MAX_TURNS        Max turns per session (default: $MAX_TURNS)
  WORKDIR          Working directory (default: $WORKDIR)
  TITLE_PREFIX     Session title prefix (default: "$TITLE_PREFIX")
  CARD_FILTER      Regex to include only matching card names
  SLEEP_BETWEEN    Seconds to sleep between launches (default: $SLEEP_BETWEEN)
USAGE
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

# Verify CLI is available
if ! command -v humanlayer-nightly >/dev/null 2>&1; then
  echo "error: humanlayer-nightly CLI not found in PATH" >&2
  exit 1
fi

# Prepare output folders
mkdir -p "$WORKDIR/reports/cards" "$WORKDIR/reports/logs"

# Prompt template for each agent
BASE_PROMPT="$(cat <<'EOF'
You are an autonomous code agent working inside this repository.

Task: For the card "{{CARD}}" (Category: {{CATEGORY}}, Elixir: {{ELIXIR}}), audit implementation status by:
1) FIRST: Do a quick web search to understand the card's official mechanics and behaviors from Clash Royale wiki or official sources.
2) THEN: Carefully examine gamedata.json to understand what capabilities THIS SPECIFIC CARD actually has.
   - Only look for mechanics that are explicitly present in the card's data
   - Do NOT assume the card has common mechanics unless they appear in its gamedata entry
   - Examples of possible gimmicks: charge/dash, chain/beam, retarget, death spawn/effect, projectiles, aura, heal, reflect, pull, tether, shield, rage/slow, split, deployables, lifesteal, spawn-on-damage, spawn-on-death, tower-interactions, pathing rules, immunity rules, etc.
   - Ignore and exclude EVOLUTIONS (EVOS) entirely.
3) FINALLY: Cross-reference the codebase (focus: src/clasher/entities.py, spells.py, dynamic_spells.py, engine.py, arena.py, battle.py) to determine what is implemented.
4) Producing a concise Markdown report with these sections:
   - Card, Elixir, Category (and Rarity/Type if known)
   - Implemented (bullet list, cite file paths and class/function names)
   - Missing (bullet list with the source of truth from gamedata.json - ONLY list mechanics that the card actually has according to gamedata)
   - Notes (ambiguities, name mapping, assumptions)

Output: Write the report to "reports/cards/{{SAFE_CARD}}.md" in this repository. Keep bullets short. Do not implement features; only audit and report. Do not discuss or include EVOS.
EOF
)"

# Helper to sanitize filenames (lowercase, alnum and hyphens only)
sanitize() {
  local s="$1"
  s="$(printf '%s' "$s" | tr '[:upper:]' '[:lower:]')"
  s="$(echo "$s" | sed 's/[^a-z0-9]/-/g; s/-\{2,\}/-/g; s/^-//; s/-$//')"
  printf '%s' "$s"
}

launch_for_card() {
  local name="$1" elixir="$2" category="$3"
  local safe
  safe="$(sanitize "$name")"

  local prompt
  prompt="${BASE_PROMPT//\{\{CARD\}\}/$name}"
  prompt="${prompt//\{\{ELIXIR\}\}/$elixir}"
  prompt="${prompt//\{\{CATEGORY\}\}/$category}"
  prompt="${prompt//\{\{SAFE_CARD\}\}/$safe}"

  local title
  title="$TITLE_PREFIX - $name"

  echo "Launching agent for: $name ($category, elixir: $elixir)" | tee -a "$WORKDIR/reports/logs/$safe.log"
  humanlayer-nightly launch \
    --title "$title" \
    --working-dir "$WORKDIR" \
    --max-turns "$MAX_TURNS" \
    --dangerously-skip-permissions \
    "$prompt" | tee -a "$WORKDIR/reports/logs/$safe.log"
}

# Card list: NAME|ELIXIR|CATEGORY
while IFS='|' read -r NAME ELIXIR CATEGORY; do
  # Skip empty/comment lines
  if [[ -z "${NAME// }" ]] || [[ "${NAME:0:1}" == "#" ]]; then
    continue
  fi
  # Optional filter by card name (regex match)
  if [[ -n "$CARD_FILTER" ]] && ! [[ "$NAME" =~ $CARD_FILTER ]]; then
    continue
  fi
  # Test mode: only run a small, representative subset
  if [[ "$TEST_MODE" -eq 1 ]]; then
    case "$NAME" in
      "Archers"|"Barbarian Barrel"|"Battle Ram") ;;
      *) continue ;;
    esac
  fi
  launch_for_card "$NAME" "${ELIXIR:-?}" "${CATEGORY:-Troop}"
  # Optional delay between launches
  if [[ "$SLEEP_BETWEEN" != "0" ]]; then
    sleep "$SLEEP_BETWEEN"
  fi
done <<'CARDS'
# Troops
Skeletons|1|Troop
Ice Spirit|1|Troop
Fire Spirit|1|Troop
Electro Spirit|1|Troop
Heal Spirit|1|Troop
Goblins|2|Troop
Bomber|2|Troop
Spear Goblins|2|Troop
Ice Golem|2|Troop
Bats|2|Troop
Wall Breakers|2|Troop
Suspicious Bush|2|Troop
Berserker|2|Troop
Knight|3|Troop
Archers|3|Troop
Minions|3|Troop
Skeleton Army|3|Troop
Ice Wizard|3|Troop
Guards|3|Troop
Princess|3|Troop
Miner|3|Troop
Mega Minion|3|Troop
Dart Goblin|3|Troop
Goblin Gang|3|Troop
Bandit|3|Troop
Royal Ghost|3|Troop
Skeleton Barrel|3|Troop
Fisherman|3|Troop
Firecracker|3|Troop
Elixir Golem|3|Troop
Little Prince|3|Troop
Goblin Machine|3|Troop
Valkyrie|4|Troop
Musketeer|4|Troop
Baby Dragon|4|Troop
Mini P.E.K.K.A|4|Troop
Hog Rider|4|Troop
Dark Prince|4|Troop
Lumberjack|4|Troop
Battle Ram|4|Troop
Inferno Dragon|4|Troop
Electro Wizard|4|Troop
Hunter|4|Troop
Night Witch|4|Troop
Zappies|4|Troop
Flying Machine|4|Troop
Magic Archer|4|Troop
Mighty Miner|4|Troop
Battle Healer|4|Troop
Skeleton King|4|Troop
Golden Knight|4|Troop
Skeleton Dragons|4|Troop
Mother Witch|4|Troop
Phoenix|4|Troop
Goblin Demolisher|4|Troop
Rune Giant|4|Troop
Giant|5|Troop
Balloon|5|Troop
Witch|5|Troop
Barbarians|5|Troop
Prince|5|Troop
Wizard|5|Troop
Minion Horde|5|Troop
Bowler|5|Troop
Executioner|5|Troop
Ram Rider|5|Troop
Rascals|5|Troop
Cannon Cart|5|Troop
Royal Hogs|5|Troop
Electro Dragon|5|Troop
Archer Queen|5|Troop
Monk|5|Troop
Goblinstein|5|Troop
Giant Skeleton|6|Troop
Royal Giant|6|Troop
Sparky|6|Troop
Elite Barbarians|6|Troop
Goblin Giant|6|Troop
Boss Bandit|6|Troop
Spirit Empress|6|Troop
P.E.K.K.A|7|Troop
Lava Hound|7|Troop
Royal Recruits|7|Troop
Mega Knight|7|Troop
Electro Giant|7|Troop
Golem|8|Troop
Three Musketeers|9|Troop

# Buildings
Cannon|3|Building
Tombstone|3|Building
Mortar|4|Building
Bomb Tower|4|Building
Tesla|4|Building
Furnace|4|Building
Goblin Cage|4|Building
Goblin Drill|4|Building
Goblin Hut|5|Building
Inferno Tower|5|Building
Elixir Collector|6|Building
X-Bow|6|Building
Barbarian Hut|7|Building

# Spells
Mirror|?|Spell
Rage|2|Spell
Zap|2|Spell
The Log|2|Spell
Barbarian Barrel|2|Spell
Giant Snowball|2|Spell
Goblin Curse|2|Spell
Arrows|3|Spell
Goblin Barrel|3|Spell
Tornado|3|Spell
Clone|3|Spell
Earthquake|3|Spell
Royal Delivery|3|Spell
Void|3|Spell
Vines|3|Spell
Fireball|4|Spell
Freeze|4|Spell
Poison|4|Spell
Graveyard|5|Spell
Rocket|6|Spell
Lightning|?|Spell
CARDS

echo "All agents launched. Logs: $WORKDIR/reports/logs" >&2


