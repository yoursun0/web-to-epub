from __future__ import annotations

import re

import trafilatura

from web_to_epub.epub_build import Chapter

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_BODY_RE = re.compile(r"<body[^>]*>(.*)</body>", re.IGNORECASE | re.DOTALL)


def _as_fragment(html: str) -> str:
    """trafilatura 2.x HTML output is a full document; keep the inner body."""
    match = _BODY_RE.search(html)
    if match:
        return match.group(1).strip()
    return html.strip()


def extract_chapter(html: str, url: str) -> Chapter | None:
    downloaded = html
    body = trafilatura.extract(
        downloaded,
        url=url,
        include_comments=False,
        include_tables=True,
        include_images=False,
        include_links=False,
        output_format="html",
        favor_recall=True,
    )
    if not body or not str(body).strip():
        return None
    body_html = _as_fragment(_IMG_RE.sub("", str(body)))
    if not body_html.strip():
        return None
    meta_title = trafilatura.extract_metadata(downloaded)
    title = None
    if meta_title is not None:
        title = getattr(meta_title, "title", None)
    if not title or not str(title).strip():
        title = url
    else:
        title = str(title).strip()
    return Chapter(title=title, body_html=body_html, source_url=url)
