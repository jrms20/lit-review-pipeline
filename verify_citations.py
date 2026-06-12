# verify_citations.py
# After the overnight run: extract every arXiv ID from the scope reports,
# verify each one against the real arXiv API, and cross-reference against
# s2_corpus.json (if it exists) to surface recall gaps.
import re, time, json, sys
from pathlib import Path
import requests

ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_ID_RE = re.compile(r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b")

REPORT_FILES = [
    Path("reports/narrow.md"),
    Path("reports/adjacent.md"),
    Path("reports/analogous.md"),
    Path("reports/CONSOLIDATED_REVIEW.md"),
]

def check_arxiv(arxiv_id):
    clean_id = re.sub(r"v\d+$", "", arxiv_id)
    r = requests.get(ARXIV_API, params={"id_list": clean_id}, timeout=15)
    r.raise_for_status()
    total = re.search(
        r"<opensearch:totalResults[^>]*>(\d+)</opensearch:totalResults>", r.text
    )
    if total and int(total.group(1)) == 0:
        return None, False
    title = re.search(r"<entry>.*?<title>(.*?)</title>", r.text, re.DOTALL)
    return (title.group(1).strip() if title else "(title unavailable)"), True

def main():
    all_ids: dict[str, list[str]] = {}
    for path in REPORT_FILES:
        if not path.exists():
            continue
        for id_ in ARXIV_ID_RE.findall(path.read_text()):
            all_ids.setdefault(id_, []).append(path.name)

    if not all_ids:
        print("No reports found or no arXiv IDs detected — run the pipeline first.")
        sys.exit(0)

    print(f"Found {len(all_ids)} unique arXiv IDs. Verifying against arXiv API...\n")

    verified, failed = [], []
    for arxiv_id in sorted(all_ids):
        title, ok = check_arxiv(arxiv_id)
        if ok:
            verified.append((arxiv_id, title))
            print(f"  ✓  {arxiv_id}  —  {title[:72]}")
        else:
            failed.append(arxiv_id)
            sources = ", ".join(all_ids[arxiv_id])
            print(f"  ✗  {arxiv_id}  —  NOT FOUND  (in: {sources})")
        time.sleep(0.5)

    # Cross-reference against s2_corpus.json to surface recall gaps
    corpus_path = Path("s2_corpus.json")
    missing_from_reports: list[str] = []
    if corpus_path.exists():
        corpus = json.loads(corpus_path.read_text())
        corpus_arxiv_ids = {
            p["externalIds"]["ArXiv"]
            for p in corpus
            if (p.get("externalIds") or {}).get("ArXiv")
        }
        report_ids_clean = {re.sub(r"v\d+$", "", i) for i in all_ids}
        missing_from_reports = sorted(corpus_arxiv_ids - report_ids_clean)

    print(f"\n--- SUMMARY ---")
    print(f"  Verified : {len(verified)}")
    print(f"  Not found: {len(failed)}  {'<-- hallucinations to remove' if failed else '(none)'}")
    if failed:
        print(f"  Remove   : {', '.join(failed)}")
    if missing_from_reports:
        print(f"\n  In s2_corpus.json but not cited in any report ({len(missing_from_reports)} papers):")
        for id_ in missing_from_reports[:20]:
            print(f"    arXiv:{id_}")
        if len(missing_from_reports) > 20:
            print(f"    ... and {len(missing_from_reports) - 20} more (run with full output to see all)")

if __name__ == "__main__":
    main()
