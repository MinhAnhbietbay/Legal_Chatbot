#!/usr/bin/env python3
"""Crawl vanban.chinhphu.vn banking/credit-law documents via ASP.NET postback pagination.

Unlike scripts/legalrag_crawl_laws.py (generic BFS crawler for other
domains), this walks the real GridView pagination on vanban.chinhphu.vn and
extracts text from PDF attachments. See
docs/specs/2026-08-19-legal-crawler-rewrite-design.md for why.
Crawler fetches each detail page to compute content hashes to detect server-side
modifications (trade-off: uses more HTTP requests, paced by delay_seconds).

Examples:
    python3 scripts/legalrag_crawl_chinhphu.py --max-pages 3
    python3 scripts/legalrag_crawl_chinhphu.py --categories 24 --years 2025 --max-pages 3
    python3 scripts/legalrag_crawl_chinhphu.py --categories 24 --records-per-page 500 --output data/legal/raw/chinhphu_banking.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.legal_rag.crawler.chinhphu_crawler import ChinhphuCrawler, ChinhphuCrawlConfig
from src.legal_rag.crawler.seeds import BANKING_LAW_KEYWORDS

# URL cũ '?classid=2&mode=1&orggroupid=6' chỉ trả về văn bản UBND tỉnh (E1).
# Cách lọc đúng là dùng URL gốc he-thong-van-ban, lọc server-side bằng drdDocCategory=24
# và records_per_page=500 để hiện pager (E2).
# Bộ lọc từ khoá BANKING_LAW_KEYWORDS mặc định tắt khi lọc danh mục (E6) để tránh loại nhầm
# các thông tư NHNN về ngoại hối, nhưng vẫn cho bật qua cờ --keyword-filter.
DEFAULT_BASE_URL = "https://vanban.chinhphu.vn/he-thong-van-ban"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="URL gốc he-thong-van-ban")
    parser.add_argument("--categories", default="24", help="Mã danh mục phân tách bằng dấu phẩy (mặc định: 24 = Tài chính - Ngân hàng; 0 = tất cả)")
    parser.add_argument(
        "--years",
        default="2020,2021,2022,2023,2024,2025,2026",
        help=(
            "Năm ban hành phân tách bằng dấu phẩy. Mặc định 2020-2026 (quyết định 2026-10-01). "
            "Đặt rỗng ('--years \"\"') = một lượt cho tất cả các năm — KHÔNG khuyến nghị vì có thể "
            "chạm trần 500 kết quả của site và bị cắt im lặng (E7)."
        ),
    )
    parser.add_argument("--records-per-page", default="500", help="Số bản ghi trên trang postback (mặc định 500 để hiện pager)")
    parser.add_argument("--keyword-filter", action="store_true", help="Bật lọc từ khoá BANKING_LAW_KEYWORDS (mặc định tắt khi có categories)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max GridView pages to walk per category/search")
    parser.add_argument("--min-text-chars", type=int, default=500)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--output", default="data/legal/raw/chinhphu_crawl.jsonl")
    parser.add_argument("--force-refresh", action="store_true", help="Bỏ qua state đã lưu, crawl lại tất cả văn bản")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    categories = tuple(c.strip() for c in args.categories.split(",") if c.strip())
    years = tuple(y.strip() for y in args.years.split(",") if y.strip())
    keywords = BANKING_LAW_KEYWORDS if args.keyword_filter else ()
    config = ChinhphuCrawlConfig(
        base_url=args.base_url,
        categories=categories,
        years=years,
        records_per_page=args.records_per_page,
        keywords=keywords,
        max_pages_per_listing=args.max_pages,
        min_text_chars=args.min_text_chars,
        delay_seconds=args.delay_seconds,
        output_path=args.output,
        force_refresh=args.force_refresh,
    )
    crawler = ChinhphuCrawler(config)
    stats = crawler.crawl()
    print(f"Visited pages: {stats.visited}")
    print(f"Saved documents: {stats.saved}")
    print(f"Updated documents: {crawler.updated}")
    print(f"Skipped pages: {stats.skipped}")
    print(f"Errors: {stats.errors}")
    print(f"Empty listing pages: {crawler.empty_listing_pages}")
    print(f"Output: {stats.output_path}")


if __name__ == "__main__":
    main()
