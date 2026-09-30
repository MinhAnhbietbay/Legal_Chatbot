#!/usr/bin/env python3
"""Prepare banking-law chunks from VN-Law-Advisor JSON exports.

Example:
    python scripts/legalrag_prepare_corpus.py \
        --input data/legal/raw \
        --output data/legal/processed/banking_chunks.jsonl
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.legal_rag.chunking import chunk_documents
from src.legal_rag.corpus_filter import filter_banking_docs
from src.legal_rag.ingestion.json_loader import load_legal_documents
from src.legal_rag.cleaning import strip_page_chrome


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/legal/raw", help="JSON/JSONL export file or folder")
    parser.add_argument("--output", default="data/legal/processed/banking_chunks.jsonl")
    parser.add_argument("--chunk-size", type=int, default=1400)
    parser.add_argument("--overlap", type=int, default=180)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docs = load_legal_documents(args.input)
    banking_docs = filter_banking_docs(docs)
    
    for doc in banking_docs:
        doc.content = strip_page_chrome(doc.content, title=doc.title)

    chunks = chunk_documents(banking_docs, chunk_size=args.chunk_size, overlap=args.overlap)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_suffix(output.suffix + ".tmp")
    with temp_output.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n")
    temp_output.replace(output)

    print(f"Loaded documents: {len(docs)}")
    print(f"Banking-law documents: {len(banking_docs)}")
    print(f"Written chunks: {len(chunks)} -> {output}")


if __name__ == "__main__":
    main()

