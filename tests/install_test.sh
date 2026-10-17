#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# SpecGuard: Install Verification Script
# ============================================================================

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ./install.sh"
    echo "Instala SpecGuard de forma universal en los orquestadores soportados."
    exit 0
elif [[ $# -gt 0 ]]; then
    echo "Error: Opcion desconocida '$1'."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SOURCE_SKILL_FILE="$REPO_DIR/SKILL.md"
TARGET_DIR="$HOME/.agents/skills/spec-guard"

MARKER_START="<!-- spec-guard:begin -->"
MARKER_END="<!-- spec-guard:end -->"

echo "Iniciando instalación de SpecGuard..."

mkdir -p "$TARGET_DIR/spec-guard"
cp "$SOURCE_SKILL_FILE" "$TARGET_DIR/SKILL.md"
cp "$SOURCE_SKILL_FILE" "$TARGET_DIR/spec-guard/SKILL.md"
echo "✓ Skill canónica spec-guard instalada en $TARGET_DIR"

CONFIG_FILES=(
    "$HOME/.config/opencode/system_prompt.md"
    "$HOME/.gemini/system_prompt.md"
)

INJECTION_TEXT="$MARKER_START
# SpecGuard: Motor SDD y Memoria Transaccional
La habilidad canónica se encuentra en: $TARGET_DIR/SKILL.md
$MARKER_END"

for config_file in "${CONFIG_FILES[@]}"; do
    if [[ -f "$config_file" ]]; then
        sed -i.bak "/$MARKER_START/,/$MARKER_END/d" "$config_file"
        rm -f "$config_file.bak"
        echo -e "\n$INJECTION_TEXT" >> "$config_file"
        echo "✓ Marcadores inyectados en $config_file"
    fi
done

echo "Done!"