# consolidate.py
import json
from pathlib import Path

OUT = Path("reports")
scopes = ["narrow", "adjacent", "analogous"]

TITLE = "Consolidated Literature Review"  # ← change for your topic
master = [f"# {TITLE}\n"]
for s in scopes:
    md = OUT / f"{s}.md"
    master.append(f"\n\n---\n\n# Scope: {s.upper()}\n")
    master.append(md.read_text() if md.exists() else f"_({s} did not complete — see {s}_ERROR.txt)_")

# Deduped bibliography across scopes (normalise by URL; swap to arXiv-ID/DOI for tighter dedup)
seen, biblio = {}, []
for s in scopes:
    f = OUT / f"{s}_sources.json"
    if not f.exists(): continue
    for src in json.loads(f.read_text()):
        key = (src.get("url") or src.get("title") or "").strip().lower()
        if key and key not in seen:
            seen[key] = True
            biblio.append(src)

master.append("\n\n---\n\n# Master Bibliography (deduped)\n")
master.append(f"\n_{len(biblio)} unique sources across all scopes._\n\n")
for b in sorted(biblio, key=lambda x: (x.get("title") or "").lower()):
    master.append(f"- **{b.get('title','(untitled)')}** — {b.get('url','')}\n")

Path("reports/CONSOLIDATED_REVIEW.md").write_text("".join(master))
print("Wrote reports/CONSOLIDATED_REVIEW.md")
