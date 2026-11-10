from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse


def load_urls(
    path: str | Path,
    *,
    warn: Callable[[str], None] | None = None,
) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    urls: list[str] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parsed = urlparse(line)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            if warn is not None:
                warn(f"line {lineno}: skip unsupported URL: {line}")
            continue
        urls.append(line)
    return urls
