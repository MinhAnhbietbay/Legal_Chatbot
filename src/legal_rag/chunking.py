"""Chia văn bản pháp luật thành chunk có neo Điều - Khoản.

Phương án (quyết định người dùng 2026-10-01): chunk = một Khoản, nhưng content được
GẮN THÊM số Điều và tiêu đề Điều ở đầu. Lý do: trích dẫn cần xuống tới Khoản, còn
BM25 chỉ khớp được cái gì có trong text — mà tiêu đề Điều ("Điều 7. Điều kiện vay
vốn") là nơi mang nghĩa. Gắn nó vào là cải thiện recall gần như miễn phí.

Các nhánh còn lại:
- Điều không chia Khoản          -> chunk = cả Điều,  structure="dieu"
- Khoản dài quá max_chunk_chars  -> cắt theo điểm a)/b), giữ số Khoản
- Không parse được Điều nào      -> cắt theo ký tự,  structure="fallback"

`split_text()` được giữ nguyên tên và chữ ký vì nhánh fallback vẫn dùng nó.
"""

from __future__ import annotations

import re

from src.legal_rag.cleaning import strip_page_chrome_lines
from src.legal_rag.documents import LegalChunk, LegalDocument
from src.legal_rag.legal_structure import Article, Khoan, parse_articles

# Chỉ dùng để tìm VỊ TRÍ bắt đầu của điểm đầu tiên trong một Khoản (tách câu dẫn ra
# khỏi danh sách điểm) — không dùng để parse cấu trúc, đó là việc của legal_structure.
_DIEM_START_RE = re.compile(r"(?m)^[ \t]*[a-zđ]\s*\)\s*")


def split_text(text: str, chunk_size: int = 1400, overlap: int = 180) -> list[str]:
    """Cắt text theo số ký tự, ưu tiên cắt ở ranh giới câu. Dùng cho nhánh fallback."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        cut = cleaned.rfind(". ", start, end)
        if cut > start + chunk_size // 2:
            end = cut + 1
        chunks.append(cleaned[start:end].strip())
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def _article_context(article: Article) -> str:
    """Dòng ngữ cảnh gắn vào đầu mỗi chunk của một Điều."""
    if article.title:
        return f"Điều {article.number}. {article.title}"
    return f"Điều {article.number}."


def _base_metadata(doc: LegalDocument) -> dict:
    """Metadata chung: giữ nguyên mọi key crawler đã ghi, rồi thêm field của chunking."""
    return {
        **doc.metadata,
        "source": doc.title,
        "issuer": doc.issuer,
        "doc_type": doc.doc_type,
        "issued_date": doc.issued_date,
        "source_url": doc.source_url,
    }


def _make_chunk(
    doc: LegalDocument,
    index: int,
    content: str,
    *,
    dieu: str,
    dieu_title: str,
    khoan: str,
    diem: str,
    structure: str,
) -> LegalChunk:
    metadata = _base_metadata(doc)
    metadata.update(
        {
            "dieu": dieu,
            "dieu_title": dieu_title,
            "khoan": khoan,
            "diem": diem,
            "structure": structure,
        }
    )
    return LegalChunk(
        chunk_id=f"{doc.doc_id}::chunk-{index:04d}",
        doc_id=doc.doc_id,
        title=doc.title,
        content=content,
        metadata=metadata,
    )


def _khoan_chunks(
    doc: LegalDocument,
    article: Article,
    khoan: Khoan,
    start_index: int,
    max_chunk_chars: int,
    chunk_overlap: int,
) -> list[LegalChunk]:
    """Một Khoản -> một chunk; nếu dài quá thì cắt theo điểm a)/b)."""
    context = _article_context(article)
    body = f"{context}\n{khoan.body}".strip()

    if len(body) <= max_chunk_chars or not khoan.diem:
        pieces = [(body, "")] if len(body) <= max_chunk_chars else [
            (f"{context}\n{piece}", "")
            for piece in split_text(khoan.body, chunk_size=max_chunk_chars, overlap=chunk_overlap)
        ]
    else:
        # Lấy câu dẫn của Khoản (phần đứng trước điểm a) đầu tiên, ví dụ "2. Mục đích sử
        # dụng vốn hợp pháp gồm:"). Nếu bỏ nó thì mỗi chunk điểm sẽ mất ngữ cảnh "gồm" đó
        # — lỗi phát hiện ở review: ghép thẳng diem.body mà không có câu dẫn làm mất nội
        # dung mở đầu của Khoản.
        preamble_match = _DIEM_START_RE.search(khoan.body)
        preamble = khoan.body[: preamble_match.start()].strip() if preamble_match else ""
        prefix = "\n".join(part for part in (context, preamble) if part)
        pieces = []
        for diem in khoan.diem:
            header = f"Khoản {khoan.number}. {diem.label}) "
            # Spec §2.1: "cắt tiếp theo điểm, có overlap" — nếu bản thân MỘT điểm (sau khi
            # legal_structure giữ đủ nhiều dòng) đã dài hơn max_chunk_chars thì phải cắt
            # tiếp bằng split_text(), không được ghép thẳng ra một chunk quá khổ.
            budget = max(max_chunk_chars - len(prefix) - len(header) - 1, 200)
            diem_pieces = (
                [diem.body]
                if len(diem.body) <= budget
                else split_text(diem.body, chunk_size=budget, overlap=chunk_overlap)
            )
            for piece in diem_pieces:
                content = "\n".join(part for part in (prefix, f"{header}{piece}") if part).strip()
                pieces.append((content, diem.label))

    chunks: list[LegalChunk] = []
    for offset, (content, diem_label) in enumerate(pieces):
        chunks.append(
            _make_chunk(
                doc,
                start_index + offset,
                content,
                dieu=article.number,
                dieu_title=article.title,
                khoan=khoan.number,
                diem=diem_label,
                structure="dieu-khoan",
            )
        )
    return chunks


def chunk_document(
    doc: LegalDocument,
    max_chunk_chars: int = 1400,
    chunk_overlap: int = 180,
) -> list[LegalChunk]:
    """Chia một văn bản thành chunk có neo Điều - Khoản."""
    cleaned = strip_page_chrome_lines(doc.content, title=doc.title)
    if not cleaned:
        return []

    articles = parse_articles(cleaned)
    chunks: list[LegalChunk] = []

    if not articles:
        # Không parse được Điều nào (PDF scan, định dạng lạ). Cắt theo ký tự và
        # ĐÁNH DẤU, để báo cáo eval đếm được "% chunk có neo Điều-Khoản chính xác".
        for index, piece in enumerate(
            split_text(cleaned, chunk_size=max_chunk_chars, overlap=chunk_overlap)
        ):
            chunks.append(
                _make_chunk(
                    doc, index, piece,
                    dieu="", dieu_title="", khoan="", diem="", structure="fallback",
                )
            )
        return chunks

    for article in articles:
        if not article.khoan:
            chunks.append(
                _make_chunk(
                    doc, len(chunks), article.body.strip(),
                    dieu=article.number, dieu_title=article.title,
                    khoan="", diem="", structure="dieu",
                )
            )
            continue
        for khoan in article.khoan:
            chunks.extend(
                _khoan_chunks(doc, article, khoan, len(chunks), max_chunk_chars, chunk_overlap)
            )
    return chunks


def chunk_documents(
    docs: list[LegalDocument],
    max_chunk_chars: int = 1400,
    chunk_overlap: int = 180,
) -> list[LegalChunk]:
    chunks: list[LegalChunk] = []
    for doc in docs:
        chunks.extend(chunk_document(doc, max_chunk_chars=max_chunk_chars, chunk_overlap=chunk_overlap))
    return chunks


def format_citation(chunk: LegalChunk) -> str:
    """Dựng chuỗi trích dẫn. MỘT chỗ duy nhất, dùng bởi cả eval và Spec B.

    Chunk `fallback` KHÔNG được bịa ra số Điều — nói thẳng là chưa xác định được.
    """
    source = chunk.metadata.get("source") or chunk.title
    structure = chunk.metadata.get("structure", "fallback")
    if structure == "fallback":
        return f"[{source}, chưa xác định Điều]"

    parts = [source, f"Điều {chunk.metadata.get('dieu', '')}"]
    khoan = chunk.metadata.get("khoan", "")
    if khoan:
        parts.append(f"Khoản {khoan}")
    return "[" + ", ".join(parts) + "]"
