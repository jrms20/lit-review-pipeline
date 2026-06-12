# audit.py
# Post-run quality audit. Called automatically by run_litreview.py after all
# scopes finish, or run standalone: python3 audit.py
import json, re
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

OUT = Path("reports")
SCOPES = ["narrow", "adjacent", "analogous"]
AUDIT_MODEL = "claude-haiku-4-5-20251001"

# Anchor papers and which scopes they are expected to surface in
ANCHORS = [
    ("blacklight",               ["narrow", "adjacent", "analogous"]),
    ("stateful detection",       ["narrow", "adjacent", "analogous"]),
    ("hopskipjump",              ["analogous"]),
    ("boundary attack",          ["analogous"]),
    ("oars",                     ["narrow", "analogous"]),
    ("constitutional classifier",["narrow"]),
    ("prada",                    ["adjacent"]),
]


# ── Layer 1: process health ─────────────────────────────────────────────────

def _process_health():
    rows = []
    for scope in SCOPES:
        if (OUT / f"{scope}_ERROR.txt").exists():
            rows.append((scope, "FAILED", "—", "—"))
            continue
        if not (OUT / f"{scope}.md").exists():
            rows.append((scope, "MISSING", "—", "—"))
            continue
        meta_path = OUT / f"{scope}_meta.json"
        if meta_path.exists():
            m = json.loads(meta_path.read_text())
            rows.append((scope, "OK", m.get("costs", "?"), len(m.get("source_urls", []))))
        else:
            rows.append((scope, "OK", "?", "?"))
    return rows


# ── Layer 2: anchor paper coverage ─────────────────────────────────────────

def _anchor_coverage():
    hits: dict[str, list[str]] = {a: [] for a, _ in ANCHORS}
    for scope in SCOPES:
        # Search report text (primary) + sources.json with normalised separators (fallback)
        texts = []
        report_p = OUT / f"{scope}.md"
        if report_p.exists():
            texts.append(report_p.read_text().lower())
        sources_p = OUT / f"{scope}_sources.json"
        if sources_p.exists():
            # normalise hyphens/underscores to spaces so URL fragments match
            texts.append(re.sub(r"[-_]", " ", sources_p.read_text().lower()))
        combined = "\n".join(texts)
        for anchor, _ in ANCHORS:
            if anchor in combined:
                hits[anchor].append(scope)
    return hits


# ── Layer 3: LLM audit of evidence tables ───────────────────────────────────

def _extract_table(report_text: str) -> str:
    m = re.search(
        r"(\|[^\n]*citation[^\n]*\|(?:\n\|[^\n]+\|)+)",
        report_text, re.IGNORECASE,
    )
    return m.group(0) if m else ""


def _llm_audit_scope(scope: str, client: anthropic.Anthropic) -> dict | None:
    report_path = OUT / f"{scope}.md"
    sources_path = OUT / f"{scope}_sources.json"
    if not report_path.exists():
        return None

    table = _extract_table(report_path.read_text())
    if not table:
        return {
            "overall": "WARN",
            "reason": "No evidence table found — extraction_prompt may not have fired correctly",
            "rows": [],
            "vocab_violations": [],
            "high_relevance_assessment": [],
        }

    sources: list[str] = []
    if sources_path.exists():
        for s in json.loads(sources_path.read_text()):
            t, u = s.get("title", ""), s.get("url", "")
            if t or u:
                sources.append(f"{t} | {u}")

    prompt = f"""Audit this literature review evidence table against the sources that were actually retrieved.

RETRIEVED SOURCES (what the model had access to when writing the report):
{chr(10).join(sources[:60])}

EVIDENCE TABLE:
{table[:6000]}

Return ONLY a JSON object with this exact structure — no prose, no markdown fences:
{{
  "overall": "PASS|WARN|FAIL",
  "reason": "one sentence summary",
  "rows": [
    {{"citation": "Author et al. YEAR", "backed": true, "note": "matching source title or URL"}}
  ],
  "vocab_violations": ["list only actual violations of the controlled vocabularies"],
  "high_relevance_assessment": [
    {{"citation": "Author et al. YEAR", "justified": true, "reason": "one sentence"}}
  ]
}}

Rules:
- Set backed=true only when you can point to a retrieved source with a clearly matching title or URL.
- Include ALL rows from the table in "rows".
- Only include rows where bpj_relevance=high in "high_relevance_assessment".
- Set overall=WARN if more than 20% of rows are unbacked; FAIL if more than 40% are unbacked."""

    resp = client.messages.create(
        model=AUDIT_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    block = resp.content[0]
    text = block.text if hasattr(block, "text") else ""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {
        "overall": "WARN",
        "reason": "Could not parse LLM response",
        "rows": [],
        "vocab_violations": [],
        "high_relevance_assessment": [],
        "_raw": text[:500],
    }


# ── Report assembly ──────────────────────────────────────────────────────────

def run_audit(verbose: bool = True) -> Path:
    client = anthropic.Anthropic()
    lines: list[str] = ["# AUDIT REPORT\n\n"]

    # Layer 1
    health = _process_health()
    if verbose:
        print("\n=== Layer 1: Process health ===")
    lines.append("## Process Health\n\n| scope | status | cost ($) | sources |\n|---|---|---|---|\n")
    for scope, status, cost, nsrc in health:
        lines.append(f"| {scope} | {status} | {cost} | {nsrc} |\n")
        if verbose:
            print(f"  {scope}: {status}  cost={cost}  sources={nsrc}")
    lines.append("\n")

    # Layer 2
    coverage = _anchor_coverage()
    if verbose:
        print("\n=== Layer 2: Anchor paper coverage ===")
    lines.append("## Anchor Paper Coverage\n\n")
    for anchor, expected in ANCHORS:
        found = coverage.get(anchor, [])
        mark = "✓" if found else "✗"
        missing_from = [s for s in expected if s not in found]
        detail = f"found in: {', '.join(set(found))}" if found else "**NOT FOUND in any scope**"
        if missing_from:
            detail += f"  _(expected also in: {', '.join(missing_from)})_"
        lines.append(f"- {mark} `{anchor}`: {detail}\n")
        if verbose:
            print(f"  {mark}  {anchor}: {', '.join(set(found)) if found else 'NOT FOUND'}")
    lines.append("\n")

    # Layer 3
    if verbose:
        print("\n=== Layer 3: LLM audit of evidence tables ===")
    lines.append("## Evidence Table Audit\n\n")
    ok_scopes = [scope for scope, status, _, _ in health if status == "OK"]

    for scope in ok_scopes:
        if verbose:
            print(f"  Auditing {scope}...")
        result = _llm_audit_scope(scope, client)
        lines.append(f"### {scope.upper()}\n\n")
        if not result:
            lines.append("_Scope did not complete._\n\n")
            continue

        overall = result.get("overall", "?")
        reason = result.get("reason", "")
        rows = result.get("rows", [])
        backed = sum(1 for r in rows if r.get("backed"))
        unbacked = len(rows) - backed

        lines.append(f"**{overall}** — {reason}\n\n")
        lines.append(f"Rows: {backed} source-backed · {unbacked} unbacked / {len(rows)} total\n\n")
        if verbose:
            print(f"    {overall}: {reason}")
            print(f"    {backed}/{len(rows)} source-backed, {unbacked} unbacked")

        if rows:
            lines.append("| Citation | Backed | Note |\n|---|---|---|\n")
            for r in rows:
                b = "✓" if r.get("backed") else "✗"
                lines.append(f"| {r.get('citation','')} | {b} | {r.get('note','')} |\n")
            lines.append("\n")

        violations = result.get("vocab_violations") or []
        if violations:
            lines.append(f"**Vocab issues:** {'; '.join(violations)}\n\n")

        high = result.get("high_relevance_assessment") or []
        if high:
            lines.append("**High-relevance rows:**\n\n")
            for h in high:
                mark = "✓" if h.get("justified") else "✗"
                lines.append(f"- {mark} {h.get('citation','')} — {h.get('reason','')}\n")
            lines.append("\n")

    lines.append(
        "---\n\n_Run `python3 verify_citations.py` to validate arXiv IDs and check "
        "recall against the S2 snowball corpus._\n"
    )

    audit_path = OUT / "AUDIT_REPORT.md"
    audit_path.write_text("".join(lines))
    if verbose:
        print(f"\nAudit report written to {audit_path}")
    return audit_path


if __name__ == "__main__":
    run_audit()
