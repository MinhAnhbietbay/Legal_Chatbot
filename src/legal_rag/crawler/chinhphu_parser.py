"""Parsers for vanban.chinhphu.vn document listing and detail pages.

Unlike the generic `LegalHTMLParser` used for other domains, this reads the
site's actual structured metadata table (Số ký hiệu / Ngày ban hành / Cơ
quan ban hành / ...) instead of relying on <meta> og-tags, which these pages
don't have. Most documents' real text lives only in a linked PDF attachment,
not in this HTML — see pdf_extract.py.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass, field


@dataclass
class ChinhphuListingRow:
    doc_code: str
    detail_url: str


@dataclass
class ChinhphuDocMeta:
    title: str = ""
    doc_number: str = ""
    issued_date: str = ""
    effective_date: str = ""
    doc_type: str = ""
    issuer: str = ""
    signer: str = ""
    pdf_urls: list[str] = field(default_factory=list)


_ROW_PATTERN = re.compile(
    # Chấp nhận cả nháy đơn và nháy kép ở href — fixture test dùng nháy đơn, nhưng chưa
    # chắc chắn 100% HTML thật luôn vậy (review 2026-10-01); nới regex là thay đổi không
    # rủi ro vì chỉ MỞ RỘNG tập khớp, không làm hẹp lại các case đang khớp đúng.
    r"""<a href=['"](?P<href>[^'"]*pageid=\d+&docid=\d+[^'"]*)['"]>\s*"""
    r'<span class="code">(?P<code>[^<]*)</span>'
)
_FIELD_PATTERN = re.compile(
    # <td> chứa value cho phép có attribute (style/class) như <td> label — nới lỏng để
    # không vỡ nếu HTML thật thêm attribute vào ô value mà fixture test chưa phản ánh.
    r'<td class="col1"[^>]*>\s*(?P<label>[^<]+?)\s*</td>\s*<td[^>]*>\s*(?P<value>.*?)\s*</td>',
    re.S,
)
_PDF_PATTERN = re.compile(r'href="(https://datafiles\.chinhphu\.vn/[^"]+\.pdf)"')
_TITLE_PATTERN = re.compile(r'<h4 class="title">\s*<span[^>]*>(?P<title>.*?)</span>', re.S)

_LABEL_TO_FIELD = {
    "số ký hiệu": "doc_number",
    "ngày ban hành": "issued_date",
    "ngày có hiệu lực": "effective_date",
    "loại văn bản": "doc_type",
    "cơ quan ban hành": "issuer",
    "người ký": "signer",
}


def _clean_value(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_listing_rows(html: str, base_url: str = "https://vanban.chinhphu.vn") -> list[ChinhphuListingRow]:
    """Extract one row per document link from a listing/search-results page."""
    rows: list[ChinhphuListingRow] = []
    seen_urls: set[str] = set()
    for match in _ROW_PATTERN.finditer(html):
        href = html_lib.unescape(match.group("href"))
        detail_url = href if href.startswith("http") else f"{base_url}{href}"
        if detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        rows.append(
            ChinhphuListingRow(doc_code=html_lib.unescape(match.group("code")).strip(), detail_url=detail_url)
        )
    return rows


def parse_detail_page(html: str) -> ChinhphuDocMeta:
    """Extract structured metadata and attached PDF links from a document detail page."""
    meta = ChinhphuDocMeta()
    title_match = _TITLE_PATTERN.search(html)
    if title_match:
        meta.title = _clean_value(title_match.group("title"))
    for match in _FIELD_PATTERN.finditer(html):
        label = _clean_value(match.group("label")).lower()
        field_name = _LABEL_TO_FIELD.get(label)
        if field_name:
            setattr(meta, field_name, _clean_value(match.group("value")))
    meta.pdf_urls = list(dict.fromkeys(_PDF_PATTERN.findall(html)))
    return meta


def select_primary_pdf_url(pdf_urls: list[str]) -> str | None:
    """Prefer the main document PDF over "-kem" (phụ lục/kèm theo) attachments."""
    primary = [url for url in pdf_urls if "-kem" not in url.rsplit("/", 1)[-1]]
    candidates = primary or pdf_urls
    return candidates[0] if candidates else None


def parse_category_names(html: str) -> dict[str, str]:
    """Map mã lĩnh vực -> tên lĩnh vực, đọc từ <select ...drdDocCategory> của trang listing.

    Đọc runtime thay vì hardcode: form thật có 80 lĩnh vực (xác nhận bằng curl 2026-10-01)
    và danh sách này do site quản lý nên có thể thay đổi. Trả về {} nếu không tìm thấy select
    (ví dụ fixture test tối giản) — khi đó caller để tên lĩnh vực rỗng, không được crash.
    """
    select_match = re.search(
        r'<select\b[^>]*\bname=["\'][^"\']*drdDocCategory["\'][^>]*>(.*?)</select>',
        html,
        re.I | re.S,
    )
    if not select_match:
        return {}

    names: dict[str, str] = {}
    for value, label in re.findall(
        r'<option\b[^>]*\bvalue=["\']([^"\']*)["\'][^>]*>(.*?)</option>',
        select_match.group(1),
        re.I | re.S,
    ):
        text = html_lib.unescape(re.sub(r"<[^>]+>", "", label)).strip()
        if value:
            names[value] = text
    return names
