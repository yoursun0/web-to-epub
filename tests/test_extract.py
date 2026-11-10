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
    # Trafilatura yields a body and no metadata title, so the title is the URL.
    assert chapter is not None
    assert chapter.title == "https://example.com/no-title"
