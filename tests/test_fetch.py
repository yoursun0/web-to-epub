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
