# The formal track: mechanistic extraction from proof assistants

This document is the design for the half of ProofGraph where the edges are
**facts, not judgements**: graphs extracted mechanically — no AI, no human
citation-typing — from machine-checked proofs. It exists because of a specific
piece of feedback that reshaped the project:

> Build a mechanistic codebase that develops the ProofGraph by extracting
> existing proofs, theorems and axioms — no AI API should be needed, as this
> method should someday be an enhanced part of interconnected formal analysis.

That instinct is exactly right, and it is worth being precise about *why*: it
answers the most serious objection in [RISKS.md](RISKS.md). Section 1 there
argues, correctly, that a hand-authored edge has no correctness criterion —
there is no fact of the matter a checker could check. An edge read off a
kernel-checked proof term does not have that problem. **The proof is the
ground truth; the extractor only changes its representation.**

---

## 1. The intended pipeline, restated precisely

The vision, in the founder's terms: start from axioms; build the earliest
theorems on them; each new theorem integrated into the graph is connected to
whatever earlier material it actually uses, **at the specific step where it
uses it** — possibly to a mid-proof step of an earlier theorem, not just to its
conclusion; later theorems may rest only on other theorems, with no direct
axiom edge at all.

Three refinements turn that into something a formal system can execute, and
none of them weakens it:

**Axioms are postulated, not proved.** There is no "Rocq/Lean proof of an
axiom" — an axiom is precisely a statement accepted without proof. In Lean the
foundation is the calculus of inductive constructions plus three axioms
(`propext`, `Quot.sound`, `Classical.choice`); in Metamath's set.mm it is 20
axioms and 2 inference rules for classical ZFC. What *is* done with axioms is
exactly what the pipeline needs: they are **declared** as the graph's roots,
and every theorem's transitive closure bottoms out in them. `#print axioms` in
Lean and `Print Assumptions` in Rocq exist precisely to report that closure.

**"Check each new theorem against previous proofs for connections" is
automatic, and that is the good news.** In a formal library a proof cannot use
a prior result without naming it — the checker rejects it otherwise. So the
integration check the pipeline calls for is not a search procedure to design;
it is bookkeeping the kernel already did, waiting to be read out. The work is
in *surfacing* it (see §4: nothing serves the reverse query today).

**Connections "from any step, not only the last" — one correction.** What a
later proof invokes is a prior theorem's *statement*, never literally line 7 of
its proof — proofs are sealed boxes once checked; that is what makes them
composable. The step-granularity lives on the *using* side: **step 5 of proof
B invokes theorem A** is exactly what this project records, per step, with a
stable address (`B#collapse-inner → A`). When a middle portion of an existing
proof is worth pointing at, the formal world's answer is to *extract it as a
lemma* — at which point it becomes a node and everything works. Detecting
repeated sub-proof patterns that deserve extraction is a real research topic
(grammar compression over proof terms, [arXiv:2505.12305](https://arxiv.org/abs/2505.12305)),
and a populated ProofGraph is the right substrate for it.

## 2. What is built and working today: the Metamath extractor

[`tools/proofgraph/metamath.py`](../tools/proofgraph/metamath.py) — roughly 600
lines, two dependencies, no AI, no toolchain beyond Python.

**Why Metamath first.** A Metamath database is a single plain-text file; the
proof format *is* the step structure (a proof is a sequence of labels applied
to a stack, so "which theorem is used at which step" is literally what the
file says); and verification is simple enough to reimplement and audit — which
means the extractor can afford to **verify every proof before emitting a
single edge**. Lean and Rocq need real toolchains and are designed below, not
faked here.

**What it does.** Parses any `.mm` database (normal and compressed proofs,
including `Z`-tagged step reuse), replays every proof through a built-in
verifier — substitution, stack discipline, and disjoint-variable conditions
per the Metamath spec — and emits ProofGraph nodes whose steps are the logical
(`|-`) replay steps, each carrying machine-derived `by` lists: the earlier
steps it consumed, in mandatory-hypothesis order, plus the assertion it
applied. Grammar steps (wff assembly) become vocabulary edges rather than
proof edges, so the graph is about mathematics rather than parsing. Nodes
whose proofs verify are marked `verified`; incomplete proofs stay `draft` with
the reason recorded.

```bash
# extract everything up to and including set.mm's `id`, with the viewer
python -m proofgraph extract corpora/set.mm --stop-at id \
    -o examples/setmm-through-id.json --html build/setmm.html

# what does mp2 rest on, and at which steps?
python -m proofgraph why mp2 --json examples/setmm-through-id.json

# every proof step in the extract that invokes ax-mp — the reverse
# step-level lookup that no existing search engine serves
python -m proofgraph uses ax-mp --json examples/setmm-through-id.json
```

**Evidence, from this repository's own runs.** The first 60 theorems of the
real set.mm verified 60/60 with zero failures in 0.8 s; the first 1,000 in
1.0 s. The extracted proof of set.mm's `id` matches the Metamath Proof
Explorer page for it step for step. And one more result worth recording: the
first hand-written proof in the test fixture — written carefully, on paper,
by the person building the verifier — **was wrong** (a misinstantiated
`ax-1`), and the verifier refused it. The error rate of careful humans is the
project's founding observation, and it reproduced itself at the first
opportunity.

**Trust statement.** An extracted edge means: *this Python verifier replayed
the proof from axioms and it checked*. That is a strong claim and still not
the strongest one available — this verifier is young and is not
`metamath.exe`. Before publishing any load-bearing claim derived from an
extraction, cross-check the database against the canonical verifiers.

Two provenance facts worth stating rather than discovering later. set.mm is
**CC0 / public domain** (the repository LICENSE is the verbatim CC0 1.0 legal
code), so extractions carry no restrictions beyond honesty. And "no AI" here
describes *this pipeline*, not the corpus's history: set.mm's own contributor
table includes OpenAI (some proofs in the database were machine-found, then
kernel-checked and human-curated like everything else). The kernel does not
care who found a proof, and neither does the extractor — but a project that
advertises a no-AI pipeline should say precisely where that boundary is.
Practical note: fetch set.mm from the **develop** branch; `master` is a stale
2021 snapshot.

## 3. The Lean path (designed; needs a toolchain, not ideas)

A Lean proof term is an `Expr` whose constant subterms name every lemma used,
at a specific structural position. The mechanistic extractor is therefore a
metaprogram, not a parser: iterate `Environment.constants`, and for each
theorem walk its value with an `Expr` traversal collecting used constants
(`Lean.Expr` folds; positions recoverable during traversal). No AI anywhere.

Two granularities exist and they are genuinely different:

- **Term-level** (what the kernel checked): exact, complete, but
  post-elaboration — `simp` becomes a large generated term, and the structure
  reflects the elaborator's output more than the human's argument.
- **Tactic-level** (what the human wrote): `intro`, `rw [add_comm]`,
  `exact mul_left_cancel …` — this is the layer matching ProofGraph's notion
  of a "step". **[LeanDojo](https://leandojo.org/leandojo.html) already
  extracts this**, with premises annotated per tactic and goal states before
  and after, for all of mathlib.

Consequence, stated plainly so this project does not waste a volunteer's year:
**the Lean work is integration, not invention.** A `leandojo-to-proofgraph`
converter — LeanDojo's traced tactics into this repository's node format, so
`uses`/`why`/the viewer run over mathlib data — is a weekend-scale project
with real value (the reverse step-level index over mathlib does not exist as
a served query). Re-extracting what LeanDojo extracts would be rediscovery.

## 4. The Rocq path (greenfield — the real prize)

For Rocq there is no LeanDojo. Step-level premise attribution does not exist
in any form: `coq-dpdgraph` is whole-object-level, Alectryon renders goal
states without premise links, `Print Assumptions` prints a flat set. And the
substrate has just shifted — SerAPI is discontinued; `coq-lsp`/`rocq-lsp` is
the successor — so there is no legacy incumbent to displace.

The design, for someone who knows the Rocq internals (this is the single most
valuable contribution an outside collaborator could make):

1. Drive `rocq-lsp` over a `.v` file; after each sentence, request the proof
   state; on `Qed`, obtain the kernel term of the completed proof.
2. Walk the term for constants (the analogue of the Lean traversal); attribute
   them to sentences via the elaboration spans `coq-lsp` tracks.
3. Emit the same extracted-JSON this repository already loads, viewers and
   queries included.

Deliverable 1 is `rocq-lsp`-shaped engineering, not theory. Even a
*whole-proof* extractor for the Rocq stdlib — skipping step attribution in
version one — would be the first of its kind and immediately useful.

## 5. After construction: how a ProofGraph helps attack open problems

Asked directly: once the graph exists, how does it help prove something new —
an Erdős problem, a conjecture? Honestly, in four mechanisms, in decreasing
order of evidence:

**1. Premise selection — the proven one, with the numbers.** The pipeline that
has actually produced new machine proofs for fifteen years is: **mine** the
dependency graph from checked proofs → **rank** candidate premises for a new
goal → hand the pruned problem to an automated prover → **replay** the found
proof in the kernel → feed the new lemma's edges back in. Isabelle's
Sledgehammer is the existence proof, and its evaluations isolate exactly what
the graph is worth, because its two selectors differ in precisely that: MePo
ranks by symbol overlap and never touches the graph; MaSh/MeSh are *trained on
the dependency graph* — a k-NN over "which premises did similar theorems'
proofs actually use". On identical provers and budgets, cumulative over six
large formalizations: **MePo alone 48.5% of goals; adding the graph-trained
selectors, 66.1%** (Blanchette et al., *A Learning-Based Fact Selector for
Isabelle/HOL*, JAR 2016 — which also found the graph-trained selector needs
~4× fewer premises for its peak). CoqHammer reports 40.8% of Coq stdlib
theorems push-button; MizAR proves ~40% of the Mizar library; Lean's ReProver
(51.2% pass@1, vs 47.6% for the same model without retrieval) is trained on
LeanDojo's step-level premise data — the same kind of data this project's
extractor emits. That difference — mid-40s to mid-60s percent — is the
measured value of the artefact this track builds. The graph does not prove;
it makes the prover's search space tractable, and that is worth ~15–18
percentage points of actually-closed goals.

**2. Dependency-gap analysis.** Formalize an open problem's *statement* (this
is how the [Erdős formalization effort](https://www.erdosproblems.com/) and
DeepMind's [formal-conjectures](https://github.com/google-deepmind/formal-conjectures)
already work — statements first). The graph then answers: *which prerequisite
theory does the statement's vocabulary rest on, and which of it is missing
from the formal corpus?* That produces a concrete, ordered work-list of
lemmas — the map of what must be built before anyone can even attempt the
proof formally. This is the one thing a proof graph is genuinely best at.

**3. Lemma mining.** Repeated sub-proof structure across the corpus = a lemma
nobody has extracted yet. Grammar-compression over proof terms
([arXiv:2505.12305](https://arxiv.org/abs/2505.12305)) formalizes this; a
populated step-level graph is its natural input. New *named* mathematics from
old proofs — modest, real, and mechanistic.

**4. Provenance for machine-generated mathematics — the bet on the future.**
As AI systems produce more proofs, the binding question becomes *audit*: what
does this new proof actually rest on, and does anything in its closure smell?
A step-level, kernel-backed provenance graph is the audit tool. This is the
one mechanism whose value *rises* as provers get stronger.

**What none of these do:** supply the idea. Erdős problems that fell recently
fell to search and to human-model collaboration, not to dependency lookups. A
graph shortens the distance between an idea and a checked proof; it does not
have ideas. Any version of this project that forgets that sentence turns into
the thing [RISKS.md](RISKS.md#overclaiming) warns about.

## 6. How the two tracks fit together

| | Formal track | Informal track |
|---|---|---|
| Edge provenance | read off a kernel-checked proof, verified at extraction | typed by a human, reviewed by two more |
| Correctness criterion | the proof itself (RISKS §1 answered) | inter-annotator agreement (RISKS §1 stands) |
| Populates | `extract` → JSON corpora | `graph/` YAML modules |
| Its open question | can the extraction reach Lean/Rocq scale and stay honest? | is step-level attribution a well-defined human judgement at all? |

Same schema, same queries, same viewer — `why`, `uses`, `T6#conclude`-style
stable addresses — over both. The informal track is the measurement study
([ROADMAP.md](ROADMAP.md) Phase 3); the formal track is the infrastructure
build. Each is the other's control group, which is the most honest structural
relationship the two could have.
