"""Small HTTP client with retries, polite delays, and ASP.NET-friendly POST/cookie support."""

from __future__ import annotations

import re
import time
import urllib.parse
from dataclasses import dataclass
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = "CreditRiskLegalRAG/0.1 (+research crawler; contact: local)"


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    body: str
    final_url: str
    set_cookie: str = ""


@dataclass
class _RawResponse:
    body: bytes
    status: int
    content_type: str
    final_url: str
    set_cookie: str


class FetchError(RuntimeError):
    """Raised when a page cannot be fetched after retries."""


def _charset_from_content_type(content_type: str) -> str:
    match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    return match.group(1) if match else "utf-8"


class HttpClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 20,
        delay_seconds: float = 1.0,
        retries: int = 2,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.retries = retries
        self._last_request_at = 0.0

    def _cookie_header(self, headers) -> str:
        parts = [raw.split(";", 1)[0] for raw in (headers.get_all("Set-Cookie") or [])]
        return "; ".join(parts)

    def _request(
        self,
        url: str,
        method: str,
        body: bytes | None = None,
        cookie: str = "",
        extra_headers: dict[str, str] | None = None,
    ) -> _RawResponse:
        headers = {"User-Agent": self.user_agent}
        if cookie:
            headers["Cookie"] = cookie
        if extra_headers:
            headers.update(extra_headers)

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            wait = self.delay_seconds - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            try:
                request = Request(url, data=body, method=method, headers=headers)
                with urlopen(request, timeout=self.timeout) as response:
                    self._last_request_at = time.monotonic()
                    raw = response.read()
                    return _RawResponse(
                        body=raw,
                        status=response.status,
                        content_type=response.headers.get("Content-Type", ""),
                        final_url=response.url,
                        set_cookie=self._cookie_header(response.headers),
                    )
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(1 + attempt)
        raise FetchError(f"Cannot {method} {url}: {last_error}")

    def fetch(self, url: str, cookie: str = "") -> FetchResult:
        raw = self._request(url, "GET", cookie=cookie)
        return self._decode(url, raw)

    def post(self, url: str, data: dict[str, str], cookie: str = "") -> FetchResult:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        raw = self._request(
            url,
            "POST",
            body=encoded,
            cookie=cookie,
            extra_headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return self._decode(url, raw)

    def fetch_bytes(self, url: str) -> bytes:
        return self._request(url, "GET").body

    def _decode(self, url: str, raw: _RawResponse) -> FetchResult:
        charset = _charset_from_content_type(raw.content_type)
        text = raw.body.decode(charset, errors="replace")
        return FetchResult(
            url=url,
            status=raw.status,
            content_type=raw.content_type,
            body=text,
            final_url=raw.final_url,
            set_cookie=raw.set_cookie,
        )
