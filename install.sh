#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# SpecGuard: Universal Install & Uninstall Script (OpenCode / Antigravity)
# ============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SKILL_FILE="$REPO_DIR/SKILL.md"
TARGET_DIR="$HOME/.agents/skills/spec-guard"
STATE_GUARD_DIR="$HOME/.agents/skills/state-guard"
GEMINI_SKILLS_DIR="$HOME/.gemini/config/skills/spec-guard"

MARKER_START="<!-- spec-guard:begin -->"
MARKER_END="<!-- spec-guard:end -->"
LEGACY_MARKER_START="<!-- state-guard:begin -->"
LEGACY_MARKER_END="<!-- state-guard:end -->"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: ./install.sh [--uninstall]"
    echo "Instala o desinstala SpecGuard de forma universal."
    exit 0
elif [[ "${1:-}" == "--uninstall" || "${1:-}" == "--cleanup" ]]; then
    echo "Iniciando limpieza de SpecGuard..."
    for d in "$TARGET_DIR" "$STATE_GUARD_DIR" "$GEMINI_SKILLS_DIR"; do
        if [ -d "$d" ]; then
            rm -rf "$d"
            echo "✓ Directorio eliminado: $d"
        fi
    done

    rm -f "$HOME/.local/bin/sg" "$HOME/.local/bin/spec-guard" "$HOME/.local/bin/sg-verify-crit" "$HOME/.local/bin/sg-init" 2>/dev/null || true

    CONFIG_FILES=(
        "$HOME/.config/opencode/AGENTS.md"
        "$HOME/.gemini/GEMINI.md"
        "$HOME/.gemini/system_prompt.md"
    )
    for file in "${CONFIG_FILES[@]}"; do
        if [ -f "$file" ]; then
            sed -i.bak "/$MARKER_START/,/$MARKER_END/d" "$file"
            sed -i.bak "/$LEGACY_MARKER_START/,/$LEGACY_MARKER_END/d" "$file"
            rm -f "$file.bak"
            echo "✓ Inyección limpiada en: $file"
        fi
    done

    python3 - <<'PY' 2>/dev/null || true
import json, os, re
config_path = os.path.expanduser('~/.config/opencode/opencode.jsonc')
if os.path.exists(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        clean = re.sub(r'//.*?\n|/\*.*?\*/', '', f.read(), flags=re.S)
    try:
        cfg = json.loads(clean)
        modified = False
        for k in ['spec-guard', 'state-guard']:
            if k in cfg.get('agent', {}):
                del cfg['agent'][k]
                modified = True
        if modified:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            print("✓ Agentes eliminados de opencode.jsonc")
    except Exception:
        pass
PY
    echo "Limpieza completada."
    exit 0
elif [[ $# -gt 0 ]]; then
    echo "Error: Opcion desconocida '$1'."
    exit 1
fi

echo "Iniciando instalación universal de SpecGuard..."

# 1. Directorios unificados y copia de paquete spec_guard, skill canónica y plantillas
mkdir -p "$TARGET_DIR/templates" "$TARGET_DIR/spec-guard"

echo "→ Copiando paquete canónico spec_guard..."
cp -r "$REPO_DIR/spec_guard" "$TARGET_DIR/"
chmod +x "$TARGET_DIR/spec_guard/cli.py" "$TARGET_DIR/spec_guard/core/state_manager.py" 2>/dev/null || true

echo "→ Copiando plantillas..."
cp -r "$REPO_DIR/spec_guard/templates/"* "$TARGET_DIR/templates/" 2>/dev/null || true
chmod +x "$TARGET_DIR/templates/verify-crit.sh" 2>/dev/null || true

echo "→ Copiando skill canónica SKILL.md..."
cp "$SOURCE_SKILL_FILE" "$TARGET_DIR/SKILL.md"
cp "$SOURCE_SKILL_FILE" "$TARGET_DIR/spec-guard/SKILL.md"
echo "  ✓ Skill canónica instalada en $TARGET_DIR/SKILL.md"

# 1b. Instalación de Skill nativa en Antigravity (~/.gemini/config/skills/spec-guard/)
echo "→ Instalando Skill nativa en Antigravity ($GEMINI_SKILLS_DIR)..."
mkdir -p "$GEMINI_SKILLS_DIR"
cp "$SOURCE_SKILL_FILE" "$GEMINI_SKILLS_DIR/SKILL.md"
echo "  ✓ Skill spec-guard registrada en Antigravity ($GEMINI_SKILLS_DIR/SKILL.md)"

# Enlaces simbólicos en ~/.local/bin
mkdir -p "$HOME/.local/bin"
ln -sf "$TARGET_DIR/spec_guard/cli.py" "$HOME/.local/bin/sg"
ln -sf "$TARGET_DIR/spec_guard/cli.py" "$HOME/.local/bin/spec-guard"
ln -sf "$TARGET_DIR/templates/verify-crit.sh" "$HOME/.local/bin/sg-verify-crit"
echo "  ✓ Symlinks creados en ~/.local/bin/ (sg, spec-guard, sg-verify-crit)"

# 2. Texto de Bootstrap (Directiva Única con primacía de AGENTS.md)
BOOTSTRAP_TEXT=$(cat <<EOF
## ACTIVE SPECIFICATION-DRIVEN DEVELOPMENT (SDD) CONTRACT: SpecGuard
MANDATORY BOOTSTRAP — execute before responding to anything:
1. Obey AGENTS.md in the project root if present; otherwise call read_file on $TARGET_DIR/SKILL.md.
2. Follow every instruction in that file as your absolute SDD state contract.
3. SpecGuard CLI binary: $TARGET_DIR/spec_guard/cli.py (or 'sg' in PATH)
   Subcomandos operativos (agente): init | context | next-rf-id | init-change | rf-status | mark-rf
                                     | glossary-check | validate-spec | begin | commit | rollback
                                     | checkpoint | session-checkpoint | status | list-changes
                                     | next-task | verify-gate | mark-task | verify-crit | install-hooks
   Subcomandos EXCLUSIVOS DE HUMANO (el agente nunca los ejecuta):
                                     plan-approve | plan-confirm | hotfix-init | hotfix-confirm
   En modo 'chat' (default), para avanzar de PLAN a EXECUTE solicita aprobación en el chat (STOP)
   y luego ejecuta 'sg commit --change <nombre> --next-phase execute --approval-text "<respuesta>"'.
   En modo 'strict', si 'commit' devuelve EXIT_GATE_REQUIRED (5): DETENÉ el ciclo y pedile
   al usuario que corra 'sg plan-approve --change <nombre>' en su propia
   terminal, y luego 'sg plan-confirm --change <nombre> --token <CODIGO>'.
4. Check for an active change at .spec-guard/changes/*/state.ini (or legacy .state-guard/changes/*/state.ini)
   and act accordingly (Cold Boot via 'sg context', Resume via 'sg status', or Recovery).
EOF
)
export BOOTSTRAP_TEXT

# 3. Inyección en Antigravity (GEMINI.md)
GEMINI_FILE="$HOME/.gemini/GEMINI.md"
mkdir -p "$(dirname "$GEMINI_FILE")"
if [[ -f "$GEMINI_FILE" ]]; then
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

echo "→ Tip: Podés ejecutar 'sg install-hooks' en tu repositorio para activar hooks bloqueantes de git (pre-commit y commit-msg)."

# 5. Bootstrap del repositorio actual si estamos en un repo git
if git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "→ Inicializando AGENTS.md y CLAUDE.md en el repositorio..."
    python3 "$REPO_DIR/spec_guard/cli.py" init -d "$REPO_DIR" >/dev/null || true
fi

echo -e "\nDone! SpecGuard v3.0.0 instalado exitosamente."
