"""Tách cấu trúc văn bản pháp luật Việt Nam: Điều -> Khoản -> điểm.

Thuần chuỗi, không biết gì về chunk hay retrieval. Tách thành module riêng vì đây là
phần regex rủi ro nhất của Spec A và cần test cô lập trên text bẩn.

Yêu cầu quan trọng: text đưa vào phải CÒN `\\n`. Mọi neo ở đây là neo đầu dòng, nên
nếu text đã bị nén khoảng trắng (`strip_page_chrome()` làm vậy) thì không còn gì để neo.
Dùng `cleaning.strip_page_chrome_lines()` thay thế.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Điều: cho phép 'Điều' bị xuống dòng tách khỏi số (PDF hay làm vậy) vì \s khớp \n.
# Số Điều có thể là số ghép kiểu bộ pháp điển: '31.1.TT.77.1'.
# Chấp nhận cả 'Điêu' vì text PDF đôi khi mất dấu ngã/huyền trên 'ề'.
DIEU_RE = re.compile(
    r"(?m)^[ \t]*Đi[eề]u\s+"
    r"(?P<num>\d+(?:\.\d+)*(?:\.[A-Za-zĐ]+)*(?:\.\d+)*)"
    r"\s*[\.:]?\s*(?P<title>[^\n]*)"
)

# Khoản: đầu dòng, '<số>.' hoặc '<số>)'. Cho phép hậu tố chữ ('1a') và khoảng trắng
# trước dấu chấm ('1 .'). Bắt buộc có khoảng trắng sau dấu, để số trang đứng một mình
# hoặc '15' giữa dòng không bị nhận nhầm.
KHOAN_RE = re.compile(r"(?m)^[ \t]*(?P<num>\d+[a-z]?)\s*[\.\)]\s+(?P<body>[^\n]*)")

# Điểm: đầu dòng, một chữ rồi ')'.
DIEM_RE = re.compile(r"(?m)^[ \t]*(?P<label>[a-zđ])\s*\)\s*(?P<body>[^\n]*)")


@dataclass
class Diem:
    label: str
    body: str


@dataclass
class Khoan:
    number: str
    body: str
    diem: list[Diem] = field(default_factory=list)


@dataclass
class Article:
    number: str
    title: str
    body: str
    khoan: list[Khoan] = field(default_factory=list)


def _parse_diem(segment: str) -> list[Diem]:
    """Tách điểm trong phần thân của một Khoản.

    `DIEM_RE` chỉ neo được đầu dòng của điểm (`[^\\n]*` không ăn qua `\\n`), nên nếu lấy
    thẳng `match.group("body")` thì một điểm xuống dòng (ví dụ "a) ...\\ndòng tiếp theo")
    sẽ mất toàn bộ các dòng sau. Lấy theo khoảng [đầu body, đầu điểm kế tiếp) như cách
    `_parse_khoan` làm với Khoản để giữ hết các dòng.
    """
    hits = list(DIEM_RE.finditer(segment))
    diem_list: list[Diem] = []
    for index, match in enumerate(hits):
        end = hits[index + 1].start() if index + 1 < len(hits) else len(segment)
        diem_list.append(Diem(label=match.group("label"), body=segment[match.start("body"):end].strip()))
    return diem_list


def _parse_khoan(text: str) -> list[Khoan]:
    """Tách Khoản trong phần thân của một Điều (KHÔNG gồm dòng header của Điều)."""
    hits = list(KHOAN_RE.finditer(text))
    khoan_list: list[Khoan] = []
    for index, match in enumerate(hits):
        end = hits[index + 1].start() if index + 1 < len(hits) else len(text)
        segment = text[match.start():end].strip()
        khoan_list.append(Khoan(number=match.group("num"), body=segment, diem=_parse_diem(segment)))
    return khoan_list


def parse_articles(text: str) -> list[Article]:
    """Tách danh sách Điều. Không tìm được Điều nào thì trả về [] (không raise)."""
    hits = list(DIEU_RE.finditer(text))
    articles: list[Article] = []
    for index, match in enumerate(hits):
        end = hits[index + 1].start() if index + 1 < len(hits) else len(text)
        # Khoản phải parse từ SAU dòng header: nếu không, dòng '7. Điều kiện vay vốn'
        # của chính header (khi 'Điều' bị xuống dòng tách khỏi số) sẽ bị đếm thành
        # "Khoản 7". Đây là lỗi thật đã gặp khi prototype.
        after_header = text[match.end():end]
        articles.append(
            Article(
                number=match.group("num"),
                title=match.group("title").strip(),
                body=text[match.start():end].strip(),
                khoan=_parse_khoan(after_header),
            )
        )
    return articles
