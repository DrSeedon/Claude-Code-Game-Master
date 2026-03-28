#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Find project root
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common-module.sh"
PROJECT_DIR="$(find_project_root "$SCRIPT_DIR")"
RULES_DIR="$PROJECT_DIR/.claude/additional/campaign-custom-rules"

ACTION="${1:-list}"

_list() {
    local campaign_dir applied_ids=""
    campaign_dir=$(bash "$PROJECT_DIR/tools/dm-campaign.sh" path 2>/dev/null || true)
    if [[ -n "$campaign_dir" && -f "$campaign_dir/campaign-overview.json" ]]; then
        applied_ids=$(uv run python -c "
import sys, json
try:
    with open(sys.argv[1]) as f:
        d = json.load(f)
    ids = d.get('custom_rules_applied', [])
    print(' '.join(ids))
except: pass
" "$campaign_dir/campaign-overview.json" 2>/dev/null || true)
    fi

    echo ""
    local i=1
    for f in "$RULES_DIR"/*.md; do
        [[ -f "$f" ]] || continue
        local id name description genres recommended
        id=$(grep -m1 "^## id" "$f" -A1 | tail -1 | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        name=$(grep -m1 "^## name" "$f" -A1 | tail -1 | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        description=$(grep -m1 "^## description" "$f" -A1 | tail -1 | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        genres=$(grep -m1 "^## genres" "$f" -A1 | tail -1 | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        recommended=$(grep -m1 "^## recommended_for" "$f" -A1 | tail -1 | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')

        local marker="  "
        if echo " $applied_ids " | grep -q " $id "; then
            marker="* "
        fi

        echo "  [$i] ${marker}${id}"
        echo "      ${name}"
        echo "      ${description}"
        echo "      Genres: ${genres}"
        echo "      Best for: ${recommended}"
        echo ""
        i=$((i+1))
    done
}

_show() {
    local target="${2:-}"
    if [[ -z "$target" ]]; then
        echo "[ERROR] Usage: dm-campaign-custom-rules.sh show <id>" >&2
        return 1
    fi
    for f in "$RULES_DIR"/*.md; do
        [[ -f "$f" ]] || continue
        local id
        id=$(grep -m1 "^## id" "$f" -A1 | tail -1 | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [[ "$id" == "$target" ]]; then
            cat "$f"
            return 0
        fi
    done
    echo "[ERROR] Rule not found: $target" >&2
    return 1
}

_recommend() {
    local genre="${2:-}"
    case "$genre" in
        *survival*|*stalker*|*fallout*|*metro*|*post-apocalyptic*|*zone*|*zomboid*|*zombie*|*apocalypse*)
            echo "realistic-progression russian-language" ;;
        *horror*|*gritty*|*realistic*|*dark*)
            echo "realistic-progression" ;;
        *russian*|*ru|*cyrillic*)
            echo "russian-language" ;;
        *)
            echo "" ;;
    esac
}

_apply() {
    local target="${2:-}"
    if [[ -z "$target" ]]; then
        echo "[ERROR] Usage: dm-campaign-custom-rules.sh apply <id>" >&2
        return 1
    fi

    local campaign_dir
    campaign_dir=$(bash "$PROJECT_DIR/tools/dm-campaign.sh" path 2>/dev/null)

    if [[ -z "$campaign_dir" ]]; then
        echo "[ERROR] No active campaign" >&2
        return 1
    fi

    for f in "$RULES_DIR"/*.md; do
        [[ -f "$f" ]] || continue
        local id
        id=$(grep -m1 "^## id" "$f" -A1 | tail -1 | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [[ "$id" == "$target" ]]; then
            uv run python - "$f" "$campaign_dir/campaign-overview.json" "$campaign_dir/campaign-rules.md" << 'PYEOF'
import sys, json, re, os

rule_file = sys.argv[1]
overview_file = sys.argv[2]
rules_output_file = sys.argv[3]

with open(rule_file) as f:
    content = f.read()

def extract(key):
    m = re.search(r'^## ' + key + r'\s*\n(.+?)(?=\n## |\Z)', content, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else ''

rule_id = extract('id')
name = extract('name')
rules_block = extract('rules')

# Update campaign-overview.json
with open(overview_file) as f:
    data = json.load(f)

applied = data.get('custom_rules_applied', [])
if rule_id in applied:
    print(f'[SKIP] Rule already applied: {rule_id}')
    sys.exit(0)

applied.append(rule_id)
data['custom_rules_applied'] = applied

with open(overview_file, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# Append to campaign-rules.md
begin_marker = f'<!-- BEGIN CUSTOM RULE: {rule_id} -->'
end_marker = f'<!-- END CUSTOM RULE: {rule_id} -->'

block = f'\n{begin_marker}\n## {name}\n\n{rules_block}\n{end_marker}\n'

if os.path.exists(rules_output_file):
    with open(rules_output_file, 'a') as f:
        f.write(block)
else:
    with open(rules_output_file, 'w') as f:
        f.write(f'# Campaign Rules\n{block}')

print(f'[SUCCESS] Custom rule applied: {rule_id}')
PYEOF
            return 0
        fi
    done
    echo "[ERROR] Rule not found: $target" >&2
    return 1
}

_remove() {
    local target="${2:-}"
    if [[ -z "$target" ]]; then
        echo "[ERROR] Usage: dm-campaign-custom-rules.sh remove <id>" >&2
        return 1
    fi

    local campaign_dir
    campaign_dir=$(bash "$PROJECT_DIR/tools/dm-campaign.sh" path 2>/dev/null)

    if [[ -z "$campaign_dir" ]]; then
        echo "[ERROR] No active campaign" >&2
        return 1
    fi

    uv run python - "$target" "$campaign_dir/campaign-overview.json" "$campaign_dir/campaign-rules.md" << 'PYEOF'
import sys, json, re, os

rule_id = sys.argv[1]
overview_file = sys.argv[2]
rules_output_file = sys.argv[3]

# Update campaign-overview.json
with open(overview_file) as f:
    data = json.load(f)

applied = data.get('custom_rules_applied', [])
if rule_id not in applied:
    print(f'[SKIP] Rule not applied: {rule_id}')
    sys.exit(0)

applied.remove(rule_id)
data['custom_rules_applied'] = applied

with open(overview_file, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# Strip from campaign-rules.md
if not os.path.exists(rules_output_file):
    print(f'[SUCCESS] Rule removed from overview: {rule_id} (no campaign-rules.md to update)')
    sys.exit(0)

with open(rules_output_file) as f:
    text = f.read()

begin_marker = f'<!-- BEGIN CUSTOM RULE: {rule_id} -->'
end_marker = f'<!-- END CUSTOM RULE: {rule_id} -->'

pattern = re.compile(
    r'\n?' + re.escape(begin_marker) + r'.*?' + re.escape(end_marker) + r'\n?',
    re.DOTALL
)

new_text, count = pattern.subn('', text)

if count == 0:
    print(f'[WARN] Marker not found in campaign-rules.md — overview updated, file unchanged.')
else:
    with open(rules_output_file, 'w') as f:
        f.write(new_text)
    print(f'[SUCCESS] Custom rule removed: {rule_id}')
PYEOF
}

case "$ACTION" in
    list)      _list ;;
    show)      _show "$@" ;;
    apply)     _apply "$@" ;;
    remove)    _remove "$@" ;;
    recommend) _recommend "$@" ;;
    *)
        echo "Usage: dm-campaign-custom-rules.sh <list|show <id>|apply <id>|remove <id>|recommend <genre>>"
        exit 1
        ;;
esac
