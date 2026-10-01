"""Nạp bộ câu hỏi đánh giá do người dùng tự viết.

Format YAML (xem docs/eval/retrieval_questions.example.yaml). `khoan` bỏ trống nghĩa là
mọi Khoản của Điều đó đều được tính đúng.

Nhãn sai thì thà dừng: file sai định dạng sẽ raise ValueError kèm `id` của câu gần nhất,
chứ không âm thầm bỏ qua câu đó — một bộ câu hỏi hỏng phải nhìn ra ngay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class GoldEntry:
    doc: str
    dieu: str
    khoan: str = ""


@dataclass
class EvalQuestion:
    id: str
    question: str
    relevant: list[GoldEntry] = field(default_factory=list)
    note: str = ""


def load_questions(path: str | Path) -> list[EvalQuestion]:
    """Nạp và kiểm tra bộ câu hỏi. Raise ValueError nếu sai định dạng."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path}: file câu hỏi phải là một danh sách YAML ở cấp cao nhất")

    questions: list[EvalQuestion] = []
    for index, item in enumerate(payload):
        label = (item or {}).get("id", f"(câu thứ {index + 1}, chưa có id)") if isinstance(item, dict) else f"(câu thứ {index + 1})"
        if not isinstance(item, dict):
            raise ValueError(f"{path}: câu {label} không phải một mapping YAML")
        if not item.get("question"):
            raise ValueError(f"{path}: câu {label} thiếu trường 'question'")
        if "relevant" not in item:
            raise ValueError(
                f"{path}: câu {label} thiếu trường 'relevant'. "
                "Nếu chưa gắn nhãn, ghi 'relevant: []' để eval báo là bỏ qua "
                "thay vì tính thành 0 điểm."
            )
        raw_relevant = item.get("relevant") or []
        if not isinstance(raw_relevant, list):
            raise ValueError(f"{path}: câu {label}: 'relevant' phải là danh sách")

        relevant: list[GoldEntry] = []
        for gold in raw_relevant:
            if not isinstance(gold, dict) or not gold.get("doc") or gold.get("dieu") in (None, ""):
                raise ValueError(f"{path}: câu {label}: mỗi mục 'relevant' cần có 'doc' và 'dieu'")
            relevant.append(
                GoldEntry(
                    doc=str(gold["doc"]),
                    dieu=str(gold["dieu"]),
                    khoan="" if gold.get("khoan") in (None, "") else str(gold["khoan"]),
                )
            )

        questions.append(
            EvalQuestion(
                id=str(item["id"]) if item.get("id") else label,
                question=str(item["question"]),
                relevant=relevant,
                note=str(item.get("note") or ""),
            )
        )
    return questions
