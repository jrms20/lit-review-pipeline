# Automated Literature Review Pipeline

A systematic literature review pipeline built on [GPT Researcher](https://github.com/assafelovic/gpt-researcher). It adds three things that vanilla GPT Researcher lacks:

- **Multi-scope parallel search** — runs three conceptually distinct query lenses simultaneously (narrow, adjacent, analogous), so you cover the exact topic, related problem domains, and structural analogues in one pass.
- **Citation snowballing** — starts from known anchor papers and walks their full reference and citation graphs via Semantic Scholar, surfacing papers that keyword search misses.
- **Structured extraction** — a custom prompt forces output into a per-paper evidence table with controlled vocabularies rather than prose summaries, giving you something you can sort and reason over.

The repo ships with a worked example for **Boundary Point Jailbreaking (BPJ) defence research**. Swapping it out for a new topic takes about 15 minutes — see [Adapting for a new topic](#adapting-for-a-new-topic) below.

---

## Files

| File | What it does |
| --- | --- |
| `run_litreview.py` | Main pipeline. Runs three GPT Researcher agents in parallel (narrow / adjacent / analogous scopes), each with a tailored query and retriever weighting. Writes per-scope reports and metadata to `reports/`. |
| `s2_snowball.py` | Semantic Scholar crawler. Starting from a list of seed papers (arXiv IDs or DOIs), harvests their full reference and citation graphs into `s2_corpus.json`. |
| `extraction_prompt.txt` | Structured output schema. Passed as `custom_prompt` to GPT Researcher — forces a per-paper evidence table with controlled vocabularies plus a synthesis section. |
| `consolidate.py` | Merges the three scope reports into `reports/CONSOLIDATED_REVIEW.md` and deduplicates the bibliography across scopes. |
| `smoke_test.py` | Quick sanity check that the retrievers are reachable before you commit to the full pipeline. |
| `audit.py` | Automated post-run quality audit. Runs automatically at the end of `run_litreview.py` and writes `reports/AUDIT_REPORT.md`. Also callable standalone. Checks process health, anchor paper coverage, and uses a fast model to cross-reference each evidence table row against the sources actually retrieved. |
| `verify_citations.py` | Verifies every arXiv ID in the scope reports against the real arXiv API and flags hallucinated citations. Cross-references against `s2_corpus.json` to surface recall gaps. Run after `audit.py`. |
| `.env.example` | Template for the required environment variables. Copy to `.env` and fill in your keys. |

---

## Setup

**Requirements:** Python 3.10+

```bash
git clone <this-repo>
cd <this-repo>

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in your API keys
```

**API keys you need:**

| Key | Where to get it | Required? |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Yes |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | Yes (for embeddings) — or switch to the keyless HuggingFace option in `.env` |
| `TAVILY_API_KEY` | [app.tavily.com](https://app.tavily.com) | Yes — or switch `RETRIEVER` to `duckduckgo,arxiv` in `.env` |

---

## Running

**1. Smoke test** (verify all retrievers are working, costs ~$0.20):

```bash
python smoke_test.py
```

**2. Citation snowball** (harvest reference/citation graphs for your seed papers):

```bash
python s2_snowball.py
# → writes s2_corpus.json
```

**3. Full pipeline** (runs three scopes concurrently with a 60-second stagger, costs ~$3–6):

```bash
python run_litreview.py
# → writes reports/narrow.md, reports/adjacent.md, reports/analogous.md
#   + _sources.json, _meta.json per scope, and AUDIT_REPORT.md
```

**4. Consolidate**:

```bash
python consolidate.py
# → writes reports/CONSOLIDATED_REVIEW.md
```

**5. Verify citations** (optional but recommended before sharing):

```bash
python verify_citations.py
# → checks every arXiv ID against the real arXiv API
```

---

## Adapting for a new topic

The BPJ content is isolated in four places. Change these and the rest of the pipeline is generic:

### 1. `run_litreview.py` — the three scope queries

Edit the `SCOPES` dict near the top of the file. Each scope has a `query` (what GPT Researcher searches for) and a `retriever` (ordering of search backends — put the most relevant one first):

```python
SCOPES = {
    "narrow": {
        "query": "Your exact topic — be specific and verbose for better recall",
        "retriever": "tavily,arxiv,semantic_scholar",
    },
    "adjacent": {
        "query": "A related problem in a neighbouring domain that uses similar methods",
        "retriever": "tavily,semantic_scholar,arxiv",
    },
    "analogous": {
        "query": "A structurally similar problem in a different field",
        "retriever": "arxiv,semantic_scholar,tavily",
    },
}
```

**Tips for writing good scope queries:**

- *Narrow*: your exact research question, including key terminology and the specific variant you care about.
- *Adjacent*: same class of problem but in a different application domain (e.g. if your topic is NLP attacks, adjacent might be image-classifier attacks).
- *Analogous*: structurally similar problem with a different surface form (e.g. anomaly detection literature if your topic involves detecting unusual query patterns).

### 2. `s2_snowball.py` — seed papers

Replace the `SEEDS` list with your anchor papers. You can use arXiv IDs or DOIs:

```python
SEEDS = [
    "arXiv:2301.00001",
    "DOI:10.1145/1234567.1234568",
]
```

If you don't have seed papers yet, skip this script and rely solely on GPT Researcher's keyword search. Run snowballing once you've identified key papers from the initial report.

### 3. `extraction_prompt.txt` — the evidence table schema

Rewrite this prompt for your domain. The structure to keep:

- **PART 1**: a Markdown table with one row per paper and columns relevant to your topic.
- **PART 2**: a synthesis section with guided questions (e.g. "which mechanisms are most transferable to your setting?").
- The rule at the bottom: *only cite real sources from context, write n/a rather than guessing*.

### 4. `consolidate.py` — report title

Change the `TITLE` variable at the top of the file:

```python
TITLE = "Your Topic — Consolidated Literature Review"
```

### 5. `audit.py` — anchor papers

Update the `ANCHORS` list to reflect the landmark papers for your new topic:

```python
ANCHORS = [
    ("key paper title fragment", ["narrow", "analogous"]),
]
```

---

## Cost estimates

| Step | Approximate cost |
| --- | --- |
| Smoke test | ~$0.20 |
| Full pipeline (3 scopes) | ~$3–6 |
| Automated audit | ~$0.05 |
| Snowballing | Free (keyless Semantic Scholar; add a key in `s2_snowball.py` for higher rate limits) |

Costs scale with `MAX_ITERATIONS`, `MAX_SUBTOPICS`, and `TOTAL_WORDS` in `.env`.
