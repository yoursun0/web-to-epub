import zipfile
from pathlib import Path

import ebooklib
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
    items = [i for i in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
    # ebooklib may include nav; chapter docs >= 2
    assert len(items) >= 2
    # No image items
    assert list(book.get_items_of_type(ebooklib.ITEM_IMAGE)) == []
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
    docs = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    blob = b"".join(i.get_content() for i in docs).decode("utf-8", errors="ignore")
    assert "https://example.com/1" in blob


def test_build_epub_cleans_partial_on_write_failure(tmp_path: Path, monkeypatch):
    from web_to_epub import epub_build as mod
    from web_to_epub.epub_build import Chapter, build_epub

    chapters = [
        Chapter(title="One", body_html="<p>a</p>", source_url="https://example.com/1"),
    ]
    dest = tmp_path / "out.epub"
    partial = dest.with_suffix(dest.suffix + ".partial")

    def boom(path, book, **kwargs):
        Path(path).write_bytes(b"partial-junk")
        raise OSError("disk full")

    monkeypatch.setattr(mod.epub, "write_epub", boom)
    try:
        build_epub(chapters, title="T", author=None, dest=dest)
        assert False, "expected OSError"
    except OSError:
        pass
    assert not partial.exists()
    assert not dest.exists()
