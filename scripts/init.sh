#!/usr/bin/env bash
# scripts/init.sh — Bootstrap repository with SpecGuard SDD conventions
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATE_FILE="$REPO_DIR/spec_guard/templates/AGENTS.md.template"
VERIFY_SRC="$SCRIPT_DIR/verify-crit.sh"

TARGET_DIR="."
FORCE=false

print_help() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -d, --target-dir <path>      Target directory to bootstrap (default: current directory ".")
  -f, --force                  Overwrite existing AGENTS.md and CLAUDE.md files (default: safe append/update)
  -h, --help                   Show this help message

Behavior:
  - Preserves any pre-existing AGENTS.md by appending the SpecGuard contract
    inside delimited markers (<!-- BEGIN SPECGUARD --> ... <!-- END SPECGUARD -->).
  - If the markers already exist, it updates that section in-place without touching
    custom instructions.
  - Ensures CLAUDE.md references @AGENTS.md.
  - Installs scripts/verify-crit.sh into the target repository.
  - Initializes .spec-guard/ structure if needed.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    -f|--force)
      FORCE=true
      shift
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "Error: Unknown argument '$1'" >&2
      print_help
      exit 1
      ;;
  esac
done

TARGET_DIR="$(cd "$TARGET_DIR" 2>/dev/null && pwd || echo "$TARGET_DIR")"
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Target directory '$TARGET_DIR' does not exist. Creating..."
  mkdir -p "$TARGET_DIR"
  TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"
fi

if [[ ! -f "$TEMPLATE_FILE" ]]; then
  echo "Error: Template file not found at '$TEMPLATE_FILE'" >&2
  exit 1
fi

AGENTS_TARGET="$TARGET_DIR/AGENTS.md"
CLAUDE_TARGET="$TARGET_DIR/CLAUDE.md"
content="$(<"$TEMPLATE_FILE")"

START_MARKER="<!-- BEGIN SPECGUARD -->"
END_MARKER="<!-- END SPECGUARD -->"

# Manage AGENTS.md
if [[ ! -f "$AGENTS_TARGET" ]]; then
  printf '%s\n' "$content" > "$AGENTS_TARGET"
  echo "Created: $AGENTS_TARGET"
elif [[ "$FORCE" == true ]]; then
  printf '%s\n' "$content" > "$AGENTS_TARGET"
  echo "Overwritten (--force): $AGENTS_TARGET"
else
  if grep -q "$START_MARKER" "$AGENTS_TARGET"; then
    python3 -c '
import sys
content, target, start, end = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with open(target, "r", encoding="utf-8") as f:
    text = f.read()
if start in text and end in text:
    pre = text.split(start)[0]
    post = text.split(end, 1)[1]
    new_text = pre.rstrip() + "\n\n" + content.strip() + "\n" + post.lstrip("\n")
    with open(target, "w", encoding="utf-8") as f:
        f.write(new_text)
' "$content" "$AGENTS_TARGET" "$START_MARKER" "$END_MARKER"
    echo "Updated existing SpecGuard contract block in: $AGENTS_TARGET"
  else
    printf '\n\n%s\n' "$content" >> "$AGENTS_TARGET"
    echo "Appended SpecGuard contract to existing: $AGENTS_TARGET (preserved custom rules)"
  fi
fi

# Manage CLAUDE.md
if [[ ! -f "$CLAUDE_TARGET" ]]; then
  printf '@AGENTS.md\n' > "$CLAUDE_TARGET"
  echo "Created: $CLAUDE_TARGET (pointing to @AGENTS.md)"
elif [[ "$FORCE" == true ]]; then
  printf '@AGENTS.md\n' > "$CLAUDE_TARGET"
  echo "Overwritten (--force): $CLAUDE_TARGET (pointing to @AGENTS.md)"
else
  if grep -q '@AGENTS.md' "$CLAUDE_TARGET"; then
    echo "Notice: $CLAUDE_TARGET already references @AGENTS.md"
  else
    printf '\n@AGENTS.md\n' >> "$CLAUDE_TARGET"
    echo "Appended: @AGENTS.md reference to existing $CLAUDE_TARGET"
  fi
fi

# Install verify-crit.sh
VERIFY_DEST_DIR="$TARGET_DIR/scripts"
VERIFY_DEST="$VERIFY_DEST_DIR/verify-crit.sh"
if [[ -f "$VERIFY_SRC" ]]; then
  if [[ "$(readlink -f "$VERIFY_SRC")" != "$(readlink -f "$VERIFY_DEST" 2>/dev/null || echo "$VERIFY_DEST")" ]]; then
    mkdir -p "$VERIFY_DEST_DIR"
    cp "$VERIFY_SRC" "$VERIFY_DEST"
    chmod +x "$VERIFY_DEST"
    echo "Installed: $VERIFY_DEST"
  else
    chmod +x "$VERIFY_DEST"
  fi
fi

# Ensure .spec-guard directory structure
mkdir -p "$TARGET_DIR/.spec-guard/changes" "$TARGET_DIR/.spec-guard/specs"

echo ""
echo "Bootstrap complete."
echo "Contract file: $AGENTS_TARGET"
echo "Claude import: $CLAUDE_TARGET"
