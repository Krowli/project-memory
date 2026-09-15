#!/usr/bin/env python3
"""Optional probe: is the store's lexical ranking leaving quality on the table?

    /path/to/venv/bin/python evals/dense_probe.py
    /path/to/venv/bin/python evals/dense_probe.py --static minishlab/potion-base-8M

Not part of `run.py`, and deliberately not a dependency: it needs `fastembed`
(or, with `--static`, `model2vec`) and downloads a model, which the skill itself
never does. It exists because the decision to stay lexical is the most
load-bearing one in the project and the figures behind it came from a corpus
nobody else can see.

`--static` swaps the transformer for a model2vec static-embedding model — a
token-to-vector table with no torch and no ONNX runtime. The hybrid was refused
on cost, not quality (`references/retrieval.md`), and a static model is the
cheapest form the idea can take; if it does not clear the cost bar, the cheap
version of the idea is ruled out, not the idea. Alongside quality this reports
what the cost objection is actually about: a cold process to one query vector,
wall clock and peak RSS, next to the cold shipped search on the same store.

It measures three things on the same corpus and queries as `run.py`:

  dense    embeddings only — cosine over whole pages
  hybrid   the shipped ranking fused with dense by reciprocal rank fusion
  shipped  for reference, re-run here so all three see identical inputs

and reports the paraphrase column separately, because that is where the lexical
ranker is measured to be weakest (0.796 on keywords against 0.534 on paraphrase)
and where embeddings are supposed to win.
"""
from __future__ import annotations

import argparse
import math
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "skills" / "project-memory" / "scripts"))

import memory_search  # noqa: E402
import run as harness  # noqa: E402

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RRF_K = 60


def rrf(*rankings: list[str], k: int = RRF_K) -> list[str]:
    """Reciprocal rank fusion — the standard way to combine two rankings without
    having to make their scores comparable."""
    scored: dict[str, float] = {}
    for ranking in rankings:
        for rank, slug in enumerate(ranking):
            scored[slug] = scored.get(slug, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scored, key=lambda s: -scored[s])[:10]


def cold_process(argv: list[str]) -> tuple[float, float]:
    """Wall clock and peak RSS of one fresh process — what the skill pays per
    search, since it is a script run afresh each time."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t = time.perf_counter()
    subprocess.run(argv, capture_output=True, check=True)
    wall = time.perf_counter() - t
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # macOS reports bytes, Linux kilobytes.
    scale = 1.0 if sys.platform == "darwin" else 1024.0
    return wall, max(rss, before) * scale / 1e6


def main() -> int:
    ap = argparse.ArgumentParser(description="dense and hybrid retrieval, measured")
    ap.add_argument("--static", metavar="MODEL", default=None,
                    help="a model2vec static model instead of fastembed's MiniLM")
    args = ap.parse_args()

    data = harness.load_corpus()
    corpus, queries = data["pages"], data["known_item"]

    if args.static:
        try:
            from model2vec import StaticModel
        except ImportError:
            print("needs model2vec: pip install model2vec", file=sys.stderr)
            return 2
        model_name = args.static
        t = time.perf_counter()
        static = StaticModel.from_pretrained(model_name)
        load = time.perf_counter() - t
        embed_docs = embed_queries = static.encode
        one_vector = (f"from model2vec import StaticModel as M; "
                      f"M.from_pretrained({model_name!r}).encode(['q'])")
    else:
        try:
            from fastembed import TextEmbedding
        except ImportError:
            print("needs fastembed: pip install fastembed", file=sys.stderr)
            return 2
        model_name = MODEL
        t = time.perf_counter()
        model = TextEmbedding(model_name=model_name)
        load = time.perf_counter() - t
        embed_docs, embed_queries = model.embed, model.query_embed
        one_vector = (f"from fastembed import TextEmbedding as M; "
                      f"list(M(model_name={model_name!r}).query_embed(['q']))")

    def unit(vec):
        # fastembed does not normalise this model's output — measured norms of 3.4
        # and 4.9 on a short and a long text. A raw dot product therefore ranks by
        # length as much as by meaning, which quietly handicaps dense retrieval.
        norm = math.sqrt(sum(float(x) * float(x) for x in vec))
        return [float(x) / norm for x in vec] if norm else list(vec)

    docs = [f"{p['title']}\n{p['body']}" for p in corpus]
    slugs = [p["slug"] for p in corpus]
    t = time.perf_counter()
    doc_vecs = [unit(v) for v in embed_docs(docs)]
    index_build = time.perf_counter() - t

    t = time.perf_counter()
    query_vecs = [unit(v) for v in embed_queries([q["q"] for q in queries])]
    per_query_embed = (time.perf_counter() - t) / len(queries)

    with tempfile.TemporaryDirectory() as tmp:
        store = harness.materialise(corpus, Path(tmp))
        search_script = Path(memory_search.__file__).resolve()
        cold_search = cold_process([sys.executable, str(search_script), "--store", str(store),
                                    "terminal", "freeze", "webgl"])
        cold_vector = cold_process([sys.executable, "-c", one_vector])
        results = {"dense": [], "hybrid": [], "shipped": []}
        by_type = {name: {} for name in results}

        for item, qv in zip(queries, query_vecs):
            relevant = set(item["relevant"])
            sims = sorted(((sum(a * b for a, b in zip(qv, dv)), slug)
                           for dv, slug in zip(doc_vecs, slugs)), reverse=True)
            dense = [slug for _, slug in sims[:10]]
            shipped = [p.slug for _, p in memory_search.search(item["q"], store, k=10)]

            for name, ranked in (("dense", dense), ("shipped", shipped),
                                 ("hybrid", rrf(shipped, dense))):
                value = harness.ndcg_at(ranked, relevant)
                results[name].append(value)
                by_type[name].setdefault(item.get("type", "other"), []).append(value)

    print(f"model {model_name}")
    print(f"  load {load * 1000:.0f} ms | embed {len(corpus)} pages {index_build * 1000:.0f} ms | "
          f"per query {per_query_embed * 1000:.1f} ms")
    print(f"  cold process to one query vector {cold_vector[0] * 1000:.0f} ms, "
          f"peak RSS {cold_vector[1]:.0f} MB | cold shipped search "
          f"{cold_search[0] * 1000:.0f} ms, peak RSS {cold_search[1]:.0f} MB\n")

    types = sorted(by_type["shipped"])
    head = f"{'method':10} {'nDCG@10':>8} {'vs shipped, paired':>26}" + \
           "".join(f"{t:>13}" for t in types)
    print(head)
    print("-" * len(head))
    for name in ("shipped", "dense", "hybrid"):
        mean = statistics.fmean(results[name])
        if name == "shipped":
            delta = ""
        else:
            d, low, high = harness.paired_delta(results[name], results["shipped"])
            mark = "significant" if (low > 0 or high < 0) else "not significant"
            delta = f"{d:+.3f} [{low:+.3f},{high:+.3f}] {mark}"
        cells = "".join(f"{statistics.fmean(by_type[name][t]):>13.3f}" for t in types)
        print(f"{name:10} {mean:>8.3f} {delta:>26}{cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
