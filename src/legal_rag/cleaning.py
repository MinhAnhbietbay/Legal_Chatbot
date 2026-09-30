"""Text cleaning helpers for crawled Vietnamese legal documents."""

from __future__ import annotations

import re

import unicodedata

def normalize_vietnamese(text: str) -> str:
    """Lowercase and remove Vietnamese accents for tolerant keyword matching."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


NOISE_PHRASES = (
    "english 中文",
    "trang chủ chính phủ",
    "công dân doanh nghiệp kiều bào",
    "báo điện tử chính phủ",
    "văn phòng chính phủ",
    "thư điện tử công vụ chính phủ",
    "sea games",
    "phục hồi và phát triển kinh tế",
    "giải ngân vốn đầu tư công",
    "chuyển đổi số",
    "thích ứng an toàn",
)

START_MARKERS = (
    "Số ký hiệu",
    "Ngày ban hành",
    "Ngày có hiệu lực",
    "Loại văn bản",
    "Điều 1.",
    "Điều 1 ",
    "Chương I",
    "CHƯƠNG I",
)

END_MARKERS = (
    "Tài liệu đính kèm",
    "Các văn bản khác",
    "Văn bản liên quan",
    "Thuộc tính văn bản",
    "Ý kiến bạn đọc",
    "Tin liên quan",
)

WEATHER_PATTERN = re.compile(
    r"\b[A-ZÀ-ỴĐ][\wÀ-Ỵà-ỵđĐ\s]{2,30}\s+\d{1,2}°\s*-\s*\d{1,2}°",
    flags=re.UNICODE,
)


def _first_marker_index(text: str, markers: tuple[str, ...]) -> int | None:
    positions = [text.find(marker) for marker in markers if marker in text]
    positions = [pos for pos in positions if pos >= 0]
    return min(positions) if positions else None


def _last_title_index(text: str, title: str) -> int | None:
    if not title:
        return None
    idx = text.rfind(title)
    return idx if idx >= 0 else None


def strip_page_chrome(text: str, title: str = "") -> str:
    """Remove common portal navigation/weather text from crawled pages."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return ""

    title_idx = _last_title_index(cleaned, title)
    marker_idx = _first_marker_index(cleaned, START_MARKERS)
    start_candidates = [idx for idx in (title_idx, marker_idx) if idx is not None]
    if start_candidates:
        cleaned = cleaned[min(start_candidates) :]

    end_idx = _first_marker_index(cleaned, END_MARKERS)
    if end_idx and end_idx > 300:
        cleaned = cleaned[:end_idx]

    cleaned = WEATHER_PATTERN.sub(" ", cleaned)
    for phrase in NOISE_PHRASES:
        cleaned = re.sub(re.escape(phrase), " ", cleaned, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", cleaned).strip()


def looks_like_noise_document(title: str, source_url: str, content: str) -> bool:
    """Reject article/list pages that are not actual legal-document pages."""
    haystack = normalize_vietnamese(" ".join([title, source_url, content[:1000]]))
    if "phapdien.moj.gov.vn/qt/tintuc" in haystack:
        return True
    if "vanban.chinhphu.vn/he-thong-van-ban" in haystack:
        return True
    if "nghien-cuu-trao-doi" in haystack and "so ky hieu" not in haystack:
        return True
    return False
