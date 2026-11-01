"""Section-level retrieval over docs/*.md using TF-IDF (runs fully offline, no embedding API)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from . import DOCS_DIR


@dataclass
class Chunk:
    doc: str
    section: str
    text: str

    @property
    def ref(self) -> str:
        return f"{self.doc}#{self.section}"


def load_chunks(docs_dir=DOCS_DIR) -> list[Chunk]:
    """Split each markdown file on '## ' headings; each section is one chunk."""
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        title, *sections = re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M)
        doc_title = title.strip().splitlines()[0].lstrip("# ").strip()
        for sec in sections:
            heading, _, body = sec.partition("\n")
            chunks.append(Chunk(path.stem, heading.strip(), f"{doc_title}. {heading.strip()}. {body.strip()}"))
    return chunks


class Retriever:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks or load_chunks()
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
        self.matrix = self.vec.fit_transform(c.text for c in self.chunks)

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        scores = linear_kernel(self.vec.transform([query]), self.matrix).ravel()
        top = scores.argsort()[::-1][:k]
        return [(self.chunks[i], float(scores[i])) for i in top]
