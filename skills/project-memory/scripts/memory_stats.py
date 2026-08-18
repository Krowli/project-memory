#!/usr/bin/env python3
"""Summarise the store's log: what was written, what was refused, what was asked.

Usage:  python3 memory_stats.py [--store DIR] [--since YYYY-MM-DD] [--json]

Exists because a log nobody reads is the same failure as no log. Three questions
it answers, which are exactly the ones a trial period has to settle:

  did agents write at all          — writes, and how many were merges
  is the gate helping or annoying  — refusals by code, as a share of attempts
  does search find things          — queries that returned nothing

A refusal rate that is high and concentrated on one code usually means the rule
is wrong, not the writer. Queries with zero hits are the strongest signal there
is: either the corpus has a hole, or ranking does.

Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from memory_lib import LOG_NAME, VERSION, find_store


def read_log(store: Path, since: str | None) -> list[dict]:
    path = store / LOG_NAME
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # a torn line should not hide the rest of the log
        if not isinstance(rec, dict) or "ts" not in rec:
            continue  # nor should a line from some other writer
        if since and rec.get("ts", "") < since:
            continue
        out.append(rec)
    return out


def _median(values: list[int]) -> int:
    """The real median. The upper-middle value was reported for even counts, which
    biased high exactly the statistic used to argue about the length floor."""
    if not values:
        return 0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


def summarise(records: list[dict]) -> dict:
    writes = [r for r in records if r.get("event") == "write"]
    rejects = [r for r in records if r.get("event") == "reject"]
    searches = [r for r in records if r.get("event") == "search"]
    attempts = len(writes) + len(rejects)
    misses = [r for r in searches if not r.get("hits")]

    return {
        "span": [records[0]["ts"], records[-1]["ts"]] if records else [],
        "writes": len(writes),
        "creates": sum(1 for r in writes if r.get("mode") == "create"),
        "merges": sum(1 for r in writes if r.get("mode") == "merge"),
        "median_chars": _median([r.get("chars", 0) for r in writes]),
        "rejects": len(rejects),
        "reject_rate": round(len(rejects) / attempts, 3) if attempts else 0.0,
        "reject_codes": dict(Counter(r.get("code", "?") for r in rejects).most_common()),
        "searches": len(searches),
        "zero_hit_searches": len(misses),
        "zero_hit_rate": round(len(misses) / len(searches), 3) if searches else 0.0,
        "zero_hit_queries": [r.get("query") for r in misses][-15:],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Summarise the project-memory log.")
    ap.add_argument("--version", action="version",
                    version=f"project-memory {VERSION} ({Path(__file__).resolve().parent.parent})")
    ap.add_argument("--store", type=Path, default=None)
    ap.add_argument("--since", default=None, help="ISO date, e.g. 2026-08-09")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    store = args.store or find_store()
    records = read_log(store, args.since)
    if not records:
        print(f"no log entries in {store / LOG_NAME}", file=sys.stderr)
        return 0

    s = summarise(records)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0

    print(f"{s['span'][0]} … {s['span'][1]}\n")
    print(f"writes    {s['writes']:>5}   ({s['creates']} new, {s['merges']} merged, "
          f"median {s['median_chars']} chars)")
    print(f"refused   {s['rejects']:>5}   ({s['reject_rate']:.0%} of write attempts)")
    for code, n in s["reject_codes"].items():
        print(f"            {n:>3}  {code}")
    print(f"searches  {s['searches']:>5}   ({s['zero_hit_rate']:.0%} returned nothing)")
    for q in s["zero_hit_queries"]:
        print(f"            miss: {q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
