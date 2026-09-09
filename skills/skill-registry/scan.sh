#!/bin/sh
# Skill Registry — Escáner POSIX
# Escanea $HOME/.skills-custom y ./skills-custom e identifica skills personalizadas para indexar.
# Uso: sh skills/skill-registry/scan.sh

GLOBAL_DIR="$HOME/.skills-custom"
LOCAL_DIR="./skills-custom"
OUTPUT="./.spec-guard/skill-registry.md"

# Crear directorio de salida si no existe
mkdir -p ./.spec-guard

# Encabezado del índice
cat > "$OUTPUT" << 'HEADER'
# Skill Registry

Generado automáticamente por skill-registry/scan.sh

| Nombre | Descripción | Trigger | Ubicación |
|--------|-------------|---------|-----------|
HEADER

found=0

for SKILLS_DIR in "$GLOBAL_DIR" "$LOCAL_DIR"; do
  # Verificar que el directorio base existe
  [ -d "$SKILLS_DIR" ] || continue

  # Iterar sobre cada subdirectorio de skills
  for dir in "$SKILLS_DIR"/*/; do
    # Verificar que el directorio de la skill existe (por si está vacío)
    [ -d "$dir" ] || continue

    name=$(basename "$dir")

  # Ignorar directorios con prefijo _ y directorios heredados del viejo esquema
  case "$name" in
    _*)    continue ;;
  esac

  # Verificar que existe SKILL.md
  skill_file="$dir/SKILL.md"
  [ -f "$skill_file" ] || continue

  # Extraer descripción del frontmatter YAML usando awk
  # Busca entre los "---" del frontmatter, extrae desde "description:" hasta
  # encontrar "license:" o "metadata:" o fin de frontmatter
  desc=$(awk '
    /^---$/ { fm_count++; next }
    fm_count == 1 {
      if (in_desc) {
        if ($0 ~ /^license:/ || $0 ~ /^metadata:/ || $0 ~ /^name:/ || $0 ~ /^---$/) {
          in_desc = 0
          next
        }
        # Continuación de descripción multiline
        gsub(/^[[:space:]]+/, "", $0)
        if (length($0) > 0) {
          if (desc_text != "") desc_text = desc_text " " $0
          else desc_text = $0
        }
        next
      }
      if ($0 ~ /^description:/) {
        in_desc = 1
        # Extraer valor inline si existe
        val = $0
        sub(/^description:[[:space:]]*>?[[:space:]]*/, "", val)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
        if (length(val) > 0) desc_text = val
        next
      }
    }
    END { print desc_text }
  ' "$skill_file")

  # Fallback si no se encontró descripción
  if [ -z "$desc" ]; then
    desc="(Sin descripción)"
  fi

  # Extraer disparador del contenido del archivo
  trigger=$(grep -i "disparador" "$skill_file" | head -1 | sed 's/.*[*_]*[Dd]isparador[*_]*:[[:space:]]*//;s/[[:space:]]*\.$//')

  if [ -z "$trigger" ]; then
    trigger="(No especificado)"
  fi

  # Limpiar doble /
  clean_path=$(echo "$skill_file" | sed 's|//|/|g')

  # Escribir entrada al índice
  echo "| **$name** | $desc | $trigger | \`$clean_path\` |" >> "$OUTPUT"
  found=1
  done
done

# Si no se encontraron skills, indicar vacío
if [ "$found" -eq 0 ]; then
  echo "_No se encontraron skills adicionales a las fases._" >> "$OUTPUT"
fi

echo ""
echo "Índice generado en: $OUTPUT"
