#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)
[ -z "$FILE" ] && exit 0

case "$FILE" in
  *dm-slots/*.md|*modules/*/rules.md|*modules/*/module.json)
    ;;
  *)
    exit 0
    ;;
esac

[ -f "$FILE" ] || exit 0

if grep -Pq '[а-яА-ЯёЁ]' "$FILE" 2>/dev/null; then
  echo "LANGUAGE POLICY VIOLATION: $FILE contains Cyrillic text"
  echo "All rules files must be written entirely in English."
  grep -Pn '[а-яА-ЯёЁ]' "$FILE" | head -5
  exit 1
fi
