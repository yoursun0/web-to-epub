from __future__ import annotations

import httpx

USER_AGENT = "web-to-epub/0.1 (+https://github.com/yoursun0/web-to-epub)"


class FetchError(Exception):
    """Raised for HTTP/network failures; str(self) is a short reason."""


def fetch_html(url: str, *, timeout: float = 30.0) -> str:
    """GET url; return response text. Raises FetchError on failure."""
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url, headers=headers)
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
