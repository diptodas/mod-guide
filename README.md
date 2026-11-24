# Mod-Guide

A small version of the Mod-Guide system from the COMPASS '26 paper: an LLM-based
content moderation feedback tool that uses retrieval-augmented generation (RAG)
over a corpus of insensitive speech annotated by Hindu and Chakma community members.

## What it does

1. **Corpus**: loads the annotated `.xlsx` catalogues (speech + community explanation)
   from `corpus_data/<Community>/`.
2. **Retrieval (RAG)**: for each input text, finds the most similar corpus entries
   using multilingual sentence embeddings (`distiluse-base-multilingual-cased-v1`,
   the paper's model), top-k = 2 by default. Character n-gram TF-IDF is the fallback.
3. **Persona prompting**: five moderator roles (teacher, mediator, judge,
   representative, protector), as in the paper.
4. **Generation**: sends the persona, the retrieved community explanations and the
   input to an OpenAI model and returns feedback in Bengali.
5. **Retrieval-only fallback**: with no API key, it shows the retrieved explanations.

The web page lets you pick a persona and turn RAG on or off, so you can compare the
standalone LLM with the RAG-grounded version, as the paper's evaluation does.

## Quick start (Mac, no terminal needed)

1. Install Python 3.10 or newer from https://www.python.org/downloads/ (skip if already installed).
2. Copy the two catalogues into `corpus_data/` as described under Setup below.
3. Double-click `start.command`. The first run takes several minutes while it installs
   everything and downloads the embedding model. The browser opens by itself at
   http://127.0.0.1:8000.
4. To use LLM feedback, create a file named `config.env` in this folder containing one line:
   `OPENAI_API_KEY=your-key-here`. Keep this file private and never share it.
5. To stop the app, close the Terminal window that opened.

If macOS blocks the file, right-click it, choose Open, and confirm.

## Setup

```bash
cd mod-guide
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy the catalogues into place (from the Minority ARC data folder):
#   corpus_data/Chakma/Catalogue.xlsx
#   corpus_data/Hindu/catalogue.xlsx

export OPENAI_API_KEY=sk-...        # optional; omit for retrieval-only mode
export MODEL_NAME=gpt-6-luna          # optional; default is the cheapest GPT-6 tier. The paper used gpt-4
# export TEMPERATURE=0.2             # optional; leave unset for models that accept only the default
# The first run downloads the embedding model (several hundred MB).
# Set RETRIEVER=tfidf to skip it and use TF-IDF instead.
uvicorn app:app --reload
```

Open http://127.0.0.1:8000.

## API

- `GET /api/status`: corpus size, communities, LLM on or off, personas.
- `POST /api/feedback` with `{"text": "...", "persona": "teacher", "use_rag": true}`.

## Differences from the paper

- The paper used a React front end. This version uses plain HTML and JavaScript.
- Retrieval uses the paper's multilingual sentence embeddings. Set `RETRIEVER=tfidf`
  for the lighter character n-gram TF-IDF alternative.
- The paper split documents into 512-character chunks. Here each speech and
  explanation pair stays as one document.
- The evaluation pipeline (BERTScore comparisons, expert review, user study) is not included.
- The paper translated all content into Bengali. Here the input can be in any
  language, and the model is asked to reply in Bengali.

## Notes

The corpus is small and drawn from one set of community members. Its explanations
are perspectives, not ground truth. The paper notes that moderation decisions, even
when community-informed, can essentialise minority identities, so outputs should be
reviewed by people before they are used.

## Data and privacy

The `corpus_data/` folder holds community-written content, including hateful wording, and
it was collected under a research consent process. It is excluded from version control
(see `.gitignore`), and the offline HTML file that embeds it is excluded too. Before sharing
the corpus, check the ethics terms for the study. Never commit `config.env`, which holds the
OpenAI API key.
