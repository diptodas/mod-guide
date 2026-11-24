"""Mod-Guide: LLM-based moderation feedback with RAG over a community-sourced corpus.

Run:  uvicorn app:app --reload
Set OPENAI_API_KEY to get LLM feedback. Without it, the app runs in
retrieval-only mode and shows the most relevant community explanations.
"""

import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from corpus import DEFAULT_EMBEDDING_MODEL, Retriever, load_corpus
from personas import PERSONAS, build_messages

CORPUS_DIR = os.environ.get("CORPUS_DIR", "corpus_data")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-6-luna")  # cheapest GPT-6 tier
RETRIEVER_BACKEND = os.environ.get("RETRIEVER", "embeddings")  # "embeddings" or "tfidf"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
TOP_K = int(os.environ.get("TOP_K", "2"))
TEMPERATURE = float(os.environ["TEMPERATURE"]) if os.environ.get("TEMPERATURE") else None
MAX_INPUT_CHARS = 4000

entries = load_corpus(CORPUS_DIR)
retriever = Retriever(entries, top_k=TOP_K, backend=RETRIEVER_BACKEND, model_name=EMBEDDING_MODEL)

app = FastAPI(title="Mod-Guide")


class FeedbackRequest(BaseModel):
    text: str = Field(..., max_length=MAX_INPUT_CHARS)
    persona: str = "teacher"
    use_rag: bool = True


def generate(messages: list[dict]) -> str | None:
    """Returns the LLM reply, or None when no API key is configured."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    from openai import OpenAI  # imported lazily so retrieval-only mode needs no SDK

    client = OpenAI(api_key=api_key)
    kwargs = {"model": MODEL_NAME, "messages": messages}
    # Some models (e.g. gpt-6-luna) accept only the default temperature, so the
    # parameter is sent only when TEMPERATURE is set explicitly.
    if TEMPERATURE is not None:
        kwargs["temperature"] = TEMPERATURE
    response = client.chat.completions.create(**kwargs)
    reply = response.choices[0].message.content or ""
    # Drop a leading "হ্যাঁ।" ("yes.") or "না।" ("no.") that the model sometimes adds before the answer.
    return re.sub(r"^\s*(?:হ্যাঁ|না)[।.]\s*", "", reply)


@app.get("/api/status")
def status():
    communities = sorted({e.community for e in entries})
    return {
        "corpus_entries": len(entries),
        "communities": communities,
        "retriever": retriever.backend or "none",
        "llm_enabled": bool(os.environ.get("OPENAI_API_KEY")),
        "model": MODEL_NAME,
        "personas": {k: v["label"] for k, v in PERSONAS.items()},
    }


@app.post("/api/feedback")
def feedback(req: FeedbackRequest):
    if not req.text.strip():
        raise HTTPException(400, "Enter some text to check.")
    if req.persona not in PERSONAS:
        raise HTTPException(400, f"Unknown persona: {req.persona}")

    passages = retriever.search(req.text) if req.use_rag else []
    sources = [
        {
            "community": e.community,
            "theme": e.theme,
            "speech": e.speech,
            "explanation": e.explanation,
            "score": round(s, 3),
        }
        for e, s in passages
    ]

    messages = build_messages(req.persona, req.text, passages)
    try:
        reply = generate(messages)
    except Exception as exc:  # surface the model's error message to the page
        raise HTTPException(502, f"Model call failed: {exc}")
    if reply is None:
        # Retrieval-only fallback: show the community explanations directly.
        if sources:
            reply = "\n\n".join(s["explanation"] for s in sources)
        else:
            reply = "No closely matching community explanation was found in the corpus."
        mode = "retrieval-only"
    else:
        mode = "llm"

    return {
        "feedback": reply,
        "mode": mode,
        "persona": req.persona,
        "rag": req.use_rag,
        "sources": sources,
    }


@app.get("/api/corpus")
def corpus():
    """The annotated corpus, for the React page. Served only on this machine."""
    return [
        {"community": e.community, "theme": e.theme, "speech": e.speech, "explanation": e.explanation}
        for e in entries
    ]


app.mount("/", StaticFiles(directory="static", html=True), name="static")
