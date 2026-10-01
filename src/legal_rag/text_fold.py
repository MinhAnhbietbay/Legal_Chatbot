"""Chuẩn hoá chữ tiếng Việt cho retrieval lexical.

Khác `cleaning.normalize_vietnamese()` ở một điểm quyết định: hàm này map `đ` -> `d`.
`đ` là ký tự dựng sẵn U+0111 chứ không phải `d` + dấu, nên việc phân rã NFD rồi lọc
ký tự loại `Mn` (cách `normalize_vietnamese` làm) không chạm được tới nó — kết quả là
"Điều" ra "đieu" và không bao giờ khớp với "dieu".

`normalize_vietnamese()` được giữ nguyên vì `corpus_filter.py` đang dùng nó và đang
chạy đúng; đây là hàm mới bên cạnh, chỉ retrieval dùng.
"""

from __future__ import annotations

import re
import unicodedata


# Token là chuỗi chữ/số, cho phép '/' và '-' ở giữa để giữ nguyên số hiệu văn bản
# dạng "39/2016/TT-NHNN" — tách vụn nó là mất một tín hiệu truy vấn rất mạnh.
_TOKEN_PATTERN = re.compile(r"[0-9a-z]+(?:[/\-][0-9a-z]+)*")


def fold_vietnamese(text: str) -> str:
    """Hạ chữ thường, bỏ dấu, và map `đ`/`Đ` -> `d`."""
    lowered = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def tokenize_legal(text: str) -> list[str]:
    """Tách token cho BM25.

    KHÔNG loại token nào: không theo độ dài, không theo stopword list.
    - Lọc theo độ dài là lỗi L3 của code cũ: `len(token) > 2` xoá mất "nợ".
    - Stopword list là ý tồi với tiếng Việt: sau khi bỏ dấu, stopword trùng âm tiết
      mang nghĩa ("thế" của "thế chấp", "có" vs "cổ" của "cổ phần"). BM25 tự dập
      stopword bằng IDF, vì từ xuất hiện ở gần hết tài liệu có IDF tiến về 0.
    """
    return _TOKEN_PATTERN.findall(fold_vietnamese(text))
