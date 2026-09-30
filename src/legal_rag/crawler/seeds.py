"""Crawler seed and filtering defaults."""

from __future__ import annotations

from dataclasses import dataclass


BANKING_LAW_KEYWORDS = (
    "tin dung",
    "cho vay",
    "ngan hang",
    "lai suat",
    "bao dam tien vay",
    "the chap",
    "cam co",
    "phan loai no",
    "trich lap du phong",
    "to chuc tin dung",
    "kha nang tra no",
    "han muc tin dung",
    "thong tu 39/2016",
    "thong tu 02/2013",
    "thong tu 11/2021",
    "luat cac to chuc tin dung",
)

DEFAULT_ALLOWED_DOMAINS = (
    "vbpl.vn",
    "vanban.chinhphu.vn",
    "thuvienphapluat.vn",
    "sbv.gov.vn",
    "www.sbv.gov.vn",
    "phapdien.moj.gov.vn",
)

DEFAULT_SEED_URLS = (
    "https://vbpl.vn/",
    "https://vanban.chinhphu.vn/",
    "https://sbv.gov.vn/",
    "https://phapdien.moj.gov.vn/",
)


@dataclass(frozen=True)
class CrawlConfig:
    seed_urls: tuple[str, ...] = DEFAULT_SEED_URLS
    allowed_domains: tuple[str, ...] = DEFAULT_ALLOWED_DOMAINS
    keywords: tuple[str, ...] = BANKING_LAW_KEYWORDS
    max_pages: int = 100
    max_depth: int = 2
    min_text_chars: int = 500
    delay_seconds: float = 1.0
    output_path: str = "data/legal/raw/law_crawl.jsonl"
