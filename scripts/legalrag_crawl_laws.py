#!/usr/bin/env python3
"""Crawl Vietnamese legal pages into data/legal/raw JSONL.

Examples:
    python3 scripts/legalrag_crawl_laws.py --max-pages 50 --max-depth 2

    python3 scripts/legalrag_crawl_laws.py \
      --seed-url https://vbpl.vn/ \
      --seed-url https://sbv.gov.vn/ \
      --allowed-domain vbpl.vn \
      --allowed-domain sbv.gov.vn \
      --output data/legal/raw/banking_laws.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.legal_rag.crawler.crawler import LegalWebCrawler
from src.legal_rag.crawler.seeds import (
    BANKING_LAW_KEYWORDS,
    DEFAULT_ALLOWED_DOMAINS,
    DEFAULT_SEED_URLS,
    CrawlConfig,
)


def read_lines(path: str | None) -> tuple[str, ...]:
    if not path:
        return ()
    return tuple(
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-url", action="append", default=[], help="Seed URL to start crawling from")
    parser.add_argument("--seed-file", help="Text file with one seed URL per line")
    parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed domain, e.g. vbpl.vn")
    parser.add_argument("--keyword", action="append", default=[], help="Additional normalized keyword to keep pages")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--min-text-chars", type=int, default=500)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--output", default="data/legal/raw/law_crawl.jsonl")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_urls = tuple(args.seed_url) + read_lines(args.seed_file)
    if not seed_urls:
        seed_urls = DEFAULT_SEED_URLS

    allowed_domains = tuple(args.allowed_domain) or DEFAULT_ALLOWED_DOMAINS
    keywords = BANKING_LAW_KEYWORDS + tuple(args.keyword)

    config = CrawlConfig(
        seed_urls=seed_urls,
        allowed_domains=allowed_domains,
        keywords=keywords,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        min_text_chars=args.min_text_chars,
        delay_seconds=args.delay_seconds,
        output_path=args.output,
    )
    stats = LegalWebCrawler(config).crawl()
    print(f"Visited pages: {stats.visited}")
    print(f"Saved documents: {stats.saved}")
    print(f"Skipped pages: {stats.skipped}")
    print(f"Errors: {stats.errors}")
    print(f"Output: {stats.output_path}")


if __name__ == "__main__":
    main()
