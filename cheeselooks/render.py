"""Fill templates with tokens.

Templates are ordinary theme files with {{token}} placeholders. Files ending
in .tmpl are filled and saved without the suffix; every other file is copied
as-is. An unknown token is an error, so a typo never ships a broken theme.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

TOKEN_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")
TEMPLATE_SUFFIX = ".tmpl"


class TemplateError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def render_text(text: str, tokens: dict[str, str], source: str = "<text>") -> str:
    missing: dict[str, int] = {}

    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name in tokens:
            return tokens[name]
        line = text.count("\n", 0, m.start()) + 1
        missing.setdefault(name, line)
        return m.group(0)

    out = TOKEN_RE.sub(sub, text)
    if missing:
        raise TemplateError([f"{source}:{line}: unknown token '{{{{{name}}}}}'"
                             for name, line in missing.items()])
    return out


def render_tree(src: Path, dest: Path, tokens: dict[str, str]) -> list[Path]:
    """Render every template under src into dest. Returns the files written."""
    problems: list[str] = []
    written: list[Path] = []
    for path in sorted(src.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if path.suffix == TEMPLATE_SUFFIX:
            target = dest / rel.with_suffix("")
            try:
                content = render_text(path.read_text(encoding="utf-8"), tokens, str(rel))
            except TemplateError as exc:
                problems.extend(exc.problems)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        else:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        written.append(target)
    if problems:
        raise TemplateError(problems)
    return written
