"""Crawls vanban.chinhphu.vn banking/credit-law documents into LegalDocument JSONL.

Walks each configured listing URL's full ASP.NET GridView pagination
(AspNetGridPaginator), reads structured metadata off each document's detail
page (chinhphu_parser), downloads and extracts its primary PDF attachment
(pdf_extract) since that's where the actual legal text lives, and applies
the existing banking-keyword filter before saving.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.legal_rag.crawler.chinhphu_parser import (
    parse_category_names,
    parse_detail_page,
    parse_listing_rows,
    select_primary_pdf_url,
)
from src.legal_rag.crawler.crawler import CrawlStats, has_keyword
from src.legal_rag.crawler.http_client import FetchError, HttpClient
from src.legal_rag.crawler.paginator import AspNetGridPaginator
from src.legal_rag.crawler.pdf_extract import extract_pdf_text
from src.legal_rag.crawler.seeds import BANKING_LAW_KEYWORDS
from src.legal_rag.crawler.state import compute_content_hash, load_seen, save_seen
from src.legal_rag.documents import LegalDocument

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChinhphuCrawlConfig:
    base_url: str = "https://vanban.chinhphu.vn/he-thong-van-ban"
    categories: tuple[str, ...] = ("24",)
    # Quyết định người dùng 2026-10-01: mặc định CHIA THEO NĂM, không để rỗng.
    # Lý do (E7): một lượt không chia năm sẽ cộng dồn mọi năm của danh mục và có thể
    # vượt trần 500 kết quả của site rồi bị cắt im lặng. Chia năm khiến mỗi lượt chỉ
    # 33-115 văn bản (số đo thật danh mục 24: 2023=33, 2024=40, 2025=48, 2026=115).
    years: tuple[str, ...] = ("2020", "2021", "2022", "2023", "2024", "2025", "2026")
    records_per_page: str = "500"
    seed_keywords: tuple[str, ...] = (
        "39/2016/TT-NHNN",
        "02/2013/TT-NHNN",
        "11/2021/TT-NHNN",
        "47/2010/QH12",
        "Luật Các tổ chức tín dụng",
    )
    keywords: tuple[str, ...] = ()  # Mặc định tắt lọc từ khoá khi có categories; bật qua --keyword-filter (E6)
    min_text_chars: int = 500
    max_pages_per_listing: int = 50
    output_path: str = "data/legal/raw/chinhphu_crawl.jsonl"
    delay_seconds: float = 1.0
    force_refresh: bool = False


def _slugify(doc_number: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", doc_number).strip("-")


def _issued_year(issued_date: str) -> str:
    """Suy năm từ ngày ban hành dạng dd/mm/yyyy (dùng cho lượt seed không lọc theo năm).

    Trả về "" nếu không tìm được năm 4 chữ số — metadata để rỗng, không được crash.
    """
    match = re.search(r"\b(\d{4})\b", issued_date or "")
    return match.group(1) if match else ""


class ChinhphuCrawler:
    def __init__(self, config: ChinhphuCrawlConfig, client: HttpClient | None = None) -> None:
        self.config = config
        self.client = client or HttpClient(delay_seconds=config.delay_seconds)
        self.updated = 0
        self.empty_listing_pages = 0

    def crawl(self) -> CrawlStats:
        output = Path(self.config.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        state_path = output.parent / f"{output.name}.state.json"
        seen = {} if self.config.force_refresh else load_seen(state_path)

        visited = saved = skipped = errors = 0
        updated = 0
        empty_pdf_count = 0
        empty_listing_pages = 0

        # Mỗi batch mang theo nhãn (category, year) của chính lượt tìm kiếm đó, để ghi vào
        # metadata từng văn bản. Lượt seed_keywords không lọc danh mục nên nhãn rỗng; khi đó
        # `year` được suy từ meta.issued_date (xem _issued_year bên dưới).
        search_batches: list[tuple[str, str, dict[str, str]]] = []
        for cat in self.config.categories:
            if self.config.years:
                for year in self.config.years:
                    overrides = {
                        "drdDocCategory": cat,
                        "drdRecordPerPage": self.config.records_per_page,
                        "btnSearch": "Tìm kiếm",
                        "drdDocYear": year,
                    }
                    search_batches.append((cat, year, overrides))
            else:
                overrides = {
                    "drdDocCategory": cat,
                    "drdRecordPerPage": self.config.records_per_page,
                    "btnSearch": "Tìm kiếm",
                }
                search_batches.append((cat, "", overrides))

        for kw in self.config.seed_keywords:
            search_batches.append(("", "", {
                "txtSearchKeyword": kw,
                "drdRecordPerPage": self.config.records_per_page,
                "btnSearch": "Tìm kiếm",
            }))

        seen_in_run: set[str] = set()

        category_names: dict[str, str] = {}

        with output.open("a", encoding="utf-8") as f:
            for batch_category, batch_year, overrides in search_batches:
                paginator = AspNetGridPaginator(self.client, self.config.base_url, search_overrides=overrides)
                pages_seen = 0
                batch_docs = 0
                # Spec mục 5: postback thất bại (HTTP lỗi, v.v.) -> dừng phân trang CHO LƯỢT
                # NÀY, log rõ lý do, tiếp tục lượt tiếp theo KHÔNG crash toàn bộ crawl. Review
                # 2026-10-01: bản gốc dùng thẳng `for page_html in paginator.pages():` không
                # bắt FetchError, nên một lỗi mạng giữa chừng sẽ làm crash() cả lệnh gọi — dùng
                # vòng lặp next() thủ công để bắt lỗi ngay tại điểm phân trang có thể hỏng.
                page_iter = paginator.pages()
                pagination_error = False
                while True:
                    try:
                        page_html = next(page_iter)
                    except StopIteration:
                        break
                    except FetchError as exc:
                        logger.warning(
                            "Lỗi mạng khi phân trang cho lượt tìm kiếm %s ở trang %d: %s. "
                            "Dừng lượt này, tiếp tục lượt tiếp theo.",
                            overrides,
                            pages_seen + 1,
                            exc,
                        )
                        pagination_error = True
                        break
                    pages_seen += 1
                    if not category_names:
                        # Tên lĩnh vực đọc một lần từ <select drdDocCategory> của trang listing
                        # (fixture test tối giản không có select → {} và tên lĩnh vực để rỗng).
                        category_names = parse_category_names(page_html)
                    if pages_seen > self.config.max_pages_per_listing:
                        break
                    rows = parse_listing_rows(page_html)
                    if pages_seen > 1 and len(rows) == 0:
                        empty_listing_pages += 1
                        logger.warning(
                            "Listing trang %d của overrides %s trả về 0 văn bản (có thể do lỗi phân trang/thiếu form fields).",
                            pages_seen,
                            overrides,
                        )
                    for row in rows:
                        if row.detail_url in seen_in_run:
                            continue
                        seen_in_run.add(row.detail_url)
                        visited += 1
                        try:
                            detail = self.client.fetch(row.detail_url)
                        except FetchError:
                            errors += 1
                            continue

                        meta = parse_detail_page(detail.body)
                        pdf_url = select_primary_pdf_url(meta.pdf_urls)
                        content = ""
                        if pdf_url:
                            try:
                                pdf_bytes = self.client.fetch_bytes(pdf_url)
                                content = extract_pdf_text(pdf_bytes)
                            except FetchError:
                                content = ""
                            if not content:
                                empty_pdf_count += 1
                                logger.warning(
                                    "PDF rỗng hoặc bản scan (không có text layer) cho văn bản số ký hiệu=%s, URL=%s",
                                    meta.doc_number or row.doc_code,
                                    row.detail_url,
                                )

                        page_blob = f"{meta.title}\n{content}"
                        if len(content) < self.config.min_text_chars:
                            skipped += 1
                            continue
                        if self.config.keywords and not has_keyword(page_blob, self.config.keywords):
                            skipped += 1
                            continue

                        content_hash = compute_content_hash(content)
                        if not self.config.force_refresh and row.detail_url in seen and seen[row.detail_url] == content_hash:
                            skipped += 1
                            continue

                        is_update = (
                            not self.config.force_refresh
                            and row.detail_url in seen
                            and bool(seen[row.detail_url])
                            and seen[row.detail_url] != content_hash
                        )
                        if is_update:
                            updated += 1
                            logger.info(
                                "Phát hiện nội dung cập nhật cho văn bản số ký hiệu=%s, URL=%s",
                                meta.doc_number or row.doc_code,
                                row.detail_url,
                            )

                        doc = LegalDocument(
                            doc_id=_slugify(meta.doc_number) or row.doc_code,
                            title=meta.title or row.doc_code,
                            content=content,
                            issuer=meta.issuer,
                            doc_type=meta.doc_type,
                            issued_date=meta.issued_date,
                            source_url=row.detail_url,
                            source_system="chinhphu-postback-crawler",
                            metadata={
                                "effective_date": meta.effective_date,
                                "signer": meta.signer,
                                "pdf_url": pdf_url or "",
                                "category": batch_category,
                                "category_name": category_names.get(batch_category, ""),
                                "year": batch_year or _issued_year(meta.issued_date),
                            },
                        )
                        f.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")
                        saved += 1
                        batch_docs += 1
                        seen[row.detail_url] = content_hash
                    save_seen(state_path, seen)

                # E7 (kiểm chứng curl 2026-10-01): drdRecordPerPage=500 là GIỚI HẠN TỔNG kết quả,
                # không phải số dòng/trang. Site luôn trả 50 dòng/trang và Page$Last dừng ở trang 10,
                # nên mỗi lượt tìm kiếm lấy được tối đa 500 văn bản rồi bị cắt IM LẶNG.
                # Chạm ngưỡng => phải chia nhỏ bằng --years, nếu không sẽ mất dữ liệu mà không có lỗi.
                # Bỏ qua khối log tóm tắt này nếu lượt vừa rồi dừng giữa chừng vì lỗi mạng
                # (đã log riêng ở trên) — tránh in "chạm giới hạn 500" gây hiểu nhầm là chạy
                # trọn vẹn.
                if not pagination_error:
                    logger.info(
                        "Lượt tìm kiếm %s: %d trang, %d văn bản được ghi.",
                        overrides,
                        pages_seen,
                        batch_docs,
                    )
                    if pages_seen >= 10:
                        logger.warning(
                            "Lượt tìm kiếm %s đi hết %d trang và ghi %d văn bản (chạm giới hạn 500 "
                            "kết quả của site). Kết quả có thể bị cắt im lặng — hãy chia nhỏ bằng --years.",
                            overrides,
                            pages_seen,
                            batch_docs,
                        )

        self.updated = updated
        self.empty_listing_pages = empty_listing_pages
        if empty_listing_pages > 0:
            logger.warning("Tổng số trang listing >1 trả về 0 văn bản: %d", empty_listing_pages)
        if empty_pdf_count > 0:
            logger.info("Tổng số văn bản có PDF rỗng/scan không trích xuất được: %d", empty_pdf_count)

        return CrawlStats(visited=visited, saved=saved, skipped=skipped, errors=errors, output_path=str(output))
