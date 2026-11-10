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
        # argparse uses exit code 2 for usage errors; the CLI contract is 1.
        if exc.code == 0:
            return 0
        return 1

    try:
        urls = load_urls(args.urls_file, warn=lambda m: print(m, file=sys.stderr))
    except (OSError, UnicodeDecodeError) as exc:
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
        print(
            f"no chapters succeeded ({failures} failures); not writing EPUB",
            file=sys.stderr,
        )
        return 1

    dest = Path(args.output)
    try:
        path = build_epub(
            chapters,
            title=args.title,
            author=args.author,
            dest=dest,
        )
    except Exception as exc:  # noqa: BLE001 — assemble/write must exit 1, not crash 2
        print(f"cannot write EPUB: {exc}", file=sys.stderr)
        return 1

    print(path)
    return 0
