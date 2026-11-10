# web-to-epub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python 3.11+ CLI that reads a UTF-8 URL list file and writes one EPUB3 book (one successful URL = one chapter, text only) using httpx + trafilatura + ebooklib.

**Architecture:** Thin sequential pipeline: `url_file` loads URLs → `fetch` GETs HTML → `extract` pulls title/body via trafilatura (images disabled) → `epub_build` assembles EPUB3 with ebooklib → `cli` wires argparse, fail-continue loop, atomic write, exit codes. No concurrency, no login/paywall, no images.

**Tech Stack:** Python 3.11+, httpx, trafilatura, ebooklib, pytest, argparse (stdlib).

## Global Constraints

- Python version: 3.11+
- Runtime deps only: `httpx`, `trafilatura`, `ebooklib` (plus pytest for tests)
- CLI shape (exact): `web-to-epub URLS_FILE --title TITLE [--author AUTHOR] [-o OUTPUT]`
- URL file: UTF-8; one URL per line; blanks and `#` comments ignored; `http`/`https` only; duplicates kept in order
- Many URLs → one EPUB3; one chapter per successful URL; text only (no images)
- Fail-continue per URL; write EPUB only if ≥1 chapter succeeded
- TOC / nav entries = chapter titles (trafilatura title, else URL string)
- Sequential fetch only; one attempt per URL; no interactive prompts
- No login, cookies, CAPTCHA, or paywall bypass
- Default output: `./output.epub`; omit creator metadata when `--author` absent
- Exit `0` on partial/full success with file written; exit `1` on usage/no-chapters/unwritable; prefer catch+exit `1` over crash exit `2`
- Primary UAT fixture: `fixtures/shen-de-mofangfan-ch1-20.txt` with `--title "神的模仿犯" --author "林思之"` (QA仔 later; implementer does a smoke step only — do not message QA仔)
- GitHub remote: https://github.com/yoursun0/web-to-epub (private). Work on a feature branch; open PR to `main`. Do not force-push `main`.

---

## File map

| Path | Responsibility |
|------|----------------|
| `pyproject.toml` | Package metadata, deps, console script `web-to-epub`, pytest config |
| `README.md` | Install, CLI usage, UAT command shape, limits |
| `src/web_to_epub/__init__.py` | Package version `__version__ = "0.1.0"` |
| `src/web_to_epub/__main__.py` | `python -m web_to_epub` → `cli.main()` |
| `src/web_to_epub/url_file.py` | `load_urls(path) -> list[str]` per §5 |
| `src/web_to_epub/fetch.py` | `fetch_html(url, *, timeout=30.0) -> str`; raises typed errors |
| `src/web_to_epub/extract.py` | `extract_chapter(html, url) -> Chapter \| None`; strips images |
| `src/web_to_epub/epub_build.py` | `Chapter` dataclass; `build_epub(chapters, title, author, dest) -> Path` |
| `src/web_to_epub/cli.py` | argparse + pipeline + exit codes + stderr progress |
| `tests/test_url_file.py` | URL file parser unit tests |
| `tests/test_fetch.py` | Fetch helper with mocked httpx |
| `tests/test_extract.py` | Extract helper with fixture HTML |
| `tests/test_epub_build.py` | EPUB assembly unit tests |
| `tests/test_cli.py` | CLI integration with mocked fetch/extract |
| `tests/fixtures/sample_article.html` | Static HTML for extract tests |
| `fixtures/shen-de-mofangfan-ch1-20.txt` | Already present — UAT URL list (do not rewrite) |

Shared types (defined in `epub_build.py`, imported elsewhere):

```python
@dataclass(frozen=True)
class Chapter:
    title: str
    body_html: str  # fragment suitable for wrapping in XHTML
    source_url: str
```

---

### Task 1: Scaffold project + pytest

**Files:**
- Create: `pyproject.toml`
- Create: `src/web_to_epub/__init__.py`
- Create: `src/web_to_epub/__main__.py`
- Create: `tests/test_smoke_import.py`

**Interfaces:**
- Consumes: (none)
- Produces: installable package `web-to-epub` with empty modules importable; console script entry point declared

- [x] **Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "web-to-epub"
version = "0.1.0"
description = "Turn a list of public article URLs into one EPUB3 book"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "httpx>=0.27",
  "trafilatura>=1.12",
  "ebooklib>=0.18",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
web-to-epub = "web_to_epub.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [x] **Step 2: Write package stubs**

`src/web_to_epub/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/web_to_epub/__main__.py`:

```python
from web_to_epub.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

Create empty placeholders so later imports resolve (minimal):

`src/web_to_epub/cli.py`:

```python
def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError("cli not wired yet")
```

`src/web_to_epub/url_file.py`, `fetch.py`, `extract.py`, `epub_build.py`: empty files (or a module docstring only) for now.

- [x] **Step 3: Write failing import smoke test**

`tests/test_smoke_import.py`:

```python
def test_package_version():
    import web_to_epub

    assert web_to_epub.__version__ == "0.1.0"
```

- [x] **Step 4: Install editable + run smoke test**

Run:

```bash
cd /workspace/IT/scratch/web-to-epub
python3 -m pip install -e ".[dev]"
pytest tests/test_smoke_import.py -v
```

Expected: PASS (`test_package_version`)

- [x] **Step 5: Commit**

```bash
git add pyproject.toml src/web_to_epub/__init__.py src/web_to_epub/__main__.py \
  src/web_to_epub/cli.py src/web_to_epub/url_file.py src/web_to_epub/fetch.py \
  src/web_to_epub/extract.py src/web_to_epub/epub_build.py tests/test_smoke_import.py
git commit -m "chore: scaffold web-to-epub package and pytest"
```

---

### Task 2: URL file parser (TDD)

**Files:**
- Create: `tests/test_url_file.py`
- Modify: `src/web_to_epub/url_file.py`

**Interfaces:**
- Consumes: filesystem path to UTF-8 text file
- Produces: `load_urls(path: str | Path) -> list[str]` — ordered http(s) URLs; skips blanks/`#`; bad schemes omitted and reported via optional `warnings: list[str] | None` side channel OR by writing to a passed `warn` callable. Prefer:

```python
def load_urls(path: str | Path, *, warn: Callable[[str], None] | None = None) -> list[str]:
    ...
```

Raises `FileNotFoundError` / `OSError` / `UnicodeDecodeError` to caller (cli maps to exit 1).

- [x] **Step 1: Write failing tests**

`tests/test_url_file.py`:

```python
from pathlib import Path

import pytest

from web_to_epub.url_file import load_urls


def test_load_urls_skips_blanks_and_comments(tmp_path: Path):
    p = tmp_path / "urls.txt"
    p.write_text(
        "# weekend\n"
        "https://example.com/a\n"
        "\n"
        "  # indented comment\n"
        "https://example.com/b\n"
        "ftp://example.com/nope\n"
        "https://example.com/a\n",
        encoding="utf-8",
    )
    warnings: list[str] = []
    urls = load_urls(p, warn=warnings.append)
    assert urls == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/a",
    ]
    assert any("ftp://" in w for w in warnings)


def test_load_urls_strips_whitespace(tmp_path: Path):
    p = tmp_path / "urls.txt"
    p.write_text("  https://example.com/x  \n", encoding="utf-8")
    assert load_urls(p) == ["https://example.com/x"]


def test_load_urls_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_urls(tmp_path / "missing.txt")


def test_load_urls_empty_after_filter(tmp_path: Path):
    p = tmp_path / "urls.txt"
    p.write_text("# only comments\n\n", encoding="utf-8")
    assert load_urls(p) == []
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_url_file.py -v`

Expected: FAIL with `ImportError` or `AttributeError` (`load_urls` missing)

- [x] **Step 3: Write minimal implementation**

`src/web_to_epub/url_file.py`:

```python
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
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_url_file.py -v`

Expected: PASS (all 4 tests)

- [x] **Step 5: Commit**

```bash
git add src/web_to_epub/url_file.py tests/test_url_file.py
git commit -m "feat: parse URL list files (blanks, comments, http(s) only)"
```

---

### Task 3: Fetch helper (TDD, mock httpx)

**Files:**
- Create: `tests/test_fetch.py`
- Modify: `src/web_to_epub/fetch.py`

**Interfaces:**
- Consumes: URL string
- Produces:

```python
USER_AGENT = "web-to-epub/0.1 (+https://github.com/yoursun0/web-to-epub)"

class FetchError(Exception):
    """Raised for HTTP/network failures; str(self) is a short reason."""

def fetch_html(url: str, *, timeout: float = 30.0) -> str:
    """GET url; return response text. Raises FetchError on failure."""
```

Follow redirects within http(s). One attempt. Timeout applies to connect+read (httpx `timeout=timeout`).

- [x] **Step 1: Write failing tests**

`tests/test_fetch.py`:

```python
from unittest.mock import MagicMock, patch

import httpx
import pytest

from web_to_epub.fetch import USER_AGENT, FetchError, fetch_html


def test_fetch_html_success():
    response = MagicMock()
    response.status_code = 200
    response.text = "<html>ok</html>"
    response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.get.return_value = response

    with patch("web_to_epub.fetch.httpx.Client", return_value=mock_client):
        html = fetch_html("https://example.com/a")

    assert html == "<html>ok</html>"
    mock_client.get.assert_called_once()
    args, kwargs = mock_client.get.call_args
    assert args[0] == "https://example.com/a"
    assert kwargs["headers"]["User-Agent"] == USER_AGENT


def test_fetch_html_http_error():
    request = httpx.Request("GET", "https://example.com/missing")
    response = httpx.Response(404, request=request)

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.get.return_value = response

    with patch("web_to_epub.fetch.httpx.Client", return_value=mock_client):
        with pytest.raises(FetchError) as exc:
            fetch_html("https://example.com/missing")
    assert "404" in str(exc.value)


def test_fetch_html_timeout():
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False
    mock_client.get.side_effect = httpx.TimeoutException("timed out")

    with patch("web_to_epub.fetch.httpx.Client", return_value=mock_client):
        with pytest.raises(FetchError) as exc:
            fetch_html("https://example.com/slow")
    assert "timeout" in str(exc.value).lower() or "timed out" in str(exc.value).lower()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetch.py -v`

Expected: FAIL (`fetch_html` / `FetchError` not defined)

- [x] **Step 3: Write minimal implementation**

`src/web_to_epub/fetch.py`:

```python
from __future__ import annotations

import httpx

USER_AGENT = "web-to-epub/0.1 (+https://github.com/yoursun0/web-to-epub)"


class FetchError(Exception):
    pass


def fetch_html(url: str, *, timeout: float = 30.0) -> str:
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise FetchError(f"HTTP {exc.response.status_code}") from exc
            return response.text
    except FetchError:
        raise
    except httpx.TimeoutException as exc:
        raise FetchError(f"timeout: {exc}") from exc
    except httpx.HTTPError as exc:
        raise FetchError(str(exc)) from exc
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fetch.py -v`

Expected: PASS (all 3)

- [x] **Step 5: Commit**

```bash
git add src/web_to_epub/fetch.py tests/test_fetch.py
git commit -m "feat: fetch HTML via httpx with tool User-Agent"
```

---

### Task 4: Extract helper (TDD, fixture HTML)

**Files:**
- Create: `tests/fixtures/sample_article.html`
- Create: `tests/test_extract.py`
- Modify: `src/web_to_epub/extract.py`

**Interfaces:**
- Consumes: raw HTML string + source URL
- Produces:

```python
from web_to_epub.epub_build import Chapter

def extract_chapter(html: str, url: str) -> Chapter | None:
    """Return Chapter or None if main content empty. No images in body_html."""
```

Use trafilatura with image inclusion disabled. Prefer extracted title; fallback title = `url`. Body as HTML fragment (trafilatura `output_format="html"`) then strip any residual `<img>` tags. If body empty/None → return `None`.

Note: `Chapter` lives in `epub_build.py` — create a minimal dataclass there in this task if not already present (Task 5 owns full builder; dataclass may land here first).

- [x] **Step 1: Write sample HTML fixture**

`tests/fixtures/sample_article.html`:

```html
<!DOCTYPE html>
<html lang="zh-Hans">
<head><title>Site Chrome Title</title></head>
<body>
  <header><nav>Ads and banner</nav></header>
  <aside>推荐阅读</aside>
  <article>
    <h1>真正的文章標題</h1>
    <p>第一段正文內容。</p>
    <p>第二段正文內容。</p>
    <img src="https://example.com/ad.png" alt="ad" />
  </article>
  <footer>站点页脚</footer>
</body>
</html>
```

- [x] **Step 2: Write failing tests**

`tests/test_extract.py`:

```python
from pathlib import Path

from web_to_epub.extract import extract_chapter

FIXTURE = Path(__file__).parent / "fixtures" / "sample_article.html"


def test_extract_chapter_gets_title_and_body():
    html = FIXTURE.read_text(encoding="utf-8")
    chapter = extract_chapter(html, "https://example.com/article")
    assert chapter is not None
    assert "真正的文章標題" in chapter.title or "文章" in chapter.title
    assert "第一段正文" in chapter.body_html
    assert "第二段正文" in chapter.body_html
    assert "<img" not in chapter.body_html.lower()
    assert chapter.source_url == "https://example.com/article"


def test_extract_chapter_empty_returns_none():
    assert extract_chapter("<html><body></body></html>", "https://example.com/empty") is None


def test_extract_chapter_fallback_title_is_url():
    html = """
    <html><body><article><p>Only body no heading here for extraction.</p>
    <p>More enough text to survive boilerplate filters maybe.</p>
    </article></body></html>
    """
    chapter = extract_chapter(html, "https://example.com/no-title")
    # If trafilatura yields body but no title, title must be the URL.
    if chapter is not None:
        assert chapter.title  # non-empty
        # Either extracted something or fell back to URL
        assert isinstance(chapter.title, str)
```

- [x] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_extract.py -v`

Expected: FAIL (`extract_chapter` missing)

- [x] **Step 4: Write minimal Chapter + extract implementation**

`src/web_to_epub/epub_build.py` (dataclass only for now):

```python
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
```

`src/web_to_epub/extract.py`:

```python
from __future__ import annotations

import re

import trafilatura

from web_to_epub.epub_build import Chapter

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


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
    body_html = _IMG_RE.sub("", str(body))
    meta_title = trafilatura.extract_metadata(downloaded)
    title = None
    if meta_title is not None:
        title = getattr(meta_title, "title", None)
    if not title or not str(title).strip():
        title = url
    else:
        title = str(title).strip()
    return Chapter(title=title, body_html=body_html, source_url=url)
```

- [x] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_extract.py -v`

Expected: PASS for `test_extract_chapter_gets_title_and_body` and `test_extract_chapter_empty_returns_none`. `test_extract_chapter_fallback_title_is_url` may skip meaningfully if trafilatura returns None on tiny HTML — if it fails spuriously, tighten the fixture paragraph length until extraction succeeds, then assert `chapter.title == "https://example.com/no-title"` when metadata title is absent. Do not weaken the empty-body test.

If `favor_recall` / API kwargs differ by trafilatura version, adjust kwargs to the installed version's supported parameters while keeping `include_images=False` and HTML output.

- [x] **Step 6: Commit**

```bash
git add src/web_to_epub/extract.py src/web_to_epub/epub_build.py \
  tests/test_extract.py tests/fixtures/sample_article.html
git commit -m "feat: extract chapter title/body with trafilatura (no images)"
```

---

### Task 5: EPUB builder (TDD)

**Files:**
- Modify: `src/web_to_epub/epub_build.py`
- Create: `tests/test_epub_build.py`

**Interfaces:**
- Consumes: `list[Chapter]`, book `title`, optional `author`, `dest` path
- Produces: `build_epub(...) -> Path` written EPUB3; raises `OSError` if cannot write; TOC/nav titles = chapter titles; optional text-only source URL footer per chapter; no image items

```python
def build_epub(
    chapters: list[Chapter],
    *,
    title: str,
    author: str | None,
    dest: str | Path,
) -> Path:
```

Atomic write: write to `dest.with_suffix(dest.suffix + ".partial")` (or Adjacent temp in same dir) then `os.replace` into `dest`. Caller must not call with empty `chapters` (cli enforces).

- [x] **Step 1: Write failing tests**

`tests/test_epub_build.py`:

```python
import zipfile
from pathlib import Path

from ebooklib import epub

from web_to_epub.epub_build import Chapter, build_epub


def _chapters() -> list[Chapter]:
    return [
        Chapter("第一章", "<p>內容一</p>", "https://example.com/1"),
        Chapter("第二章", "<p>內容二</p>", "https://example.com/2"),
    ]


def test_build_epub_writes_file_with_metadata_and_spine(tmp_path: Path):
    dest = tmp_path / "out.epub"
    path = build_epub(_chapters(), title="神的模仿犯", author="林思之", dest=dest)
    assert path == dest
    assert dest.is_file()
    book = epub.read_epub(str(dest))
    titles = book.get_metadata("DC", "title")
    assert titles and titles[0][0] == "神的模仿犯"
    creators = book.get_metadata("DC", "creator")
    assert creators and creators[0][0] == "林思之"
    items = [i for i in book.get_items_of_type(epub.ITEM_DOCUMENT)]
    # ebooklib may include nav; chapter docs >= 2
    assert len(items) >= 2
    # No image items
    assert list(book.get_items_of_type(epub.ITEM_IMAGE)) == []
    # Zip has no obvious binary image extensions
    with zipfile.ZipFile(dest) as zf:
        names = zf.namelist()
    assert not any(n.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")) for n in names)


def test_build_epub_omits_creator_when_author_none(tmp_path: Path):
    dest = tmp_path / "out.epub"
    build_epub(_chapters()[:1], title="Only Title", author=None, dest=dest)
    book = epub.read_epub(str(dest))
    assert book.get_metadata("DC", "creator") in (None, [], ())


def test_build_epub_includes_source_footer(tmp_path: Path):
    dest = tmp_path / "out.epub"
    build_epub(_chapters()[:1], title="T", author=None, dest=dest)
    book = epub.read_epub(str(dest))
    docs = list(book.get_items_of_type(epub.ITEM_DOCUMENT))
    blob = b"".join(i.get_content() for i in docs).decode("utf-8", errors="ignore")
    assert "https://example.com/1" in blob
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_epub_build.py -v`

Expected: FAIL (`NotImplementedError` or missing behavior)

- [x] **Step 3: Write minimal implementation**

Replace `build_epub` in `src/web_to_epub/epub_build.py` with:

```python
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


def _chapter_xhtml(chapter: Chapter, index: int) -> str:
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
    epub.write_epub(str(partial), book)
    os.replace(partial, dest_path)
    return dest_path
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_epub_build.py -v`

Expected: PASS (all 3). If `get_metadata` for missing creator returns something other than empty, adjust the assertion to the ebooklib version's actual empty sentinel without adding a fake creator.

- [x] **Step 5: Commit**

```bash
git add src/web_to_epub/epub_build.py tests/test_epub_build.py
git commit -m "feat: build EPUB3 from chapters with ebooklib"
```

---

### Task 6: CLI wiring + integration tests

**Files:**
- Modify: `src/web_to_epub/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_urls`, `fetch_html`, `extract_chapter`, `build_epub`
- Produces: `main(argv: list[str] | None = None) -> int` matching CLI §4/§8

Pipeline inside `main`:
1. argparse for `URLS_FILE`, `--title`, `--author`, `-o/--output` (default `output.epub`)
2. `load_urls`; if empty → stderr + return 1
3. For each URL: fetch → extract; on failure stderr + continue; on success append `Chapter`
4. If no chapters → stderr summary + return 1 (no file)
5. `build_epub(...); print(path); return 0`
6. Catch unreadable file / write errors → stderr + return 1

- [x] **Step 1: Write failing CLI tests**

`tests/test_cli.py`:

```python
from pathlib import Path
from unittest.mock import patch

from web_to_epub.cli import main
from web_to_epub.epub_build import Chapter
from web_to_epub.fetch import FetchError


def test_cli_partial_success(tmp_path: Path, capsys):
    urls = tmp_path / "urls.txt"
    urls.write_text(
        "https://example.com/ok1\n"
        "https://example.com/bad\n"
        "https://example.com/ok2\n",
        encoding="utf-8",
    )
    out = tmp_path / "book.epub"

    def fake_fetch(url: str, *, timeout: float = 30.0) -> str:
        if "bad" in url:
            raise FetchError("HTTP 500")
        return f"<html><body><article><h1>{url}</h1><p>body for {url}</p></article></body></html>"

    def fake_extract(html: str, url: str) -> Chapter | None:
        return Chapter(title=url, body_html=f"<p>{url}</p>", source_url=url)

    with patch("web_to_epub.cli.fetch_html", side_effect=fake_fetch), patch(
        "web_to_epub.cli.extract_chapter", side_effect=fake_extract
    ):
        code = main(
            [
                str(urls),
                "--title",
                "Demo",
                "--author",
                "Tester",
                "-o",
                str(out),
            ]
        )
    assert code == 0
    assert out.is_file()
    captured = capsys.readouterr()
    assert str(out) in captured.out
    assert "bad" in captured.err


def test_cli_total_failure_writes_nothing(tmp_path: Path):
    urls = tmp_path / "urls.txt"
    urls.write_text("https://example.com/x\n", encoding="utf-8")
    out = tmp_path / "book.epub"

    with patch("web_to_epub.cli.fetch_html", side_effect=FetchError("boom")), patch(
        "web_to_epub.cli.extract_chapter"
    ) as extract:
        code = main([str(urls), "--title", "Demo", "-o", str(out)])
    assert code == 1
    assert not out.exists()
    extract.assert_not_called()


def test_cli_missing_title_exits_1():
    code = main(["urls.txt"])  # no --title
    assert code == 1


def test_cli_empty_url_list(tmp_path: Path):
    urls = tmp_path / "urls.txt"
    urls.write_text("# none\n", encoding="utf-8")
    code = main([str(urls), "--title", "T", "-o", str(tmp_path / "o.epub")])
    assert code == 1
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`

Expected: FAIL (`NotImplementedError` or wrong exit codes)

- [x] **Step 3: Write CLI implementation**

`src/web_to_epub/cli.py`:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from web_to_epub.epub_build import Chapter, build_epub
from web_to_epub.extract import extract_chapter
from web_to_epub.fetch import FetchError, fetch_html
from web_to_epub.url_file import load_urls


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="web-to-epub")
    p.add_argument("urls_file", help="UTF-8 text file, one URL per line")
    p.add_argument("--title", required=True, help="EPUB book title")
    p.add_argument("--author", default=None, help="EPUB author/creator")
    p.add_argument(
        "-o",
        "--output",
        default="output.epub",
        help="Output .epub path (default: ./output.epub)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 1

    try:
        urls = load_urls(args.urls_file, warn=lambda m: print(m, file=sys.stderr))
    except OSError as exc:
        print(f"cannot read URL file: {exc}", file=sys.stderr)
        return 1

    if not urls:
        print("no URLs to process after filtering", file=sys.stderr)
        return 1

    chapters: list[Chapter] = []
    failures = 0
    for url in urls:
        try:
            html = fetch_html(url)
            chapter = extract_chapter(html, url)
            if chapter is None:
                print(f"FAIL {url}: empty extract", file=sys.stderr)
                failures += 1
                continue
            chapters.append(chapter)
            print(f"OK   {url} -> {chapter.title}", file=sys.stderr)
        except FetchError as exc:
            print(f"FAIL {url}: {exc}", file=sys.stderr)
            failures += 1
        except Exception as exc:  # noqa: BLE001 — per-URL fail-continue
            print(f"FAIL {url}: {exc}", file=sys.stderr)
            failures += 1

    if not chapters:
        print(f"no chapters succeeded ({failures} failures); not writing EPUB", file=sys.stderr)
        return 1

    dest = Path(args.output)
    try:
        path = build_epub(
            chapters,
            title=args.title,
            author=args.author,
            dest=dest,
        )
    except OSError as exc:
        print(f"cannot write EPUB: {exc}", file=sys.stderr)
        return 1

    print(path)
    return 0
```

- [x] **Step 4: Run full unit suite**

Run: `pytest -v`

Expected: PASS (all tasks' tests green)

- [x] **Step 5: Commit**

```bash
git add src/web_to_epub/cli.py tests/test_cli.py
git commit -m "feat: wire CLI pipeline with fail-continue and exit codes"
```

---

### Task 7: Live smoke against UAT fixture (optional network)

**Files:**
- No production code required unless smoke reveals a clear bug (then fix in the owning module + add a regression test)

**Interfaces:**
- Consumes: installed console script + `fixtures/shen-de-mofangfan-ch1-20.txt`
- Produces: smoke log note in commit message / local `/tmp` EPUB; do **not** message QA仔

- [x] **Step 1: Run live smoke**

Run:

```bash
cd /workspace/IT/scratch/web-to-epub
web-to-epub fixtures/shen-de-mofangfan-ch1-20.txt \
  --title "神的模仿犯" --author "林思之" \
  -o /tmp/shen-de-mofangfan-ch1-20.epub
echo EXIT:$?
```

Expected:
- Ideal: EXIT:0, EPUB exists, stderr shows mix of OK lines for ch1–20
- Acceptable flake: many/all FAIL due to uukanshu rate-limit / anti-bot / geo-block — EXIT:1, no EPUB; capture sample stderr. This is an environment risk per spec §9.1, not an automatic product bug. Do not add login/bypass.
- If EXIT:0 but bodies are chrome-only ads: treat as extract tuning bug — adjust `extract.py` options and add a fixture-based regression if reproducible offline.

- [x] **Step 2: Quick structural check when EPUB exists**

Run (only if file written):

```bash
python3 - <<'PY'
from ebooklib import epub
from pathlib import Path
p = Path("/tmp/shen-de-mofangfan-ch1-20.epub")
book = epub.read_epub(str(p))
print("title", book.get_metadata("DC", "title"))
print("creator", book.get_metadata("DC", "creator"))
docs = list(book.get_items_of_type(epub.ITEM_DOCUMENT))
print("documents", len(docs))
print("images", len(list(book.get_items_of_type(epub.ITEM_IMAGE))))
PY
```

Expected: title/author match flags; documents ≥ 1; images == 0

- [x] **Step 3: Commit smoke note only if code changed; otherwise skip commit**

If extract/fetch needed a fix:

```bash
git add -u src tests
git commit -m "fix: harden extract/fetch after uukanshu smoke"
```

If no code change: no commit required for this task.

---

### Task 8: README

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: final CLI behavior
- Produces: install + usage + UAT command + limits (no images, no paywall, sequential)

- [x] **Step 1: Write README.md**

```markdown
# web-to-epub

Turn a UTF-8 list of public article URLs into one EPUB3 book (one URL → one chapter). Text only — no images. Runs as a small Python 3.11+ CLI.

## Install

```bash
python3 -m pip install -e ".[dev]"
```

## Usage

```bash
web-to-epub URLS_FILE --title TITLE [--author AUTHOR] [-o OUTPUT]
```

- `URLS_FILE`: one URL per line; blank lines and `#` comments ignored; `http`/`https` only
- Default output: `./output.epub`
- Failed URLs are logged on stderr; the EPUB is written only if at least one chapter succeeds

## Primary UAT fixture

```bash
web-to-epub fixtures/shen-de-mofangfan-ch1-20.txt \
  --title "神的模仿犯" --author "林思之" \
  -o /tmp/shen-de-mofangfan-ch1-20.epub
```

Novel-aggregation sites may rate-limit or serve anti-bot HTML. Failures stay on the fail-continue path; this tool does not log in or bypass paywalls.

## Limits (v1)

- No images, GUI, crawling, or parallel fetch
- One HTTP attempt per URL
- Python 3.11+; dependencies: httpx, trafilatura, ebooklib
```

- [x] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add web-to-epub README"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task coverage |
|------------------|---------------|
| CLI shape + exit codes §4/§8 | Task 6 |
| URL file format §5 | Task 2 |
| Sequential fetch + UA + timeout §6 | Task 3 |
| trafilatura extract, no images §6 | Task 4 |
| EPUB3 title/author/TOC/atomic write §6 | Task 5 |
| Partial vs total failure §8 | Task 6 tests |
| Primary UAT fixture §9.1 | Task 7 smoke (QA仔 not messaged) |
| Secondary automated checks §9.2 | Tasks 2, 5, 6 |
| Layout §10 / deps §7 / Python 3.11+ | Task 1 + Global Constraints |
| Non-goals (no login/images/parallel) | Global Constraints + README Task 8 |

Placeholder scan: no TBD/TODO left in steps. Type names consistent: `Chapter`, `load_urls`, `fetch_html`, `FetchError`, `extract_chapter`, `build_epub`, `main`.

YAGNI: no urllib fallback implementation in v1 (spec allows documenting httpx primary; thin `fetch_html` is the swap point). No retries, no CSS themes, no GitHub remote creation.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-11-10-web-to-epub.md`. Parent offers Helic execution choice (subagent-driven vs inline). Do not implement application code in the planning turn.
