# PH2 — Chatbot pháp lý tín dụng/ngân hàng Việt Nam (Legal RAG)

Chatbot hỏi-đáp luật tín dụng/ngân hàng VN dựa trên RAG (retrieval-augmented
generation): crawl văn bản pháp luật → làm sạch/chunk theo Điều-Khoản →
retrieval → trả lời kèm trích dẫn `[Văn bản, Điều X, Khoản Y]`.

Tách ra từ dự án `DataMining` (PH1 Home Credit + PH2 legal RAG) ngày
2026-09-30, thành project CV độc lập. Không bao gồm Bridge module hay tích
hợp dashboard với PH1 — nếu cần nối với model rủi ro tín dụng sau này, sẽ qua
API giữa hai repo, không dùng chung codebase.

## Trạng thái

Mới chuyển khung code (crawler, chunking, retrieval lexical tạm, rag_pipeline)
và corpus thô (318 văn bản, ~10 chunk sau filter) từ DataMining. **Chưa có
implementation plan ở repo này** — xem `docs/specs/` để rà soát lại thiết kế
trước khi viết plan và code.

## Đọc trước khi code

1. `docs/specs/2026-08-05-ph2-legal-rag-design-excerpt.md` — thiết kế gốc +
   mục "Điểm cần rà soát lại" (BM25-only vs so sánh embedding, crawler rewrite
   chưa chạy, bộ câu hỏi eval chưa có).
2. `docs/specs/2026-08-19-legal-crawler-rewrite-design.md` — thiết kế crawler
   viết lại, có mục "Việc cần dò thêm khi code" chưa chốt.
3. `docs/plans/2026-08-19-legal-crawler-rewrite-plan.md`
4. `docs/LEGAL_RAG_SETUP.md`
5. `src/legal_rag/README.md` — cấu trúc code.

## Cấu trúc

```
src/legal_rag/     # crawler, chunking, retrieval, rag_pipeline
scripts/           # legalrag_crawl_laws.py, legalrag_prepare_corpus.py
data/legal/        # corpus (gitignore — chạy lại crawler để tái tạo)
docs/              # specs, plans, notes, seed URL files
tests/legal_rag/   # chưa có test — viết theo TDD khi bắt đầu code
```

## Chạy thử nhanh

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 scripts/legalrag_crawl_laws.py \
  --seed-file docs/legal_seed_urls.example.txt \
  --max-pages 100 --max-depth 2 \
  --output data/legal/raw/law_crawl.jsonl

python3 scripts/legalrag_prepare_corpus.py \
  --input data/legal/raw \
  --output data/legal/processed/banking_chunks.jsonl
```
