from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chapter:
    title: str
    body_html: str
    source_url: str


def build_epub(
    chapters: list[Chapter],
    *,
    title: str,
    author: str | None,
    dest: str | Path,
) -> Path:
    raise NotImplementedError("build_epub not implemented yet")
