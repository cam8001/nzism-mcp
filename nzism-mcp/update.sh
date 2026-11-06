#!/usr/bin/env bash
# Download the latest NZISM XML, rebuild the search index, and summarise what changed.
#
# Usage:
#   ./update.sh [--check] [--force] [FILE]
#
#   FILE     use this already-downloaded NZISM XML instead of fetching it
#   --check  report differences only; change nothing
#   --force  rebuild even if the XML is identical to data/nzism.xml
#
# The NZISM site sits behind bot protection (Incapsula) and often serves a
# JavaScript challenge page to curl. If the fetch fails, download the XML in a
# browser from the URL below and pass the saved file as FILE.
#
# Does NOT regenerate data/deeplinks.json (no scraper exists yet); it reports
# which paragraph IDs lack a deeplink so you know if that file is stale.
set -euo pipefail

XML_URL="https://nzism.gcsb.govt.nz/ism-document/xml"
cd "$(dirname "$0")"

CHECK=0
FORCE=0
SRC_FILE=""
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    --force) FORCE=1 ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) SRC_FILE="$arg" ;;
  esac
done

# Downloaded content is untrusted: keep it in its own empty temp dir.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir "$TMP/dl"

if [[ -n "$SRC_FILE" ]]; then
  [[ -f "$SRC_FILE" ]] || { echo "ERROR: $SRC_FILE not found" >&2; exit 1; }
  echo "Using local file $SRC_FILE ..."
  cp "$SRC_FILE" "$TMP/dl/nzism.xml"
else
  echo "Downloading $XML_URL ..."
  curl -fsSL --max-time 120 -o "$TMP/dl/nzism.xml" "$XML_URL" || {
    echo "ERROR: download failed. Fetch the XML in a browser and re-run: ./update.sh path/to/nzism.xml" >&2
    exit 1
  }
fi

if ! head -c 200 "$TMP/dl/nzism.xml" | grep -q '<?xml\|<xml'; then
  echo "ERROR: response is not XML (likely a bot-protection challenge page):" >&2
  head -c 200 "$TMP/dl/nzism.xml" >&2; echo >&2
  echo "Fetch the XML in a browser from $XML_URL and re-run: ./update.sh path/to/nzism.xml" >&2
  exit 1
fi

echo "Validating XML ..."
uv run python -I - "$TMP/dl/nzism.xml" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
n = len(root.findall(".//paragraph"))
if root.tag != "document" and not root.findall("chapter"):
    sys.exit(f"ERROR: unexpected root <{root.tag}> with no <chapter> children")
if n < 1000:
    sys.exit(f"ERROR: only {n} paragraphs found; download looks truncated or wrong")
print(f"  OK: {n} paragraphs")
PY

if [[ -f data/nzism.xml ]] && cmp -s data/nzism.xml "$TMP/dl/nzism.xml"; then
  echo "Downloaded XML is identical to data/nzism.xml."
  if [[ $FORCE -eq 0 ]]; then
    echo "Nothing to do (use --force to rebuild anyway)."
    exit 0
  fi
fi

# Snapshot the old index, then build the new one.
[[ -f data/nzism_index.json ]] && cp data/nzism_index.json "$TMP/old_index.json"

if [[ $CHECK -eq 1 ]]; then
  echo "--check: building into a scratch copy; repo files untouched."
  mkdir -p "$TMP/work/data"
  cp build_index.py "$TMP/work/"
  cp "$TMP/dl/nzism.xml" "$TMP/work/data/nzism.xml"
  [[ -f data/deeplinks.json ]] && cp data/deeplinks.json "$TMP/work/data/"
  (cd "$TMP/work" && uv run python build_index.py)
  NEW_INDEX="$TMP/work/data/nzism_index.json"
else
  cp "$TMP/dl/nzism.xml" data/nzism.xml
  uv run python build_index.py
  NEW_INDEX="data/nzism_index.json"
fi

echo
echo "=== Change summary ==="
uv run python -I - "$TMP/old_index.json" "$NEW_INDEX" <<'PY'
import json
import sys
from pathlib import Path

old_path, new_path = Path(sys.argv[1]), Path(sys.argv[2])
new = json.loads(new_path.read_text())
new_secs = {s["id"]: s["text"] for s in new["sections"]}
links = new["deeplinks"]

if old_path.exists():
    old = json.loads(old_path.read_text())
    old_secs = {s["id"]: s["text"] for s in old["sections"]}
    added = sorted(set(new_secs) - set(old_secs))
    removed = sorted(set(old_secs) - set(new_secs))
    changed = sorted(i for i in set(new_secs) & set(old_secs) if new_secs[i] != old_secs[i])
    print(f"Sections: {len(old_secs)} -> {len(new_secs)}")
    print(f"  added {len(added)}, removed {len(removed)}, text changed {len(changed)}")
    for label, ids in (("added", added), ("removed", removed), ("changed", changed)):
        if ids:
            print(f"  {label} (first 10): {', '.join(ids[:10])}")
else:
    print(f"Sections: {len(new_secs)} (no previous index to compare)")

# deeplinks.json only covers a subset of sections (baseline ~1400 of ~4000),
# so judge staleness by new sections lacking a link, not by total coverage.
covered = sum(1 for i in new_secs if i in links)
print(f"Deeplinks: {len(links)} entries; {covered}/{len(new_secs)} sections linked")
if old_path.exists():
    new_unlinked = [i for i in added if i not in links]
    if new_unlinked:
        print(f"  {len(new_unlinked)} added sections have no deeplink (first 10): {', '.join(new_unlinked[:10])}")
        print("  -> data/deeplinks.json is likely stale; regenerate it from the NZISM HTML.")
    elif added:
        print("  all added sections have deeplinks.")
else:
    print("  (no previous index; cannot tell whether deeplinks are stale)")
PY

echo
if [[ $CHECK -eq 1 ]]; then
  echo "Check only. Run ./update.sh to apply."
else
  cat <<'EOF'
Next steps:
  1. Update the version and download date in data/README.md.
  2. Refresh data/deeplinks.json if the summary above flagged it as stale.
  3. Redeploy: cd ../nzism-mcp-cdk && npx cdk deploy
EOF
fi
