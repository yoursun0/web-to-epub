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
