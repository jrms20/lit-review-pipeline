# run_litreview.py
import asyncio, os, json, re, datetime, traceback
from pathlib import Path
from dotenv import load_dotenv
from gpt_researcher import GPTResearcher
load_dotenv()

OUT = Path("reports"); OUT.mkdir(exist_ok=True)
EXTRACTION_PROMPT = Path("extraction_prompt.txt").read_text()

# Per-scope: query + retriever weighting. Replace these with your own topic queries.
SCOPES = {
    "narrow": {
        "query": "Defences against iterative black-box jailbreak attacks on LLM safety "
                 "classifiers relying only on binary flagged/not-flagged feedback and high "
                 "query volume: single-interaction defences (probe-based classifiers, "
                 "randomised classifier ensembles, adversarial training on jailbreak strings) "
                 "AND cross-interaction defences (account-level flag-rate monitoring, "
                 "session/batch detection of automated jailbreak campaigns, query-budget and "
                 "rate-limiting). Include Constitutional Classifiers and production-grade "
                 "follow-ons.",
        "retriever": "tavily,arxiv,semantic_scholar",
    },
    "adjacent": {
        "query": "Batch-level and streaming anomaly detection and statistical process control "
                 "(CUSUM, EWMA, control charts, SPRT, change-point detection) for API abuse, "
                 "fraud/bot detection, and model-extraction defence; session/account-level "
                 "behavioural monitoring to detect automated adversarial query campaigns against "
                 "ML APIs; detecting elevated rejection/anomaly rates across many interactions.",
        "retriever": "tavily,semantic_scholar,arxiv",
    },
    "analogous": {
        "query": "Decision-based hard-label black-box adversarial attacks on image classifiers in "
                 "the Boundary Attack lineage (Boundary Attack, HopSkipJumpAttack, OPT/Sign-OPT) "
                 "and the DEFENCES and DETECTORS against them: stateful/cross-query detection, "
                 "query-similarity detection, randomised near-boundary query rejection, "
                 "query-budget defences against high-volume single-bit boundary probing.",
        "retriever": "arxiv,semantic_scholar,tavily",
    },
}

S2_CORPUS = Path("s2_corpus.json")

def _s2_context_from_sources(name: str) -> list[str]:
    """Build Title/Content/Source context from s2_corpus using arxiv IDs in sources.json."""
    sources_path = OUT / f"{name}_sources.json"
    if not sources_path.exists() or not S2_CORPUS.exists():
        return []
    sources = json.loads(sources_path.read_text())
    arxiv_ids = set()
    for s in sources:
        m = re.search(r"arxiv\.org/(?:pdf|abs|html)/(\d{4}\.\d+)", s.get("url", ""))
        if m:
            arxiv_ids.add(m.group(1))
    if not arxiv_ids:
        return []
    corpus = json.loads(S2_CORPUS.read_text())
    by_id = {p.get("externalIds", {}).get("ArXiv", ""): p for p in corpus}
    chunks = []
    for aid in arxiv_ids:
        p = by_id.get(aid)
        if p and p.get("abstract"):
            url = p.get("url") or f"https://arxiv.org/abs/{aid}"
            chunks.append(f"Title: {p['title']}\nContent: {p['abstract']}\nSource: {url}")
    return chunks


async def run_scope(name, spec):
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        os.environ["RETRIEVER"] = spec["retriever"]           # per-scope override
        r = GPTResearcher(query=spec["query"], report_type="research_report", verbose=True)
        await r.conduct_research()

        # Always prepend s2 abstracts so the LLM has real paper content even when
        # CURATE_SOURCES strips arxiv-PDF entries (which arrive with blank titles and
        # fail the credibility filter, leaving hollow shell entries in r.context).
        s2_chunks = _s2_context_from_sources(name)
        if s2_chunks:
            print(f"[{name}] Prepending {len(s2_chunks)} s2 abstracts to context")
            r.context = s2_chunks + list(r.context or [])

        report = await r.write_report(custom_prompt=EXTRACTION_PROMPT)

        (OUT / f"{name}.md").write_text(report)
        (OUT / f"{name}_sources.json").write_text(json.dumps(r.get_research_sources(), indent=2))
        (OUT / f"{name}_meta.json").write_text(json.dumps(
            {"scope": name, "finished": ts, "costs": r.get_costs(),
             "source_urls": r.get_source_urls()}, indent=2))
        print(f"[{name}] DONE @ {ts}  costs={r.get_costs()}")
        return name, "ok"
    except Exception as e:
        (OUT / f"{name}_ERROR.txt").write_text(f"{ts}\n{traceback.format_exc()}")
        print(f"[{name}] FAILED @ {ts}: {e}")
        return name, f"error: {e}"

STAGGER_SECONDS = 60  # delay between scope launches to avoid API burst

async def main():
    tasks = []
    for i, (name, spec) in enumerate(SCOPES.items()):
        if i > 0:
            print(f"[stagger] waiting {STAGGER_SECONDS}s before launching {name}...")
            await asyncio.sleep(STAGGER_SECONDS)
        tasks.append(asyncio.create_task(run_scope(name, spec)))
    results = await asyncio.gather(*tasks)
    print("SUMMARY:", dict(results))

    print("\nRunning automated audit...")
    from audit import run_audit
    run_audit()

if __name__ == "__main__":
    asyncio.run(main())
