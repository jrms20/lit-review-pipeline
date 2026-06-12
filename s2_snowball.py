# s2_snowball.py — harvest references + citations for seed papers via Semantic Scholar
import time, json, requests

S2 = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,year,externalIds,abstract,authors,venue,url"
HEADERS = {}  # add {"x-api-key": "YOUR_S2_KEY"} if you have one (raises rate limits)

# Full S2-format IDs: use "arXiv:{id}" or "DOI:{doi}" — the API accepts both.
SEEDS = [
    # Original anchors (BPJ paper, CC++, Boundary Attack lineage)
    "arXiv:2602.15001",
    "arXiv:2601.04603",
    "arXiv:1712.04248",
    "arXiv:1904.02144",
    "arXiv:1807.04457",
    # Added seeds
    "arXiv:2310.03684",
    "DOI:10.1038/s42256-023-00765-8",
    "arXiv:2311.09096",
    "arXiv:2402.08983",
    "arXiv:2403.04783",
    "arXiv:2605.31593",
]

def get_paper(s2_id):
    while True:
        r = requests.get(f"{S2}/paper/{s2_id}",
                         params={"fields": FIELDS}, headers=HEADERS, timeout=30)
        if r.status_code == 429:
            print(f"  429 on {s2_id}, waiting 5s...")
            time.sleep(5); continue
        r.raise_for_status()
        return r.json()

def get_edges(paper_id, kind):  # kind in {"references","citations"}
    out, offset = [], 0
    while True:
        r = requests.get(f"{S2}/paper/{paper_id}/{kind}",
                         params={"fields": FIELDS, "limit": 100, "offset": offset},
                         headers=HEADERS, timeout=30)
        if r.status_code == 429:        # be polite to the shared pool
            time.sleep(3); continue
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data: break
        out += [d.get("citedPaper") or d.get("citingPaper") for d in data]
        offset += 100
        if offset >= 1000: break
        time.sleep(1)
    return out

corpus = {}
for seed_id in SEEDS:
    p = get_paper(seed_id)
    pid = p["paperId"]
    corpus[pid] = p
    for kind in ("references", "citations"):
        for nb in get_edges(pid, kind):
            if nb and nb.get("paperId"):
                corpus.setdefault(nb["paperId"], nb)
        time.sleep(1)

with open("s2_corpus.json", "w") as f:
    json.dump(list(corpus.values()), f, indent=2)
print(f"Harvested {len(corpus)} unique papers -> s2_corpus.json")
