# run_litreview.py
import asyncio, os, json, datetime, traceback
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

async def run_scope(name, spec):
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        os.environ["RETRIEVER"] = spec["retriever"]           # per-scope override
        r = GPTResearcher(query=spec["query"], report_type="detailed_report", verbose=True)
        await r.conduct_research()
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
