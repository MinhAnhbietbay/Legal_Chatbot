"""Small HTTP client with retries and polite delays."""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = "CreditRiskLegalRAG/0.1 (+research crawler; contact: local)"


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    body: str
    final_url: str


class FetchError(RuntimeError):
    """Raised when a page cannot be fetched after retries."""


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

    def fetch(self, url: str) -> FetchResult:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            wait = self.delay_seconds - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            try:
                request = Request(url, headers={"User-Agent": self.user_agent})
                with urlopen(request, timeout=self.timeout) as response:
                    self._last_request_at = time.monotonic()
                    raw = response.read()
                    content_type = response.headers.get("Content-Type", "")
                    charset = response.headers.get_content_charset() or "utf-8"
                    body = raw.decode(charset, errors="replace")
                    return FetchResult(
                        url=url,
                        status=response.status,
                        content_type=content_type,
                        body=body,
                        final_url=response.url,
                    )
            except Exception as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(1 + attempt)
        raise FetchError(f"Cannot fetch {url}: {last_error}")
