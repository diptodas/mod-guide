"""Loads the community-sourced corpus of insensitive speech and retrieves
the most similar entries for a given input text (the RAG step)."""

from dataclasses import dataclass
from pathlib import Path

import openpyxl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MEDIA_SUFFIXES = (".mp4", ".mov", ".jpg", ".jpeg", ".png", ".txt")


@dataclass
class Entry:
    community: str
    theme: str
    speech: str        # the insensitive statement
    explanation: str   # why the community finds it insensitive


def _text(value) -> str:
    return str(value).strip() if value is not None else ""


def _is_media_reference(text: str) -> bool:
    low = text.lower()
    return low.startswith("http") or low.endswith(MEDIA_SUFFIXES)


def load_corpus(corpus_dir: str) -> list[Entry]:
    """Reads every .xlsx catalogue under <corpus_dir>/<Community>/.

    Expected layout (matches the Minority ARC data folder):
        corpus_dir/Chakma/Catalogue.xlsx
        corpus_dir/Hindu/catalogue.xlsx
    Columns: Theme | Comment | Expert Explanation. Theme cells are carried
    down to the rows below them. Rows without an explanation, or whose
    comment is only a link or a media filename, are skipped.
    """
    root = Path(corpus_dir)
    entries: list[Entry] = []
    if not root.exists():
        return entries

    for community_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for xlsx in sorted(community_dir.glob("*.xlsx")):
            ws = openpyxl.load_workbook(xlsx, read_only=True, data_only=True).worksheets[0]
            theme = ""
            for row in ws.iter_rows(values_only=True):
                cells = list(row)[:3] + [None, None, None]
                theme_cell, speech_cell, expl_cell = (_text(c) for c in cells[:3])
                if theme_cell and theme_cell.lower() not in ("theme",):
                    theme = theme_cell
                if not speech_cell or speech_cell.lower() == "comment":  # header row
                    continue
                if not speech_cell or not expl_cell:
                    continue
                if _is_media_reference(speech_cell):
                    continue
                entries.append(Entry(community_dir.name, theme, speech_cell, expl_cell))
    return entries


DEFAULT_EMBEDDING_MODEL = "distiluse-base-multilingual-cased-v1"  # the paper's model


class Retriever:
    """Retrieves the corpus entries most similar to an input text.

    Default backend: multilingual sentence embeddings (as in the paper), so
    Bengali and English inputs are matched on meaning. Set
    RETRIEVER=tfidf to use character n-gram TF-IDF instead, which needs no
    model download. If sentence-transformers is not installed, the
    embedding backend falls back to TF-IDF with a warning.

    Each (speech, explanation) pair is one document, so the explanation is
    retrieved together with the speech it explains.
    """

    def __init__(self, entries: list[Entry], top_k: int = 2,
                 backend: str = "embeddings", model_name: str = DEFAULT_EMBEDDING_MODEL):
        self.entries = entries
        self.top_k = top_k
        self.backend = None
        self.docs = [f"{e.speech}\n{e.explanation}" for e in entries]
        if not entries:
            return

        if backend == "embeddings":
            try:
                from sentence_transformers import SentenceTransformer

                self.model = SentenceTransformer(model_name)
                self.doc_matrix = self.model.encode(
                    self.docs, normalize_embeddings=True, convert_to_numpy=True
                )
                self.backend = f"embeddings ({model_name})"
                return
            except ImportError:
                print("sentence-transformers not installed; falling back to TF-IDF.")

        # TF-IDF fallback: character n-grams work for Bengali without a tokenizer.
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
        self.doc_matrix = self.vectorizer.fit_transform(self.docs)
        self.backend = "tfidf"

    def search(self, query: str) -> list[tuple[Entry, float]]:
        if self.backend is None or not query.strip():
            return []
        if self.backend.startswith("embeddings"):
            q = self.model.encode([query], normalize_embeddings=True, convert_to_numpy=True)
            scores = (self.doc_matrix @ q.T).ravel()
        else:
            scores = cosine_similarity(self.vectorizer.transform([query]), self.doc_matrix)[0]
        ranked = scores.argsort()[::-1][: self.top_k]
        return [(self.entries[i], float(scores[i])) for i in ranked if scores[i] > 0]
