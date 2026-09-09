#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# State Guard: Universal Install Script
# ============================================================================

# 1. Manejo de argumentos (Solo aceptamos --help)
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ./install.sh"
    echo "Instala State Guard de forma universal en los orquestadores soportados."
    exit 0
elif [[ $# -gt 0 ]]; then
    echo "Error: Opcion desconocida '$1'."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
SOURCE_SKILLS_DIR="$REPO_DIR/skills"
SOURCE_PHASES_DIR="$REPO_DIR/phases"
TARGET_DIR="$HOME/.agents/skills/spec-guard"

MARKER_START="<!-- spec-guard:begin -->"
MARKER_END="<!-- spec-guard:end -->"

echo "Iniciando instalación de State Guard..."

# 2. Creación de directorio unificado e instalación de skills y fases
mkdir -p "$TARGET_DIR/phases/_shared"

# Copiar fases (archivos planos)
phase_count=0
for phase_file in "$SOURCE_PHASES_DIR"/*.md; do
    [ -f "$phase_file" ] || continue
    cp "$phase_file" "$TARGET_DIR/phases/"
    echo "  - fase: $(basename "$phase_file" .md)"
    phase_count=$((phase_count + 1))
done

# Copiar contratos compartidos de fases
cp -r "$SOURCE_PHASES_DIR/_shared/"* "$TARGET_DIR/phases/_shared/"

echo "✓ $phase_count fases instaladas en $TARGET_DIR/phases/"

# Copiar skills discoverable (SKILL.md con frontmatter)
count=0
for skill_dir in "$SOURCE_SKILLS_DIR"/*/; do
    skill_name=$(basename "$skill_dir")
    if [[ "$skill_name" == "_shared" ]]; then continue; fi
    if [[ -f "${skill_dir}SKILL.md" ]]; then
        mkdir -p "$TARGET_DIR/$skill_name"
        cp "${skill_dir}SKILL.md" "$TARGET_DIR/$skill_name/SKILL.md"
        echo "  - $skill_name"
        count=$((count + 1))
    fi
done

echo "✓ $count skills instaladas en $TARGET_DIR"

# 3. Inyección idempotente en orquestadores soportados
CONFIG_FILES=(
    "$HOME/.config/opencode/system_prompt.md"
    "$HOME/.gemini/system_prompt.md"
)

# El bloque que se inyectará entre los marcadores
INJECTION_TEXT="$MARKER_START
# State Guard: Framework de Memoria Transaccional
Las habilidades ejecutables se encuentran en: $TARGET_DIR
Debes cargar y obedecer los contratos transaccionales (BEGIN/COMMIT) definidos en _shared.
$MARKER_END"

for config_file in "${CONFIG_FILES[@]}"; do
    if [[ -f "$config_file" ]]; then
        # Eliminamos el bloque anterior si existe (Idempotencia) usando .bak para compatibilidad MacOS/Linux
        sed -i.bak "/$MARKER_START/,/$MARKER_END/d" "$config_file"
        rm -f "$config_file.bak"
        
        # Inyectamos el nuevo bloque al final del archivo
        echo -e "\n$INJECTION_TEXT" >> "$config_file"
        echo "✓ Marcadores inyectados en $config_file"
    fi
done

echo "Done!"