# Automated Literature Review Pipeline

A systematic literature review pipeline built on [GPT Researcher](https://github.com/assafelovic/gpt-researcher). It adds three things that vanilla GPT Researcher lacks:

- **Multi-scope parallel search** — runs three conceptually distinct query lenses simultaneously (narrow, adjacent, analogous), so you cover the exact topic, related problem domains, and structural analogues in one pass.
- **Citation snowballing** — starts from known anchor papers and walks their full reference and citation graphs via Semantic Scholar, surfacing papers that keyword search misses.
- **Structured extraction** — a custom prompt forces output into a per-paper evidence table with controlled vocabularies rather than prose summaries, giving you something you can sort and reason over.

The repo ships with a worked example for **Boundary Point Jailbreaking (BPJ) defence research**. Swapping it out for a new topic takes about 15 minutes — see [Adapting for a new topic](#adapting-for-a-new-topic) below.

> **Note:** The `reports/` directory is git-ignored. To share outputs with collaborators, copy the relevant files out of `reports/` or push them to a shared drive separately.

---

## Files

| File | What it does |
| --- | --- |
| `run_litreview.py` | Main pipeline. Runs three GPT Researcher agents concurrently with a 60-second stagger (narrow / adjacent / analogous scopes), each with a tailored query and retriever weighting. Writes per-scope reports and metadata to `reports/`. |
| `s2_snowball.py` | Semantic Scholar crawler. Starting from a list of seed papers (arXiv IDs or DOIs), harvests their full reference and citation graphs into `s2_corpus.json`. |
| `extraction_prompt.txt` | Structured output schema. Passed as `custom_prompt` to GPT Researcher — forces a per-paper evidence table with controlled vocabularies plus a synthesis section. |
| `consolidate.py` | Merges the three scope reports into `reports/CONSOLIDATED_REVIEW.md` and deduplicates the bibliography across scopes. |
| `smoke_test.py` | Quick sanity check that the retrievers are reachable before you commit to the full pipeline. |
| `audit.py` | Automated post-run quality audit. Runs automatically at the end of `run_litreview.py` and writes `reports/AUDIT_REPORT.md`. Also callable standalone. Checks process health, anchor paper coverage, and uses a fast model to cross-reference each evidence table row against the sources actually retrieved. |
| `verify_citations.py` | Verifies every arXiv ID in the scope reports against the real arXiv API and flags hallucinated citations. Cross-references against `s2_corpus.json` to surface recall gaps. Run after the main pipeline. |
| `rerun_failed.py` | Recovery script. Auto-detects any scopes that failed during `run_litreview.py` (by scanning `reports/` for `*_ERROR.txt` files) and reruns just those scopes, then re-runs the audit. |
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
# open .env and fill in your API keys (see table below)
```

**API keys you need:**

| Key | Where to get it | Required? |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Yes |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | Yes (for embeddings) — or switch to the keyless HuggingFace option in `.env` |
| `TAVILY_API_KEY` | [app.tavily.com](https://app.tavily.com) | Yes — or switch `RETRIEVER` to `duckduckgo,arxiv,semantic_scholar` in `.env` |

Once your keys are in `.env`, proceed to Step 0.

---

## Running the pipeline

### Step 0 — Smoke test (recommended, ~$0.20)

Verify that all retrievers are reachable and your API keys are valid before committing to the full run:

```bash
python smoke_test.py
```

**Expected output:** A short report (3–5 paragraphs on a test search topic) followed by a `COSTS:` line. The test completes in about 2 minutes.

**If this fails:** See [Troubleshooting](#troubleshooting) below. The most common cause is a wrong API key format or a retriever that isn't reachable from your network.

---

### Step 1 — Citation snowball

Harvest reference and citation graphs for your seed papers from Semantic Scholar:

```bash
python s2_snowball.py
# → writes s2_corpus.json  (this file is git-ignored)
```

**Expected output:**

```
Harvested 284 unique papers -> s2_corpus.json
```

**Why this step matters:** The pipeline injects the S2 abstracts directly into the LLM context before writing each report. This compensates for a known GPT Researcher limitation where arXiv PDF sources are discarded during source curation because they often arrive with blank title metadata (see [Troubleshooting](#empty-or-very-short-reports) for details). Running this step first means your arXiv papers are represented by their full abstracts rather than blank stubs.

You can skip this step if you have no seed papers yet. The pipeline will still run, but report quality for arXiv-heavy topics will be lower.

---

### Step 2 — Full pipeline (~$3–6, takes 20–40 min)

Runs all three scopes concurrently with a 60-second stagger between launches:

```bash
python run_litreview.py
```

**Expected output:**

```
[stagger] waiting 60s before launching adjacent...
[stagger] waiting 60s before launching analogous...
[narrow] Prepending 8 s2 abstracts to context
[narrow] DONE @ 2026-06-12T10:30:00  costs={'total_cost': 1.23}
[adjacent] DONE @ 2026-06-12T10:52:00  costs={'total_cost': 0.98}
[analogous] DONE @ 2026-06-12T11:14:00  costs={'total_cost': 1.41}
SUMMARY: {'narrow': 'ok', 'adjacent': 'ok', 'analogous': 'ok'}

Running automated audit...
Audit report written to reports/AUDIT_REPORT.md
```

Each successful scope writes three files:
- `reports/<scope>.md` — the evidence table report
- `reports/<scope>_sources.json` — full list of URLs retrieved
- `reports/<scope>_meta.json` — timing and cost metadata

**If a scope fails** it writes `reports/<scope>_ERROR.txt` instead of the `.md` file. Proceed to Step 2a; otherwise skip it.

> **`report_type`:** The pipeline uses `research_report` (cheaper, well-suited to structured extraction via the custom prompt). To switch to longer, more discursive prose, change `report_type` to `detailed_report` in `run_litreview.py` — expect roughly 2–3× the cost.

---

### Step 2a — Rerun failed scopes (only if needed)

If any scope wrote an `_ERROR.txt` file, rerun only those scopes:

```bash
python rerun_failed.py
```

The script auto-detects which scopes failed, reruns them with the same 60-second stagger, and runs the audit again once complete. You do not need to edit anything — it reads the `*_ERROR.txt` filenames to know what to retry.

---

### Step 3 — Verify citations

Check every arXiv ID in the reports against the real arXiv API:

```bash
python verify_citations.py
```

**Expected output:**

```
[OK]   2310.04451 — "Jailbreaking Black Box Large Language Models in Twenty Queries"
[OK]   2302.05733 — "Not What You've Signed Up For: ..."
[FAIL] 2501.18638 — NOT FOUND (possible hallucination)
...
Summary: 40 OK, 2 FAIL
```

**What to do with failures:** Open the relevant `reports/<scope>.md`, find the row containing that arXiv ID, and remove it. Hallucinated citations occasionally occur with any LLM-driven pipeline; this step is specifically designed to catch them. The script also reports the actual paper title for citations where the ID is real but the pipeline cited the wrong paper — compare the title it finds against the paper name in your evidence table.

> The script may print `[rate-limited, waiting Ns]` between checks — the arXiv API throttles bulk requests. This is normal and resolves automatically; a full pass over ~40 citations takes 3–8 minutes.

---

### Step 4 — Consolidate

Merge all three scope reports into a single document:

```bash
python consolidate.py
# → writes reports/CONSOLIDATED_REVIEW.md
```

**Expected output:** A confirmation line with the total paper count and output path.

---

## Understanding the outputs

After a complete run, `reports/` contains:

| File | What to read it for |
| --- | --- |
| `narrow.md` / `adjacent.md` / `analogous.md` | Per-scope evidence tables (raw pipeline output) |
| `CONSOLIDATED_REVIEW.md` | All three scopes merged, bibliography deduplicated |
| `AUDIT_REPORT.md` | Pipeline quality check — read this first to spot coverage gaps or retrieval failures |
| `*_sources.json` | Full list of URLs retrieved per scope (useful for debugging retrieval gaps) |

---

## Adapting for a new topic

The BPJ content is isolated in five places. Change these and the rest of the pipeline is generic.

### 1. `run_litreview.py` — the three scope queries

Edit the `SCOPES` dict near the top of the file:

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

**Tips:**
- *Narrow*: your exact research question, including key terminology and the specific variant you care about.
- *Adjacent*: same class of problem in a different application domain.
- *Analogous*: structurally similar problem with a different surface form (e.g. anomaly detection literature if your topic involves detecting unusual query patterns).

### 2. `s2_snowball.py` — seed papers

Replace the `SEEDS` list with your anchor papers (arXiv IDs or DOIs):

```python
SEEDS = [
    "arXiv:2301.00001",
    "DOI:10.1145/1234567.1234568",
]
```

If you don't have seed papers yet, leave this empty and rely on GPT Researcher's keyword search first. Add seeds once you've identified key papers from the initial report.

### 3. `extraction_prompt.txt` — the evidence table schema

Rewrite this for your domain. Keep the same structure:
- **PART 1**: Markdown table, one row per paper, columns relevant to your topic.
- **PART 2**: Synthesis section with guided questions.
- The instruction at the bottom: *only cite sources from context; write n/a rather than guessing*.

### 4. `consolidate.py` — report title

Change the `TITLE` variable at the top:

```python
TITLE = "Your Topic — Consolidated Literature Review"
```

### 5. `audit.py` — anchor papers

Update `ANCHORS` to the landmark papers for your topic:

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
| Citation verification | ~$0.00 (arXiv API is free) |
| Snowballing | Free (Semantic Scholar API is keyless at default rate limits) |

Costs scale with `MAX_ITERATIONS`, `MAX_SUBTOPICS`, and `TOTAL_WORDS` in `.env`. The defaults in `.env.example` match the settings used in the BPJ worked example.

---

## Troubleshooting

### Empty or very short reports

**Symptom:** `reports/<scope>.md` is a stub, has no paper rows, or is much shorter than expected.

**Root cause:** `CURATE_SOURCES=true` in your `.env`. When this is enabled, GPT Researcher applies a credibility filter that discards any source whose title field is blank. arXiv PDF URLs almost always arrive with blank title metadata when scraped — so the entire arXiv retriever is effectively silenced, leaving the LLM with little or no context to write from.

**Fix:** Set `CURATE_SOURCES=false` in your `.env`. This is the default in `.env.example`. If you already ran s2_snowball.py first, the S2 injection step will have added abstracts directly to the LLM context regardless — but `CURATE_SOURCES=false` is still the safer default.

---

### A scope writes an `_ERROR.txt` instead of a report

**Symptom:** After `run_litreview.py`, you find `reports/narrow_ERROR.txt` (or adjacent/analogous) but no corresponding `.md`.

**Cause:** Usually a network timeout, a transient API error, or a GPT Researcher internal error mid-run.

**Fix:** Run `python rerun_failed.py`. It reads all `*_ERROR.txt` filenames automatically and reruns only those scopes. If the same scope fails again, open the `_ERROR.txt` file for the full Python traceback.

---

### `verify_citations.py` is slow or prints "rate-limited"

**Symptom:** The script pauses 10–80 seconds between checks, printing `[rate-limited, waiting Ns]`.

**Cause:** The arXiv API throttles bulk requests with HTTP 429. The script retries automatically with exponential backoff.

**Fix:** Nothing to do — let it run. A full pass over ~40 citations typically takes 3–8 minutes. If it hangs for more than 15 minutes without making progress, your network may be blocking the arXiv API endpoint (`export.arxiv.org`).

---

### Hallucinated citations appear in the reports

**Symptom:** `verify_citations.py` prints `[FAIL] ... NOT FOUND` for one or more arXiv IDs.

**Cause:** LLMs occasionally generate plausible-looking but non-existent paper identifiers. This is not specific to this pipeline — it affects any LLM-driven literature review. In practice the rate is low (the BPJ run found 2 hallucinations out of 42 citations).

**Fix:** Grep for the failing arXiv ID in the relevant scope report and delete that row from the evidence table. Also watch for wrong-paper citations: `verify_citations.py` prints the actual arXiv title it finds, which you can compare against what the report claims the paper is called.

---

### `consolidate.py` fails with `FileNotFoundError`

**Symptom:** Error like `FileNotFoundError: [Errno 2] No such file or directory: 'reports/narrow.md'`.

**Cause:** The `reports/` folder has been renamed or moved (e.g., to archive a previous run).

**Fix:** Rename the folder back to `reports/` before running `consolidate.py`. To archive a previous run, copy the files to a separate folder first, then rename back.

---

### Smoke test crashes with "BaseRetriever.invoke() missing input"

**Symptom:** `smoke_test.py` raises a `BaseRetriever` error referencing the `arxiv` retriever.

**Cause:** A known version incompatibility between certain `gpt-researcher` releases and the `arxiv` retriever plugin.

**Fix:** Remove `arxiv` from `RETRIEVER` in your `.env` (e.g., `RETRIEVER=tavily,semantic_scholar`) and rerun the smoke test. The arxiv retriever is supplemental — the pipeline's primary retrieval comes from Tavily and Semantic Scholar.
