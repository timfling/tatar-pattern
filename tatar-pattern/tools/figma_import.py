#!/usr/bin/env python3
"""
Восстановление кода дизайн-фреймов из файлов, сохранённых через TextEdit.

Плагин "Figma to Code" отдаёт обычный HTML, но при сохранении через TextEdit
он оборачивается в документ Cocoa HTML Writer, а сам код экранируется
(&lt;div&gt; вместо <div>). Скрипт снимает обёртку и возвращает исходный код.

Дополнительно:
  * вырезает inline-SVG в отдельные файлы (с дедупликацией по содержимому),
  * строит текстовый "дайджест" фрейма — дерево слоёв со стилями, но без
    громоздких SVG-путей, чтобы макет можно было читать целиком.

Запуск:  python3 tools/figma_import.py
"""

import hashlib
import html
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Информация о проекте" / "html дизайнов"
OUT = ROOT / "tatar-pattern" / "design"

CLEAN = OUT / "frames"
ICONS = OUT / "icons"
DIGEST = OUT / "digests"

SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)
COCOA_MARKER = "Cocoa HTML Writer"


def unwrap(raw: str) -> str:
    """Достаёт исходный код из документа TextEdit."""
    if COCOA_MARKER not in raw:
        return raw

    body = raw.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    # Каждая строка исходника — отдельный <p class="p1">.
    lines = []
    for para in re.findall(r"<p class=\"p1\">(.*?)</p>", body, re.S):
        text = re.sub(r"<[^>]+>", "", para)
        text = html.unescape(text).replace("\xa0", " ")
        lines.append(text.rstrip())
    return "\n".join(lines) + "\n"


def extract_icons(code: str, frame: str) -> tuple[str, dict[str, str]]:
    """Заменяет inline-SVG на плейсхолдер, сохраняя картинки на диск."""
    saved: dict[str, str] = {}

    def repl(match: re.Match) -> str:
        svg = match.group(0)
        digest = hashlib.sha1(svg.encode()).hexdigest()[:8]
        w = re.search(r'width="([\d.]+)"', svg)
        h = re.search(r'height="([\d.]+)"', svg)
        size = f"{w.group(1)}x{h.group(1)}" if w and h else "?"

        path = ICONS / f"{digest}.svg"
        if not path.exists():
            path.write_text(svg, encoding="utf-8")
        saved[digest] = size
        return f'<svg data-icon="{digest}" data-size="{size}"/>'

    return SVG_RE.sub(repl, code), saved


def make_digest(code: str) -> str:
    """Дерево слоёв: имя, ключевые стили, текст. Без SVG-путей."""
    out = []
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        indent = len(line) - len(line.lstrip())
        out.append(" " * indent + stripped)
    return "\n".join(out) + "\n"


def main() -> None:
    for d in (CLEAN, ICONS, DIGEST):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    icon_usage: dict[str, set[str]] = {}
    report = []

    for src in sorted(SRC.rglob("*.html")):
        rel = src.relative_to(SRC)
        frame = src.stem

        raw = src.read_text(encoding="utf-8", errors="replace")
        code = unwrap(raw)

        # Каталог назначения повторяет исходную структуру папок.
        dest = CLEAN / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(code, encoding="utf-8")

        lean, icons = extract_icons(code, frame)
        for digest in icons:
            icon_usage.setdefault(digest, set()).add(frame)

        dpath = DIGEST / rel.with_suffix(".txt")
        dpath.parent.mkdir(parents=True, exist_ok=True)
        dpath.write_text(make_digest(lean), encoding="utf-8")

        report.append((len(raw), len(code), len(lean), len(icons), str(rel)))

    print(f"{'исходник':>9} {'код':>8} {'дайджест':>9} {'икон':>5}  файл")
    for raw_len, code_len, lean_len, n_icons, name in report:
        print(f"{raw_len:>9} {code_len:>8} {lean_len:>9} {n_icons:>5}  {name}")

    print(f"\nВсего фреймов: {len(report)}")
    print(f"Уникальных SVG: {len(icon_usage)}  →  {ICONS}")


if __name__ == "__main__":
    main()
