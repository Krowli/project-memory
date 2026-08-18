# Evaluation

```bash
python3 evals/run.py --by-type
```

Everything this needs is committed here: the corpus, the queries, the methods and
the scorer. That is the entire point. `references/retrieval.md` used to argue the
design from figures whose inputs existed in nobody's repository — no reader could
check them, and no future change could be re-measured against them.

## What is measured

**Known-item retrieval.** Each query was written for exactly one page, and the
question is where that page lands. Reported as nDCG@10, MRR@10, recall@1 and
recall@3, with a bootstrap confidence interval over queries (1000 resamples). A
difference smaller than the interval is not a difference.

**Ambiguous queries.** Several pages are legitimately relevant. This separates
"found something" from "put the best one first", which the known-item set cannot.

**Unanswerable queries.** Realistic questions about the same project that no page
answers. A ranked list invites false confidence: the interface always returns
*something*, and an agent reads a list as an answer. The number reported is the
share of these queries that got any hit at all — lower is better, and no amount of
ranking quality compensates for it.

## Methods compared

| method | what it stands for |
|---|---|
| `shipped (fts5 index)` | what an installed skill actually runs — so the number is the number users get |
| `shipped fallback (scan)` | the path that answers on a read-only store, mid-rebuild, or without sqlite3 |
| `scan, title weight 0` | ablation of the parameter the documentation calls the most important |
| `term count (previous)` | what this skill used before BM25F |
| `fts5 on raw text` | FTS5 with its own tokenizer — the variant that loses NFC, casefold and identifiers |
| `grep -rilE` | no ranker at all: every page containing any query word, in filename order |

## Does the store help the agent

`evals/run.py` measures retrieval. It does not measure the thing that matters, which is
whether an agent *answers better* because the store exists. `evals/agent_loop.json` records
one run of that, question by question, with every search the agent ran and every page it
opened.

Protocol: the 90-page corpus is written out as a real store; 18 questions in three families
are put to an agent that has the store and the skill's instruction; the same questions, minus
the ones only the store could answer, go to a control agent with no store at all; a grader
scores both against gold facts fixed before the answers existed.

| | with the store | control, no store |
|---|---|---|
| **answerable** (8) — the answer is in exactly one page | 8 correct | not run |
| **unanswerable** (5) — no page answers it | 5 abstained | 5 abstained |
| **superseded** (5) — a decision was reversed; asks what holds *now* | 5 correct, 0 obsolete | 5 abstained |

The superseded row is the one worth having. It is the failure the README opens with, and the
agent gave the current decision every time — following the `superseded by` marker to the
replacement rather than answering from the page it found first.

Median effort per question: 2 searches and 2 pages read when the answer exists, and **6
searches** before concluding it does not. That second number is the cost of the fact measured
above — a search practically never comes back empty, so establishing absence is work.

### What this run does not establish

- **The control is weak.** It was told "if you do not know, say so plainly", which primes the
  abstention it then produced. So the unanswerable row shows the store did not *cause*
  confabulation; it cannot show that the store prevents any.
- **The project is fictional**, so a model has no prior knowledge to confabulate from.
  Abstaining is easier here than on a real codebase, where the temptation to fill a gap from
  training data is real. Read that row as an upper bound.
- **Adherence is not tested.** The agent was told to search. Whether an agent searches when
  nobody reminds it in the moment is the job of the session hook, and this measures the loop
  working when the agent cooperates, not how often it does.
- One run, 18 questions, one grader per batch, questions written by a model from the corpus.

## What this cannot tell you

**The corpus and the queries were written by a language model.** They are not
harvested from a real store, and that is a real limitation, not a footnote.

The specific danger is that a query written from a page tends to reuse that page's
distinctive words, which flatters lexical retrieval and would make these numbers
optimistic. Two things push against it, and neither removes it:

- every page carries three queries of different types, and the `paraphrase` type is
  explicitly written to describe the same thing in *different* vocabulary — the
  symptom instead of the cause, the user-visible effect instead of the internal name;
- the per-type table is the one to read. If `keywords` and `paraphrase` diverge
  sharply, that gap is the vocabulary-mismatch weakness of lexical search showing
  up, and the average across types hides it.

**No competitor is measured here.** Comparing against mem0, Basic Memory, Zep or
the embedding hybrid would need their stacks running over this same corpus. Until
someone does that, any claim that this skill retrieves better than those is a
hypothesis. What can be said from this harness is narrower and worth keeping
separate: how the shipped ranker compares to the obvious alternatives that need no
server, and whether its own documented parameters are earning their place.

**Retrieval quality is not the product.** Whether an agent gives better answers
because this store exists is a different question, and this harness does not touch
it.

## Regenerating the corpus

`corpus.json` is committed so the numbers are reproducible. It was generated by
six agents writing about distinct subsystems of one fictional project, plus one
pass for the ambiguous and unanswerable sets. Regenerating it changes the numbers;
if you do, say so next to any figure you quote from it.
