#!/usr/bin/env python3
"""Measure what the write gate is worth, by putting back what it keeps out.

    python3 evals/gate_value.py

The whole argument for refusing writes rests on one observation from a real
corpus: 104 of 495 pages were auto-generated stubs of about 139 characters, and
they took the top two result slots for real queries. That is the claim this
project is built on, and until now nothing measured it.

So: take the evaluation corpus, add stub pages in the same proportion and of the
same shape a summariser produces — on topic, correctly titled, and empty of
anything the source does not already say — and re-run the identical queries. The
difference is the cost of not having a gate. Nothing else changes.

Every stub here would be refused by `memory_write.py`: they are under the
200-character floor and they cite no source. That is the point — this is the
population the gate exists to exclude, and this is what it buys.
"""
from __future__ import annotations

import json
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "skills" / "project-memory" / "scripts"))

import memory_search  # noqa: E402
import run as harness  # noqa: E402

# 104 of 495 in the corpus that motivated the gate.
STUB_RATIO = 104 / 495


def stub_pages(pages: list[dict]) -> list[dict]:
    """What an automated pass produces: the title restated as prose, nothing more.

    Deliberately not gibberish. A stub is dangerous precisely because it is
    on-topic and well-titled — it competes for the same queries as the real page
    and wins ties on brevity, because a short page normalises to a higher score.
    """
    count = round(len(pages) * STUB_RATIO)
    out = []
    for page in pages[:count]:
        title = page["title"]
        out.append({
            "slug": f"{page['slug']}-summary",
            "title": title,
            "kind": "concept",
            "sources": [],
            "body": (f"## Summary\n\nThis page documents {title.lower()}. "
                     f"See the implementation for details."),
        })
    return out


def score(corpus: list[dict], queries: list[dict]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        store = harness.materialise(corpus, Path(tmp))
        per_type: dict[str, list[float]] = {}
        ndcg, top_is_stub = [], []
        for item in queries:
            hits = memory_search.search(item["q"], store, k=10)
            ranked = [p.slug for _, p in hits]
            value = harness.ndcg_at(ranked, set(item["relevant"]))
            ndcg.append(value)
            per_type.setdefault(item.get("type", "other"), []).append(value)
            top_is_stub.append(1.0 if ranked and ranked[0].endswith("-summary") else 0.0)
    return {
        "ndcg@10": statistics.fmean(ndcg),
        "per_query": ndcg,
        "by_type": {k: statistics.fmean(v) for k, v in sorted(per_type.items())},
        "stub_took_first_place": statistics.fmean(top_is_stub),
    }


def stubs_for_share(pages: list[dict], share: float) -> list[dict]:
    """Enough stubs that they make up `share` of the resulting store."""
    wanted = round(len(pages) * share / (1 - share))
    template = stub_pages(pages)
    stubs: list[dict] = []
    round_no = 0
    while len(stubs) < wanted:
        for i, page in enumerate(template):
            if len(stubs) >= wanted:
                break
            copy = dict(page)
            copy["slug"] = f"{page['slug']}-{round_no}-{i}" if round_no else page["slug"]
            stubs.append(copy)
        round_no += 1
    return stubs


def sweep(pages, queries, clean) -> None:
    """What the gate is worth as the store degrades.

    A store without a gate does not sit at one stub ratio; it climbs, because
    nothing removes what was written. The single number above is the first year;
    this is the curve.
    """
    print("\n  as the share of stubs grows — which is what happens without a gate")
    print(f"    {'stubs':>7} {'nDCG@10':>9} {'lost':>8} {'stub ranked first':>19}")
    print(f"    {'0%':>7} {clean['ndcg@10']:>9.3f} {'—':>8} {'0%':>19}")
    for share in (0.2, 0.35, 0.5, 0.65, 0.8):
        polluted = score(pages + stubs_for_share(pages, share), queries)
        mean, _, _ = harness.paired_delta(clean["per_query"], polluted["per_query"])
        print(f"    {share:>6.0%} {polluted['ndcg@10']:>9.3f} {mean:>+8.3f} "
              f"{polluted['stub_took_first_place']:>18.0%}")


def main() -> int:
    data = harness.load_corpus()
    pages, queries = data["pages"], data["known_item"]
    stubs = stub_pages(pages)

    clean = score(pages, queries)
    polluted = score(pages + stubs, queries)
    mean, low, high = harness.paired_delta(clean["per_query"], polluted["per_query"])

    print(f"corpus: {len(pages)} real pages, {len(stubs)} stubs added "
          f"({len(stubs) / (len(pages) + len(stubs)):.0%} of the store), "
          f"{len(queries)} queries\n")
    print(f"  gate held (real pages only)   nDCG@10 {clean['ndcg@10']:.3f}")
    print(f"  no gate (stubs admitted)      nDCG@10 {polluted['ndcg@10']:.3f}")
    print(f"  cost of not having a gate     {mean:+.3f}  [{low:+.3f}, {high:+.3f}]"
          f"  {'significant' if (low > 0 or high < 0) else 'NOT significant'}")
    print(f"\n  a stub took first place on    {polluted['stub_took_first_place']:.0%} "
          f"of queries")
    print("\n  by query type")
    for kind in sorted(clean["by_type"]):
        print(f"    {kind:12} {clean['by_type'][kind]:.3f} -> "
              f"{polluted['by_type'][kind]:.3f}")

    sweep(pages, queries, clean)

    print("\n  every stub above is refused by memory_write.py: no source, and a body "
          "under 200 characters.")
    if "--json" in sys.argv:
        print(json.dumps({"clean": clean["ndcg@10"], "polluted": polluted["ndcg@10"],
                          "delta": [mean, low, high]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
