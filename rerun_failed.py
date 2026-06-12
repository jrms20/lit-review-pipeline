# rerun_failed.py — re-run any scopes that wrote an _ERROR.txt during the main pipeline run.
import asyncio
from dotenv import load_dotenv
load_dotenv()

from run_litreview import OUT, SCOPES, run_scope

STAGGER_SECONDS = 60

def detect_failed_scopes() -> list[str]:
    failed = [p.stem.removesuffix("_ERROR") for p in OUT.glob("*_ERROR.txt")]
    known = [name for name in failed if name in SCOPES]
    unknown = [name for name in failed if name not in SCOPES]
    if unknown:
        print(f"[warn] Ignoring unrecognised error files: {unknown}")
    return sorted(known)

async def main():
    targets = detect_failed_scopes()
    if not targets:
        print("No _ERROR.txt files found in reports/ — nothing to rerun.")
        return
    print(f"Rerunning failed scopes: {targets}")
    tasks = []
    for i, name in enumerate(targets):
        if i > 0:
            print(f"[stagger] waiting {STAGGER_SECONDS}s before launching {name}...")
            await asyncio.sleep(STAGGER_SECONDS)
        tasks.append(asyncio.create_task(run_scope(name, SCOPES[name])))
    results = await asyncio.gather(*tasks)
    print("RERUN SUMMARY:", dict(results))

    print("\nRunning automated audit...")
    from audit import run_audit
    run_audit()

if __name__ == "__main__":
    asyncio.run(main())
