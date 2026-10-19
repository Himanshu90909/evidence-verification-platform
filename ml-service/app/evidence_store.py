"""Evidence store: loads the research corpus (JSONL) and its metadata mapping.

Corpus document format (one JSON per line):
{
  "document_id": "wiki-<page-slug>-<line>",
  "text": "...",
  "page": "Page Title",
  "line_id": 12,
  "source": {"name": "FEVER / Wikipedia", "url": "https://en.wikipedia.org/wiki/..."}
}
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger("evp.evidence")


@dataclass
class EvidenceDoc:
    document_id: str
    text: str
    page: str = ""
    line_id: Optional[int] = None
    source_name: str = "FEVER / Wikipedia (research corpus)"
    source_url: str = ""

    def as_dict(self) -> Dict:
        return {
            "document_id": self.document_id,
            "text": self.text,
            "page": self.page,
            "line_id": self.line_id,
            "source": {"name": self.source_name, "url": self.source_url},
        }


class EvidenceStore:
    def __init__(self) -> None:
        self.docs: List[EvidenceDoc] = []
        self.by_id: Dict[str, EvidenceDoc] = {}
        self._loaded_path: Optional[str] = None

    def load(self, path: str, max_documents: int = 0) -> None:
        docs: List[EvidenceDoc] = []
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                src = rec.get("source") or {}
                docs.append(
                    EvidenceDoc(
                        document_id=rec["document_id"],
                        text=rec["text"],
                        page=rec.get("page", ""),
                        line_id=rec.get("line_id"),
                        source_name=src.get("name", "FEVER / Wikipedia (research corpus)"),
                        source_url=src.get("url", ""),
                    )
                )
                if max_documents and len(docs) >= max_documents:
                    break
        self.docs = docs
        self.by_id = {d.document_id: d for d in docs}
        self._loaded_path = path
        logger.info("Loaded %d evidence documents from %s", len(docs), path)

    @property
    def size(self) -> int:
        return len(self.docs)

    @property
    def loaded(self) -> bool:
        return bool(self.docs)

    def get(self, document_id: str) -> Optional[EvidenceDoc]:
        return self.by_id.get(document_id)

    def get_many(self, ids: List[str]) -> List[EvidenceDoc]:
        out = []
        for i in ids:
            d = self.by_id.get(i)
            if d is not None:
                out.append(d)
        return out
