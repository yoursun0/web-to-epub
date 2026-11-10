from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ebooklib import epub


@dataclass(frozen=True)
class Chapter:
    title: str
    body_html: str
    source_url: str


def _chapter_xhtml(chapter: Chapter, _index: int) -> str:
    # body_html is a fragment; wrap minimally. ebooklib expects unicode str.
    return (
        f"<h1>{_escape(chapter.title)}</h1>\n"
        f"{chapter.body_html}\n"
        f'<p class="source">Source: {_escape(chapter.source_url)}</p>\n'
    )


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_epub(
    chapters: list[Chapter],
    *,
    title: str,
    author: str | None,
    dest: str | Path,
) -> Path:
    if not chapters:
        raise ValueError("build_epub requires at least one chapter")

    dest_path = Path(dest)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    book = epub.EpubBook()
    book.set_title(title)
    book.set_language("zh")
    if author:
        book.add_author(author)

    spine: list[object] = ["nav"]
    toc: list[epub.Link] = []
    for i, chapter in enumerate(chapters, start=1):
        file_name = f"chap_{i:04d}.xhtml"
        item = epub.EpubHtml(title=chapter.title, file_name=file_name, lang="zh")
        item.content = _chapter_xhtml(chapter, i)
        book.add_item(item)
        spine.append(item)
        toc.append(epub.Link(file_name, chapter.title, f"chap_{i:04d}"))

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine

    partial = dest_path.with_suffix(dest_path.suffix + ".partial")
    try:
        epub.write_epub(str(partial), book)
        os.replace(partial, dest_path)
    except Exception:
        if partial.exists():
            partial.unlink(missing_ok=True)
        raise
    return dest_path
