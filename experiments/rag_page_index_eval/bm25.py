import math
import re
from collections import Counter, defaultdict


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: dict[str, Counter[str]] = {}
        self.lengths: dict[str, int] = {}
        self.df: defaultdict[str, int] = defaultdict(int)

    def add(self, doc_id: str, text: str) -> None:
        if doc_id in self.docs:
            raise ValueError(f"duplicate doc_id: {doc_id}")

        counts = Counter(tokenize(text))
        self.docs[doc_id] = counts
        self.lengths[doc_id] = sum(counts.values())
        for term in counts:
            self.df[term] += 1

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if not self.docs:
            return []

        terms = tokenize(query)
        if not terms:
            return []

        avgdl = sum(self.lengths.values()) / max(len(self.lengths), 1)
        n_docs = len(self.docs)
        scored: list[tuple[str, float]] = []

        for doc_id, counts in self.docs.items():
            dl = self.lengths[doc_id] or 1
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if tf == 0:
                    continue

                idf = math.log(1 + (n_docs - self.df[term] + 0.5) / (self.df[term] + 0.5))
                denom = tf + self.k1 * (1 - self.b + self.b * dl / avgdl)
                score += idf * (tf * (self.k1 + 1)) / denom

            scored.append((doc_id, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
