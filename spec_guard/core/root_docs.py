"""
root_docs.py — Pure parsers for the 2-File Root Protocol.

The project's single sources of truth live at the repository root:
  - requirements.md (PRD): vision, strict glossary, roles, RF-XXX, out of scope
  - design.md (SAD): mandatory stack, data model, contracts, rules, security

This module only reads/transforms text and resolves paths; it never mutates
state.ini. Standard library only.
"""
import configparser
import re
import unicodedata
from pathlib import Path

__all__ = [
    "REQUIREMENTS_SECTIONS",
    "DESIGN_SECTIONS",
    "RF_ID_RE",
    "PLACEHOLDER_RE",
    "find_root_dir",
    "read_rf_scope",
    "spec_mode",
    "strip_html_comments",
    "section_body",
    "parse_rfs",
    "parse_glossary",
    "find_placeholders",
    "set_rf_checked",
    "crit_matches",
]

# Section keyword sets (accent/case-insensitive, ES/EN).
REQUIREMENTS_SECTIONS = {
    "vision": ("vision",),
    "glossary": ("glosario", "glossary"),
    "roles": ("roles",),
    "functional": ("requerimientos funcionales", "requisitos funcionales", "functional requirements"),
    "out_of_scope": ("fuera del alcance", "fuera de alcance", "out of scope"),
}
DESIGN_SECTIONS = {
    "stack": ("stack",),
    "data_model": ("modelo de datos", "data model"),
    "contracts": ("contratos", "contracts", "interfaces"),
    "rules": ("reglas", "patrones", "rules", "patterns"),
    "security": ("seguridad", "security"),
}

RF_ID_RE = re.compile(r"^RF-\d+$")
PLACEHOLDER_RE = re.compile(r"\{[A-ZÁÉÍÓÚa-záéíóú][^}]{3,80}\}")

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_HEADING_LE3_RE = re.compile(r"^#{1,3}\s", re.MULTILINE)
_RF_HEADING_RE = re.compile(r"^###\s+\[( |x|X)\]\s+(RF-\d+)\s*:\s*(.+?)\s*$", re.MULTILINE)
_CRIT_LINE_RE = re.compile(
    r"^\s*-\s*\[( |x|X)\]\s*(CRIT-\d+(?:-\d+)?)\s*"
    r"(?:\[(automated|manual)\]|\((manual)\))?\s*:?\s*(.*)$",
    re.IGNORECASE,
)
_DESCRIPTION_RE = re.compile(
    r"^\s*-\s*\*\*(?:Descripci[oó]n|Description)\s*:?\s*\*\*\s*:?\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?$")


def _fold(text: str) -> str:
    """Lowercase and strip accents for keyword matching."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


# ─── Paths and change mode ──────────────────────────────────────────────────

def find_root_dir(change_dir: Path) -> Path:
    """.spec-guard/changes/<change> -> repository root."""
    return Path(change_dir).resolve().parent.parent.parent


def read_rf_scope(change_dir: Path) -> list:
    """Return the RF IDs stored in state.ini [Scope] rf_ids (empty if absent)."""
    state = Path(change_dir) / "state.ini"
    if not state.exists():
        return []
    cfg = configparser.ConfigParser()
    cfg.read(state, encoding="utf-8")
    raw = cfg.get("Scope", "rf_ids", fallback="").strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


def spec_mode(change_dir: Path) -> str:
    """'legacy' when the change owns objective.md; 'root' when RF-scoped or root docs exist."""
    change_dir = Path(change_dir)
    if (change_dir / "objective.md").exists():
        return "legacy"
    if read_rf_scope(change_dir):
        return "root"
    if (find_root_dir(change_dir) / "requirements.md").exists():
        return "root"
    return "legacy"


# ─── Generic Markdown helpers ───────────────────────────────────────────────

def strip_html_comments(text: str) -> str:
    return _HTML_COMMENT_RE.sub("", text)


def section_body(text: str, keywords) -> "str | None":
    """Body of the first H2 whose heading contains any keyword (until next H1/H2)."""
    matches = list(_H2_RE.finditer(text))
    for idx, m in enumerate(matches):
        heading = _fold(m.group(1))
        if any(_fold(k) in heading for k in keywords):
            start = m.end()
            nxt = re.search(r"^#{1,2}\s", text[start:], re.MULTILINE)
            return text[start:start + nxt.start()] if nxt else text[start:]
    return None


def find_placeholders(text: str) -> list:
    return PLACEHOLDER_RE.findall(text)


# ─── Requirements parsing ───────────────────────────────────────────────────

def parse_rfs(text: str) -> list:
    """Parse every '### [ ] RF-NNN: Title' block."""
    rfs = []
    for m in _RF_HEADING_RE.finditer(text):
        start = m.end()
        nxt = _HEADING_LE3_RE.search(text, start)
        body = text[start:nxt.start()] if nxt else text[start:]
        desc_m = _DESCRIPTION_RE.search(body)
        criteria = []
        for line in body.splitlines():
            cm = _CRIT_LINE_RE.match(line)
            if not cm:
                continue
            kind = (cm.group(3) or cm.group(4) or "automated").lower()
            criteria.append({
                "id": cm.group(2).upper(),
                "type": "manual" if kind == "manual" else "automated",
                "checked": cm.group(1).lower() == "x",
                "description": cm.group(5).strip(),
            })
        rfs.append({
            "id": m.group(2),
            "title": m.group(3),
            "checked": m.group(1).lower() == "x",
            "description": desc_m.group(1).strip() if desc_m else "",
            "criteria": criteria,
        })
    return rfs


def parse_glossary(text: str) -> list:
    """Parse the strict glossary table: term | definition | forbidden synonyms."""
    body = section_body(text, REQUIREMENTS_SECTIONS["glossary"])
    if body is None:
        return []
    rows = [l.strip() for l in body.splitlines() if l.strip().startswith("|")]
    entries = []
    for i, row in enumerate(rows):
        if i == 0 or _TABLE_SEPARATOR_RE.match(row):
            continue  # header or separator
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 2:
            continue
        term = cells[0].replace("**", "").strip()
        if not term:
            continue
        forbidden_cell = cells[2] if len(cells) > 2 else ""
        forbidden = [f.strip().rstrip(".").strip() for f in forbidden_cell.split(",")]
        entries.append({
            "term": term,
            "definition": cells[1],
            "forbidden": [f for f in forbidden if f],
        })
    return entries


def set_rf_checked(text: str, rf_id: str):
    """Mark an RF heading and its criteria as [x]. Returns (new_text, status).

    status: 'SUCCESS' | 'ALREADY_DONE' | 'NOT_FOUND'
    """
    comment_spans = [(c.start(), c.end()) for c in _HTML_COMMENT_RE.finditer(text)]
    for m in _RF_HEADING_RE.finditer(text):
        if m.group(2) != rf_id:
            continue
        if any(s <= m.start() < e for s, e in comment_spans):
            continue
        if m.group(1).lower() == "x":
            return text, "ALREADY_DONE"
        start = m.end()
        nxt = _HEADING_LE3_RE.search(text, start)
        end = nxt.start() if nxt else len(text)
        heading = text[m.start():start].replace("[ ]", "[x]", 1)
        body_lines = []
        for line in text[start:end].splitlines(keepends=True):
            if _CRIT_LINE_RE.match(line.rstrip("\r\n")):
                line = line.replace("[ ]", "[x]", 1)
            body_lines.append(line)
        return text[:m.start()] + heading + "".join(body_lines) + text[end:], "SUCCESS"
    return text, "NOT_FOUND"


# ─── CRIT traceability ──────────────────────────────────────────────────────

def crit_matches(crit_id: str, line: str) -> bool:
    """True if `line` references exactly `crit_id` (CRIT-1 never matches CRIT-10).

    `\\b` is not usable because '_' is a word char (test_crit_01_x). Instead:
    no alphanumeric before, no digit or '[-_]digit' after.
    """
    numbers = re.findall(r"\d+", crit_id)
    if not numbers:
        return False
    core = "crit" + "".join(r"[-_]" + n for n in numbers)
    pattern = r"(?<![a-z0-9])" + core + r"(?![0-9])(?![-_][0-9])"
    return re.search(pattern, line, re.IGNORECASE) is not None
