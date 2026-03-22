#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/WebPresentation"
DEST_DIR="$ROOT_DIR/docs"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Missing source directory: $SRC_DIR" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

rsync -a --delete \
  --exclude '.DS_Store' \
  "$SRC_DIR"/ "$DEST_DIR"/

touch "$DEST_DIR/.nojekyll"

echo "Synced WebPresentation/ -> docs/"
