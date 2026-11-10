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
