#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# SpecGuard: Universal Install Script (OpenCode / Antigravity)
# ============================================================================

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ./install.sh"
    echo "Instala SpecGuard de forma universal."
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
LEGACY_MARKER_START="<!-- state-guard:begin -->"
LEGACY_MARKER_END="<!-- state-guard:end -->"

echo "Iniciando instalación universal de SpecGuard..."

# 1. Directorios unificados y copia de código, skills, fases y binarios
mkdir -p "$TARGET_DIR/bin" "$TARGET_DIR/_shared" "$TARGET_DIR/phases/_shared" "$TARGET_DIR/templates"

echo "→ Copiando paquete canónico spec_guard y binarios..."
cp -r "$REPO_DIR/spec_guard" "$TARGET_DIR/"
cp "$SCRIPT_DIR"/*.py "$TARGET_DIR/bin/" 2>/dev/null || true
cp "$SCRIPT_DIR"/*.sh "$TARGET_DIR/bin/" 2>/dev/null || true
chmod +x "$TARGET_DIR/bin"/*.py "$TARGET_DIR/bin"/*.sh 2>/dev/null || true

echo "→ Copiando plantillas..."
cp -r "$REPO_DIR/spec_guard/templates/"* "$TARGET_DIR/templates/" 2>/dev/null || true

echo "→ Copiando contratos y skills..."
cp -r "$SOURCE_SKILLS_DIR/_shared/"* "$TARGET_DIR/_shared/"

# Copiar contratos compartidos de fases
cp -r "$SOURCE_PHASES_DIR/_shared/"* "$TARGET_DIR/phases/_shared/"

# Copiar fases
phase_count=0
for phase_file in "$SOURCE_PHASES_DIR"/*.md; do
    [ -f "$phase_file" ] || continue
    cp "$phase_file" "$TARGET_DIR/phases/"
    phase_count=$((phase_count + 1))
done
echo "  ✓ $phase_count fases instaladas en $TARGET_DIR/phases/"

# Copiar skills discoverable (SKILL.md con frontmatter)
count=0
for skill_dir in "$SOURCE_SKILLS_DIR"/*/; do
    skill_name=$(basename "$skill_dir")
    if [[ "$skill_name" == "_shared" ]]; then continue; fi
    if [[ -f "${skill_dir}SKILL.md" ]]; then
        mkdir -p "$TARGET_DIR/$skill_name"
        cp "${skill_dir}SKILL.md" "$TARGET_DIR/$skill_name/SKILL.md"
        count=$((count + 1))
    fi
done
echo "  ✓ $count skills instaladas en $TARGET_DIR"

# Enlaces simbólicos en ~/.local/bin si existe o se crea
mkdir -p "$HOME/.local/bin"
ln -sf "$TARGET_DIR/bin/sg.py" "$HOME/.local/bin/sg"
ln -sf "$TARGET_DIR/bin/sg.py" "$HOME/.local/bin/spec-guard"
ln -sf "$TARGET_DIR/bin/verify-crit.sh" "$HOME/.local/bin/sg-verify-crit"
ln -sf "$TARGET_DIR/bin/init.sh" "$HOME/.local/bin/sg-init"
echo "  ✓ Symlinks creados en ~/.local/bin/ (sg, spec-guard, sg-verify-crit, sg-init)"

# 2. Texto de Bootstrap (Directiva Única con primacía de AGENTS.md)
BOOTSTRAP_TEXT=$(cat <<EOF
## ACTIVE SPECIFICATION-DRIVEN DEVELOPMENT (SDD) CONTRACT: SpecGuard
MANDATORY BOOTSTRAP — execute before responding to anything:
1. Obey AGENTS.md in the project root if present; otherwise call read_file on $TARGET_DIR/_shared/memory-guard.md.
2. Follow every instruction in that file as your absolute SDD state contract.
3. SpecGuard CLI binary: $TARGET_DIR/bin/sg.py (or 'sg' in PATH)
   Subcomandos operativos (agente): begin | commit | rollback | checkpoint | status
                                     | next-task | verify-gate | mark-task | verify-crit | session-checkpoint
   Subcomandos EXCLUSIVOS DE HUMANO (el agente nunca los ejecuta):
                                     plan-approve | plan-confirm | hotfix-init | hotfix-confirm
   Si 'commit' devuelve EXIT_GATE_REQUIRED (5): DETENÉ el ciclo y pedile
   al usuario que corra 'sg plan-approve --change <nombre>' en su propia
   terminal, y luego 'sg plan-confirm --change <nombre> --token <CODIGO>'.
4. Check for an active change at .spec-guard/changes/*/state.ini (or legacy .state-guard/changes/*/state.ini)
   and act accordingly (Cold Boot, Resume via 'status', or Recovery).
EOF
)
export BOOTSTRAP_TEXT

# 3. Inyección en Antigravity (GEMINI.md)
GEMINI_FILE="$HOME/.gemini/GEMINI.md"
mkdir -p "$(dirname "$GEMINI_FILE")"
if [[ -f "$GEMINI_FILE" ]]; then
    # Limpiar marcadores legacy y actuales si ya existían
    sed -i.bak "/$LEGACY_MARKER_START/,/$LEGACY_MARKER_END/d" "$GEMINI_FILE" && rm -f "$GEMINI_FILE.bak"
    sed -i.bak "/$MARKER_START/,/$MARKER_END/d" "$GEMINI_FILE" && rm -f "$GEMINI_FILE.bak"
fi
{
    echo
    echo "$MARKER_START"
    echo "$BOOTSTRAP_TEXT"
    echo "$MARKER_END"
} >> "$GEMINI_FILE"
echo "  ✓ Bootstrap inyectado en $GEMINI_FILE"

# 4. Inyección nativa en OpenCode (opencode.jsonc)
echo "→ Configurando OpenCode JSONC..."
python3 - <<'PY'
import json
import os
import re

config_path = os.path.expanduser('~/.config/opencode/opencode.jsonc')
bootstrap = os.environ.get('BOOTSTRAP_TEXT', '')

if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    clean_content = re.sub(r'//.*?\n|/\*.*?\*/', '', content, flags=re.S)
    try:
        cfg = json.loads(clean_content)
    except json.JSONDecodeError:
        cfg = {'$schema': 'https://opencode.ai/config.json', 'agent': {}}
else:
    cfg = {'$schema': 'https://opencode.ai/config.json', 'agent': {}}

if 'agent' not in cfg:
    cfg['agent'] = {}

# Registrar spec-guard y limpiar legacy si existía
cfg['agent']['spec-guard'] = {
    'mode': 'all',
    'description': 'SpecGuard — Specification-Driven Development (SDD) Engine',
    'prompt': bootstrap,
    'tools': {'read': True, 'write': True, 'edit': True, 'bash': True},
}
if 'state-guard' in cfg['agent']:
    del cfg['agent']['state-guard']

os.makedirs(os.path.dirname(config_path), exist_ok=True)
with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
PY
echo "  ✓ Agente spec-guard registrado directamente en opencode.jsonc"

# 5. Generación Dinámica de Slash Commands (OpenCode)
CMD_DIR="$HOME/.config/opencode/commands"
mkdir -p "$CMD_DIR"
rm -f "$CMD_DIR"/*.md 2>/dev/null || true

echo "→ Generando Slash Commands dinámicos..."
cmd_count=0

# Generar slash commands para fases (phases/*.md)
for phase_file in "$TARGET_DIR/phases"/*.md; do
    [ -f "$phase_file" ] || continue
    phase_name=$(basename "$phase_file" .md)
    desc=$(head -5 "$phase_file" | grep '^# ' | head -1 | sed 's/^# //')
    [ -z "$desc" ] && desc="Fase $phase_name"

    cat > "$CMD_DIR/${phase_name}.md" <<EOF
---
description: "$desc"
agent: spec-guard
---
Lee el archivo $TARGET_DIR/phases/${phase_name}.md y ejecuta sus instrucciones al pie de la letra.
EOF
    cmd_count=$((cmd_count + 1))
done

# Generar slash commands para skills discoverable (SKILL.md)
for skill_dir in "$TARGET_DIR"/*/; do
    skill_name=$(basename "$skill_dir")
    if [[ "$skill_name" == "_shared" || "$skill_name" == "bin" || "$skill_name" == "phases" || "$skill_name" == "spec_guard" ]]; then continue; fi
    if [[ ! -f "${skill_dir}SKILL.md" ]]; then continue; fi
    desc=$(python3 - <<'PY' "${skill_dir}SKILL.md"
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
lines = text.splitlines()
for idx, line in enumerate(lines):
    if line.startswith('description:'):
        value = line.split(':', 1)[1].strip()
        if value.startswith('>'):
            if idx + 1 < len(lines):
                print(lines[idx + 1].strip())
            else:
                print('')
        else:
            print(value.strip('"').strip("'"))
        break
else:
    print('')
PY
)

    cat > "$CMD_DIR/${skill_name}.md" <<EOF
---
description: "$desc"
agent: spec-guard
---
Lee el archivo $TARGET_DIR/$skill_name/SKILL.md y ejecuta sus instrucciones al pie de la letra.
EOF
    cmd_count=$((cmd_count + 1))
done
echo "  ✓ $cmd_count slash commands generados al vuelo."

echo "→ Tip: Podés ejecutar 'sg install-hooks' en tu repositorio para activar hooks de git (ej. post-commit)."

# 6. Bootstrap del repositorio actual si estamos en un repo git
if git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "→ Inicializando AGENTS.md y CLAUDE.md en el repositorio..."
    "$SCRIPT_DIR/init.sh" --target-dir "$REPO_DIR" || true
fi

echo -e "\nDone! SpecGuard v3.0.0 instalado exitosamente."