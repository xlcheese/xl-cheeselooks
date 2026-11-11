"""Fill templates with tokens.

Templates are ordinary theme files with {{...}} placeholders. A placeholder
is either a token name or a small color expression:

    {{accent}}                      a token
    {{alpha(text, 0.87)}}           rgba() of a color at an opacity
    {{mix(bg, text, 0.23)}}         blend from the first color toward the second
    {{lighter(accent, 0.1)}}        blend toward white
    {{darker(header, 0.05)}}        blend toward black

Arguments can be token names, #RRGGBB colors, numbers, or other expressions.
All math happens here in Python, so the same expressions work in GTK and
Cinnamon CSS. Files ending in .tmpl are filled and saved without the
suffix; every other file is copied as-is. An unknown token or a bad
expression is an error, so a typo never ships a broken theme.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import palette as pal

PLACEHOLDER_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")
TEMPLATE_SUFFIX = ".tmpl"
_TOKEN_CHARS = re.compile(r"[A-Za-z0-9_.\-#]")


class TemplateError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


class _ExprError(ValueError):
    pass


def _color(value: object) -> str:
    if isinstance(value, str) and pal.is_hex(value):
        return pal.normalize(value)
    raise _ExprError(f"expected a color, got {value!r}")


def _number(value: object) -> float:
    if isinstance(value, float):
        return value
    raise _ExprError(f"expected a number, got {value!r}")


FUNCTIONS = {
    "alpha": lambda c, a: pal.rgba(_color(c), _number(a)),
    "mix": lambda a, b, t: pal.mix(_color(a), _color(b), _number(t)),
    "lighter": lambda c, t: pal.lighter(_color(c), _number(t)),
    "darker": lambda c, t: pal.darker(_color(c), _number(t)),
}


def evaluate(expr: str, tokens: dict[str, str]) -> str:
    """Evaluate a placeholder: a token name or a function call."""
    pos = 0

    def skip() -> None:
        nonlocal pos
        while pos < len(expr) and expr[pos].isspace():
            pos += 1

    def parse() -> object:
        nonlocal pos
        skip()
        start = pos
        while pos < len(expr) and _TOKEN_CHARS.match(expr[pos]):
            pos += 1
        word = expr[start:pos]
        if not word:
            raise _ExprError(f"unexpected '{expr[pos:pos + 1] or 'end'}'")
        skip()
        if pos < len(expr) and expr[pos] == "(":
            if word not in FUNCTIONS:
                raise _ExprError(f"unknown function '{word}' (known: {', '.join(FUNCTIONS)})")
            pos += 1
            args = []
            skip()
            if pos < len(expr) and expr[pos] == ")":
                pos += 1
            else:
                while True:
                    args.append(parse())
                    skip()
                    if pos < len(expr) and expr[pos] == ",":
                        pos += 1
                        continue
                    if pos < len(expr) and expr[pos] == ")":
                        pos += 1
                        break
                    raise _ExprError("expected ',' or ')'")
            try:
                return FUNCTIONS[word](*args)
            except TypeError:
                raise _ExprError(f"wrong number of arguments for {word}()") from None
        if re.fullmatch(r"-?\d+(\.\d+)?", word):
            return float(word)
        if word.startswith("#"):
            return _color(word)
        if word in tokens:
            return tokens[word]
        raise _ExprError(f"unknown token '{word}'")

    value = parse()
    skip()
    if pos != len(expr):
        raise _ExprError(f"unexpected text after expression: '{expr[pos:]}'")
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def render_text(text: str, tokens: dict[str, str], source: str = "<text>") -> str:
    problems: list[str] = []
    cache: dict[str, str] = {}

    def sub(m: re.Match) -> str:
        expr = m.group(1)
        if expr in cache:
            return cache[expr]
        try:
            value = evaluate(expr, tokens)
        except _ExprError as exc:
            line = text.count("\n", 0, m.start()) + 1
            problems.append(f"{source}:{line}: {{{{{expr}}}}}: {exc}")
            return m.group(0)
        cache[expr] = value
        return value

    out = PLACEHOLDER_RE.sub(sub, text)
    if problems:
        raise TemplateError(problems)
    return out


INCLUDE_RE = re.compile(r'\{\{\s*include\s+"([^"]+)"\s*\}\}')
PART_SUFFIX = ".part"


def expand_includes(text: str, base: Path, depth: int = 0) -> str:
    """Replace {{include "file.part"}} with that file's text (relative to base).
    .part files are only ever included, never written to the theme."""
    if depth > 5:
        raise TemplateError([f"includes nested too deeply under {base}"])

    def sub(m: re.Match) -> str:
        part = base / m.group(1)
        if not part.is_file():
            raise TemplateError([f"include not found: {part}"])
        return expand_includes(part.read_text(encoding="utf-8"), part.parent, depth + 1)

    return INCLUDE_RE.sub(sub, text)


def render_tree(src: Path, dest: Path, tokens: dict[str, str]) -> list[Path]:
    """Render every template under src into dest. Returns the files written."""
    problems: list[str] = []
    written: list[Path] = []
    for path in sorted(src.rglob("*")):
        if path.is_dir() or path.suffix == PART_SUFFIX:
            continue
        rel = path.relative_to(src)
        if path.suffix == TEMPLATE_SUFFIX:
            target = dest / rel.with_suffix("")
            try:
                text = expand_includes(path.read_text(encoding="utf-8"), path.parent)
                content = render_text(text, tokens, str(rel))
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
