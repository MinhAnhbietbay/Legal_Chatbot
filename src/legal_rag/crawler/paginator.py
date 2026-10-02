"""Walks an ASP.NET GridView's pages by simulating __doPostBack calls."""

from __future__ import annotations

import logging
import re
from typing import Iterator, Protocol

from src.legal_rag.crawler.aspnet_postback import (
    build_page_postback_data,
    extract_form_fields,
    extract_page_targets,
    find_control_prefix,
)
from src.legal_rag.crawler.http_client import FetchResult

logger = logging.getLogger(__name__)


class _PostbackCapableClient(Protocol):
    def fetch(self, url: str, cookie: str = "") -> FetchResult: ...
    def post(self, url: str, data: dict[str, str], cookie: str = "") -> FetchResult: ...


class AspNetGridPaginator:
    """Yields each page's HTML for an ASP.NET GridView, following Page$N postbacks."""

    def __init__(
        self,
        client: _PostbackCapableClient,
        url: str,
        grid_suffix: str = "grvDocument",
        search_overrides: dict[str, str] | None = None,
    ) -> None:
        self.client = client
        self.url = url
        self.grid_suffix = grid_suffix
        self.search_overrides = search_overrides

    def pages(self) -> Iterator[str]:
        result = self.client.fetch(self.url)
        html = result.body
        cookie = result.set_cookie

        if self.search_overrides:
            form_fields = extract_form_fields(html)
            # Dùng 'hidSiteId' làm mốc tìm prefix cho bước search, KHÔNG dùng grid_suffix:
            # trang GET ban đầu (trước khi có kết quả) chưa chắc đã chứa chuỗi
            # '$grvDocument' (chỉ xuất hiện trong link __doPostBack của pager, mà pager chỉ
            # có khi ĐÃ có kết quả nhiều trang) — review 2026-10-01 phát hiện
            # find_control_prefix(html, grid_suffix) trả về None ở bước này, khiến mọi key
            # override bị POST đi KHÔNG CÓ PREFIX (ví dụ 'drdDocCategory' thay vì
            # 'ctrl_1_1$drdDocCategory'), và site bỏ qua field không đúng tên control.
            # 'hidSiteId' là field ẩn thường trực theo spec §3.1 (E3), có mặt ngay từ GET
            # đầu tiên bất kể đã có kết quả hay chưa.
            prefix = find_control_prefix(html, "hidSiteId") or find_control_prefix(html, self.grid_suffix)
            search_data = dict(form_fields)
            for key, val in self.search_overrides.items():
                prefixed_key = f"{prefix}${key}" if prefix and not key.startswith("ctrl_") else key
                search_data[prefixed_key] = val
            search_data["__EVENTTARGET"] = ""
            search_data["__EVENTARGUMENT"] = ""
            result = self.client.post(self.url, search_data, cookie=cookie)
            html = result.body
            cookie = result.set_cookie or cookie

        targets = [t for t in extract_page_targets(html) if t != "Last"]
        row_count = len(re.findall(r"pageid=\d+&docid=\d+", html))
        if not targets and row_count == 50:
            logger.warning(
                "Không tìm thấy pager và kết quả có đúng 50 dòng; có thể drdRecordPerPage khiến danh sách bị cắt mà không hiện pager. Cân nhắc đặt records_per_page=500."
            )

        yield html

        visited_pages = {"1"}
        while True:
            prefix = find_control_prefix(html, self.grid_suffix)
            if not prefix:
                if visited_pages == {"1"}:
                    logger.warning(
                        "Không tìm thấy control-prefix cho grid '%s' ở trang 1; cấu trúc HTML có thể đã đổi.",
                        self.grid_suffix,
                    )
                return
            targets = [t for t in extract_page_targets(html) if t not in visited_pages and t != "Last"]
            if not targets:
                if len(visited_pages) >= 10:
                    logger.warning(
                        "Đã duyệt qua %d trang (>= 10 trang); có thể kết quả đã chạm trần 500 văn bản/10 trang "
                        "và bị cắt ngầm bởi ASP.NET GridView. Cân nhắc thu hẹp hoặc chia nhỏ bộ lọc theo năm.",
                        len(visited_pages),
                    )
                return
            next_page = targets[0]
            form_fields = extract_form_fields(html)
            data = build_page_postback_data(form_fields, prefix, self.grid_suffix, next_page)
            result = self.client.post(self.url, data, cookie=cookie)
            if result.body == html:
                return

            # Silent pagination error detection:
            # Check if POST response indicates empty results or missing required form fields
            has_no_docs = "Không có thông tin văn bản" in result.body
            has_detail_links = bool(re.search(r"pageid=\d+&docid=\d+", result.body, re.I))
            if has_no_docs or not has_detail_links:
                logger.warning(
                    "Phát hiện lỗi phân trang im lặng ở trang %s: grid không có link chi tiết hoặc chứa thông báo "
                    "'Không có thông tin văn bản'. Có thể request POST thiếu field form cần thiết (ví dụ hidSiteId, hidIsSearch). "
                    "Dừng phân trang.",
                    next_page,
                )
                return

            html = result.body
            cookie = result.set_cookie or cookie
            visited_pages.add(next_page)
            yield html
