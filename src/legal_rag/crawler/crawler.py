"""Polite legal web crawler that exports normalized JSONL documents."""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urldefrag, urlparse

from src.legal_rag.corpus_filter import normalize_vietnamese
from src.legal_rag.crawler.html_parser import parse_html
from src.legal_rag.crawler.http_client import FetchError, HttpClient
from src.legal_rag.crawler.seeds import CrawlConfig
from src.legal_rag.documents import LegalDocument


# Per-domain path patterns for URLs that are worth queuing.
# A URL must match at least one pattern for its domain to enter the crawl queue.
# This prevents crawling news, forums, job listings, etc.
DOMAIN_URL_ALLOWLIST: dict[str, list[str]] = {
    "vanban.chinhphu.vn": [
        r"pageid=",      # document page: ?pageid=27160&docid=...
        r"classid=",     # category listing
        r"orggroupid=",  # org-filtered listing
    ],
    "vbpl.vn": [
        r"/Pages/vbpq",  # vbpl document/listing pages
        r"/Pages/van-ban",
        r"dvid=",
    ],
    "thuvienphapluat.vn": [
        r"/van-ban/[^/]+-\d+\.aspx",   # actual document: /van-ban/X-Y-123456.aspx
        r"/van-ban/[a-z\-]+$",          # category listing: /van-ban/tien-te-ngan-hang
    ],
    "www.sbv.gov.vn": [
        r"/webcenter/portal/vi/menu/trangchu/vbpq",
        r"/webcenter/portal/vi/menu/cm",
    ],
    "sbv.gov.vn": [
        r"/webcenter/portal/vi/menu/trangchu/vbpq",
    ],
}

# Fallback hints for domains not in the allowlist above
DOCUMENT_HINTS = (
    "vbpq",
    "toanvan",
    "docid",
    "itemid",
    "thong-tu",
    "nghi-dinh",
    "quyet-dinh",
)


@dataclass(frozen=True)
class CrawlStats:
    visited: int
    saved: int
    skipped: int
    errors: int
    output_path: str


def clean_url(url: str) -> str:
    url, _fragment = urldefrag(url)
    return url.strip()


def is_http_url(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}


def domain_allowed(url: str, allowed_domains: tuple[str, ...]) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == domain or host.endswith("." + domain) for domain in allowed_domains)


def looks_like_document_url(url: str) -> bool:
    normalized = normalize_vietnamese(url)
    return any(hint in normalized for hint in DOCUMENT_HINTS)


def is_queueable_url(url: str) -> bool:
    """Return True if this URL is worth crawling (legal doc or legal category page).
    
    Uses per-domain path allowlists to prevent following news/forum/job links.
    Falls back to DOCUMENT_HINTS for unlisted domains.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower().lstrip("www.")
    full_url = url

    for domain, patterns in DOMAIN_URL_ALLOWLIST.items():
        if host == domain or host == domain.lstrip("www."):
            return any(re.search(p, full_url) for p in patterns)

    # Fallback for unlisted domains
    return looks_like_document_url(url)


def has_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    normalized = normalize_vietnamese(text)
    return any(keyword in normalized for keyword in keywords)


def infer_doc_type(title: str, url: str) -> str:
    text = normalize_vietnamese(f"{title} {url}")
    for label, doc_type in (
        ("thong tu", "Thong tu"),
        ("nghi dinh", "Nghi dinh"),
        ("quyet dinh", "Quyet dinh"),
        ("luat", "Luat"),
    ):
        if label in text:
            return doc_type
    return ""


def infer_doc_id(url: str) -> str:
    parsed = urlparse(url)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", parsed.path.strip("/"))[:80].strip("-")
    query = re.sub(r"[^a-zA-Z0-9]+", "-", parsed.query)[:60].strip("-")
    value = "-".join(part for part in (parsed.netloc, slug, query) if part)
    return value or parsed.netloc


class LegalWebCrawler:
    def __init__(self, config: CrawlConfig, client: HttpClient | None = None) -> None:
        self.config = config
        self.client = client or HttpClient(delay_seconds=config.delay_seconds)

    def crawl(self) -> CrawlStats:
        queue: deque[tuple[str, int]] = deque((clean_url(url), 0) for url in self.config.seed_urls)
        seen: set[str] = set()
        saved_urls: set[str] = set()
        output = Path(self.config.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        visited = saved = skipped = errors = 0
        
        if output.exists():
            with output.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        doc = json.loads(line)
                        old_url = doc.get("source_url")
                        if old_url:
                            saved_urls.add(old_url)
                            seen.add(old_url)
                    except Exception:
                        pass
            saved = len(saved_urls)

        with output.open("a", encoding="utf-8") as f:
            while queue and visited < self.config.max_pages:
                url, depth = queue.popleft()
                url = clean_url(url)
                if not url or url in seen or not is_http_url(url):
                    continue
                seen.add(url)
                if not domain_allowed(url, self.config.allowed_domains):
                    skipped += 1
                    continue

                try:
                    result = self.client.fetch(url)
                except FetchError:
                    errors += 1
                    continue

                visited += 1
                print(f"Visited: {visited} | Saved: {saved} | Errors: {errors} | Queue: {len(queue)} | URL: {url}", flush=True)
                if "html" not in result.content_type.lower():
                    skipped += 1
                    continue

                parser = parse_html(result.body, result.final_url)
                title = parser.title or result.final_url
                content = parser.text
                page_blob = f"{title}\n{content}\n{result.final_url}"

                if depth < self.config.max_depth:
                    for link in parser.links:
                        link = clean_url(link)
                        if (
                            link not in seen
                            and is_http_url(link)
                            and domain_allowed(link, self.config.allowed_domains)
                            and is_queueable_url(link)
                        ):
                            queue.append((link, depth + 1))

                should_save = (
                    len(content) >= self.config.min_text_chars
                    and has_keyword(page_blob, self.config.keywords)
                    and (looks_like_document_url(result.final_url) or has_keyword(title, self.config.keywords))
                )
                if not should_save or result.final_url in saved_urls:
                    skipped += 1
                    continue

                saved_urls.add(result.final_url)
                doc = LegalDocument(
                    doc_id=infer_doc_id(result.final_url),
                    title=title,
                    content=content,
                    issuer=parser.meta.get("author", ""),
                    doc_type=infer_doc_type(title, result.final_url),
                    issued_date=parser.meta.get("article:published_time", ""),
                    source_url=result.final_url,
                    source_system="legal-web-crawler",
                    metadata={
                        "content_type": result.content_type,
                        "crawl_depth": depth,
                    },
                )
                f.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")
                saved += 1

        return CrawlStats(
            visited=visited,
            saved=saved,
            skipped=skipped,
            errors=errors,
            output_path=str(output),
        )
