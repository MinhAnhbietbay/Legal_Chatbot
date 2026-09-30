"""Prompt assembly for Legal RAG Mode A and Mode B."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.legal_rag.documents import LegalChunk


AUTO_REJECTION_PROMPT = """Ban la chuyen gia phap ly ngan hang tai Viet Nam.
Dua tren ket qua danh gia rui ro tin dung va cac quy dinh phap ly duoc cung cap,
hay soan thao LY DO TU CHOI CHINH THUC cho ho so vay nay.

Yeu cau:
- Neu ro tung ly do tu choi theo tung yeu to rui ro
- Moi ly do phai trich dan dieu khoan cu the: [Ten van ban, Dieu/Khoan neu co]
- Ngon ngu chuyen nghiep, phu hop de gui cho nhan vien tin dung
- Khong them thong tin ngoai ngu canh duoc cung cap

Ket qua ML:
- Xac suat vo no: {prob_default:.1%}
- Phan loai rui ro: {risk_class}
- Cac yeu to rui ro chinh: {risk_factors}

Quy dinh phap ly lien quan:
{legal_context}
"""


ADHOC_PROMPT = """Ban la tro ly phap ly nghiep vu tin dung ngan hang tai Viet Nam.
Tra loi cau hoi cua nhan vien tin dung dua tren cac van ban quy pham phap luat duoc cung cap.

Quy tac:
1. Chi tra loi dua tren ngu canh phap ly ben duoi
2. Moi luan diem phai co trich dan: [Van ban, Dieu/Khoan neu co]
3. Neu khong co thong tin: "Khong tim thay quy dinh lien quan trong tai lieu hien co"
4. Cuoi cau tra loi: goi y van ban day du can tham khao them

Cau hoi: {question}

Ngu canh phap ly:
{legal_context}
"""


def format_legal_context(chunks: list[LegalChunk]) -> str:
    """Format retrieved chunks with citation metadata."""
    blocks: list[str] = []
    for chunk in chunks:
        article = chunk.metadata.get("article_hint") or "khong ro dieu"
        source = chunk.metadata.get("source") or chunk.title
        blocks.append(f"[{source}, {article}]\n{chunk.content}")
    return "\n\n".join(blocks)


def format_risk_factors(factors: list[dict[str, Any]] | list[tuple[str, float]]) -> str:
    if not factors:
        return "Khong co yeu to rui ro duoc cung cap"
    if isinstance(factors[0], tuple):
        return "; ".join(f"{name} ({value:+.3f})" for name, value in factors)  # type: ignore[misc]
    return "; ".join(
        f"{item.get('feature')} SHAP={item.get('shap_contribution'):+.3f}: {item.get('rationale', '')}"
        for item in factors  # type: ignore[union-attr]
    )


def build_auto_rejection_prompt(ml_result: dict[str, Any], legal_chunks: list[LegalChunk]) -> str:
    return AUTO_REJECTION_PROMPT.format(
        prob_default=float(ml_result["prob_default"]),
        risk_class=ml_result["risk_class"],
        risk_factors=format_risk_factors(ml_result.get("risk_factors", [])),
        legal_context=format_legal_context(legal_chunks),
    )


def build_adhoc_prompt(question: str, legal_chunks: list[LegalChunk]) -> str:
    return ADHOC_PROMPT.format(
        question=question,
        legal_context=format_legal_context(legal_chunks),
    )


def generate_rejection_reason(
    ml_result: dict[str, Any],
    legal_chunks: list[LegalChunk],
    llm: Callable[[str], str],
) -> str:
    """Generate Mode A answer using the provided LLM callable."""
    return llm(build_auto_rejection_prompt(ml_result, legal_chunks))


def answer_adhoc_question(
    question: str,
    legal_chunks: list[LegalChunk],
    llm: Callable[[str], str],
) -> str:
    """Generate Mode B answer using the provided LLM callable."""
    return llm(build_adhoc_prompt(question, legal_chunks))

