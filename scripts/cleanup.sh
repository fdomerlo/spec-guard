#!/usr/bin/env bash
# cleanup.sh - Limpia la instalación de SpecGuard (y legacy State Guard)

SPEC_GUARD_DIR="$HOME/.agents/skills/spec-guard"
STATE_GUARD_DIR="$HOME/.agents/skills/state-guard"

MARKERS=(
    "<!-- spec-guard:begin -->" "<!-- spec-guard:end -->"
    "<!-- state-guard:begin -->" "<!-- state-guard:end -->"
)

echo "Iniciando limpieza de SpecGuard..."

# 1. Eliminar directorios de skills
for d in "$SPEC_GUARD_DIR" "$STATE_GUARD_DIR" "$HOME/.gemini/config/skills/spec-guard"; do
    if [ -d "$d" ]; then
        rm -rf "$d"
        echo "✓ Directorio eliminado: $d"
    fi
done

# 2. Eliminar symlinks en ~/.local/bin
rm -f "$HOME/.local/bin/sg" "$HOME/.local/bin/spec-guard" "$HOME/.local/bin/sg-verify-crit" "$HOME/.local/bin/sg-init" 2>/dev/null || true

# 3. Limpiar los archivos de configuración
CONFIG_FILES=(
    "$HOME/.config/opencode/AGENTS.md"
    "$HOME/.gemini/GEMINI.md"
    "$HOME/.gemini/system_prompt.md"
)

for file in "${CONFIG_FILES[@]}"; do
    if [ -f "$file" ]; then
        sed -i.bak "/<!-- spec-guard:begin -->/,/<!-- spec-guard:end -->/d" "$file"
        sed -i.bak "/<!-- state-guard:begin -->/,/<!-- state-guard:end -->/d" "$file"
        rm -f "$file.bak"
        echo "✓ Inyección limpiada en: $file"
    fi
done

# 4. Limpiar opencode.jsonc
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