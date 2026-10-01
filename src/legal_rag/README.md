# Legal RAG — chatbot pháp lý ngân hàng/tín dụng VN

Xử lý corpus pháp luật và lắp ráp pipeline RAG cho chatbot hỏi-đáp luật
tín dụng/ngân hàng. Repo độc lập, không phụ thuộc PH1 (Home Credit) hay
Bridge module — xem `docs/specs/2026-08-05-ph2-legal-rag-design-excerpt.md`
mục "Điểm cần rà soát lại" trước khi lập plan thực thi.

## Code Layout

```text
src/legal_rag/
├── documents.py              # LegalDocument, LegalChunk
├── corpus_filter.py          # lọc văn bản liên quan tín dụng/ngân hàng
├── chunking.py                # chia chunk, giữ metadata trích dẫn
├── text_fold.py              # bỏ dấu + đ->d cho retrieval
├── legal_structure.py        # text -> Điều / Khoản / điểm
├── eval/                     # Precision@k, Recall@k, MRR
├── crawler/                   # crawler pháp luật tự viết
├── ingestion/
│   └── json_loader.py         # nạp export JSON/JSONL từ crawler
├── retrieval/
│   ├── simple_retriever.py    # baseline TF-IDF (giữ lại để so sánh)
│   └── bm25_retriever.py      # Okapi BM25 tự viết, trả về điểm + lọc theo metadata
└── rag_pipeline.py            # lắp prompt truy vấn hỏi-đáp
```

## Data Flow

```text
crawler (src/legal_rag/crawler)
        ↓
data/legal/raw/*.jsonl
        ↓
python scripts/legalrag_prepare_corpus.py
        ↓
data/legal/processed/banking_chunks.jsonl
        ↓
retriever (BM25, xem quyết định lexical/embedding trong spec)
        ↓
answer synthesis (extractive + citation, Gemini fallback tuỳ chọn)
```

## Chạy crawler

```bash
python3 scripts/legalrag_crawl_laws.py \
  --seed-file docs/legal_seed_urls.example.txt \
  --max-pages 100 \
  --max-depth 2 \
  --output data/legal/raw/law_crawl.jsonl
```

Rồi chuẩn bị chunk:

```bash
python3 scripts/legalrag_prepare_corpus.py \
  --input data/legal/raw \
  --output data/legal/processed/banking_chunks.jsonl
```

Xem `docs/LEGAL_RAG_SETUP.md` để biết chi tiết luồng crawl/export, và
`docs/notes/vn-law-advisor-reference.md` cho bối cảnh vì sao không tái dùng
crawler VN-Law-Advisor.

## Việc tiếp theo

Xem mục "Điểm cần rà soát lại" trong
`docs/specs/2026-08-05-ph2-legal-rag-design-excerpt.md` — cần chốt các quyết
định đó trước khi viết implementation plan.
