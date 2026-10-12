# Roadmap

Written against [PRIOR-ART.md](PRIOR-ART.md) and [RISKS.md](RISKS.md). Every
milestone below is chosen so that **failing it is visible**. A roadmap whose
milestones cannot be failed is a wish list.

---

## Where this stands

Fourteen nodes. One module. Zero nodes checked by a proof assistant. The format
works and the validator has teeth; nothing else is established.

The pilot proves exactly one thing: **that a proof can be written so its
dependency structure is derived rather than declared, and that a machine can
check the derivation is self-consistent.** It does not prove the format survives
harder mathematics, that anyone wants it, or that it scales. Those are the next
three questions, in that order.

## The strategic problem

Prior art is unambiguous: theorem-level dependency graphs are solved, step-level
extraction from Lean is solved, and proof terms already contain everything.
Building more of the same is not a contribution.

So the roadmap does **not** aim at "more mathematics in the graph." Adding
another two hundred textbook lemmas would be a worse mathlib. It aims at the
three things nobody has done, in order of how cheaply they can be falsified.

---

## Phase 1 — Is the format actually sound? *(now)*

The pilot must survive contact with people who know more than its authors.

- [x] ~~Replace the `OWNER` placeholder~~ — done; the repository lives at
      `SanTanBan/ProofWeb`.
- [ ] **Two independent reviewers on all 8 theorems.** Every node moves to
      `reviewed` or gets an issue. This is the binding constraint and it is not
      glamorous.
- [ ] **Correct every `formalization:` link.** Several are approximate — `T4`
      points at `inv_eq_of_mul_eq_one_right`, whose mathlib statement is close to
      but not the same as ours. "mathlib has no exact counterpart" is a perfectly
      good answer and should be recorded as one.
- [ ] **Get one node to `verified`.** Any node. This exercises the only claim in
      the repository that does not depend on trusting a human, and it will
      surface whatever is wrong with the cross-linking model.
- [ ] **Resolve the closure convention** ([SPEC.md](SPEC.md#the-closure-convention))
      one way or the other, in public, with the reasoning written down.

**Exit test:** an outside reviewer reads a node and finds nothing to fix.
**Falsified if:** the first serious reviewer finds the format cannot express
something elementary without contortion.

## Phase 2 — Does it survive a proof it was not designed for?

The pilot was written knowing the format. That is the demo trap: the small case
is unrepresentative precisely because it was co-designed with the tool.

**Do this before writing node 15.** The temptation is to grow the corpus first,
because transcribing more equational algebra is easy and feels like progress. It
is the single fastest way to spend a year discovering something a week would have
shown.

- [ ] **One proof by contradiction, one by induction.** Both stress the model
      differently — induction needs a schema (is it `background`? an axiom? a
      node?), contradiction needs local assumptions discharged mid-proof. The
      `assumption` token exists in anticipation and has never been used in anger.
- [ ] **One proof with a genuine case split.**
- [ ] **A second module importing the first**, to exercise `imports` on real
      content rather than in tests.
- [ ] **Transcribe a proof written by someone else**, from a textbook, without
      adjusting it to suit the format. Record what had to be distorted.

**Exit test:** the distortion list is short and the reasons are defensible.
**Falsified if:** every non-trivial proof needs a schema extension. That means the
format encodes equational reasoning about groups, not mathematics.

## Phase 3 — Measure whether an edge is a well-defined object at all

**This is the most important milestone on the page**, and it replaces an earlier
version of Phase 3 that was **logically invalid**. That version proposed
authoring the ~17 Lean-formalized Erdős solutions by hand and comparing the
derived edges against LeanDojo's premise data as ground truth. The flaw: a
human's informal proof and a Lean formalization of the same theorem are
*different proofs*. Divergence between their premise sets is not an error rate,
so the kill criterion could never fire. It is recorded here rather than deleted,
because the mistake is instructive — it is exactly the kind of plausible,
motivated, wrong experiment this project exists to catch elsewhere.

The corrected question is prior to it, and nobody has answered it:

> **Do competent humans agree with each other about step-level premise
> attribution in informal proofs?**

If they do not, there is nothing to measure, no dispute-resolution procedure, and
no basis for the two-reviewer rule — and the whole enterprise is unfounded.
TheoremGraph, LeanDojo, `leanblueprint` and the Stacks Project all sidestep this:
they either have a kernel, so attribution is exact and free, or they work at
statement granularity, so the question never arises.

The study:

- [ ] Pick **40–60 short informal proofs** from a standard source.
- [ ] Recruit **two annotators who are not the maintainer** (paid; ~$15–25K is
      the whole budget, and it is a far more defensible grant ask than API
      credits).
- [ ] **Pre-register** — before any data exists — the sample size, the agreement
      statistic, and the threshold below which the answer is "humans do not
      agree, so hand-authored provenance is not a measurable object."
- [ ] Primary result: **inter-annotator agreement** (Jaccard on cross-node edge
      sets; Cohen's κ on per-premise inclusion).
- [ ] Secondary, descriptive only: divergence against LeanDojo premises for the
      Lean-formalized subset — **explicitly labelled as comparing two different
      proofs**, not as an error rate.
- [ ] **Publish the disagreement cases verbatim.** They are the most interesting
      output and no existing dataset contains them.

Run alongside it, and much sooner — two days of work:

- [ ] **The ablation.** Frontier model + web search, versus frontier model +
      ProofWeb, on step-level attribution for 30 blind steps, judged by a third
      party. If the graph does not beat plain retrieval by a wide margin, the
      project is finished and should say so.

**Exit test:** the study is published, whatever it says.
**Falsified if:** agreement comes back below the pre-registered threshold, or the
ablation shows no advantage. Both are in the kill criteria in
[RISKS.md](RISKS.md).

## Phase F — The formal track (runs in parallel with everything above)

Added when the project pivoted to mechanistic extraction; see
[FORMAL-TRACK.md](FORMAL-TRACK.md) for the full design. The Metamath pipeline
(parse → verify → extract, no AI) is **built and tested**. What remains:

- [x] **Scale test on all of set.mm.** Done: 47,588/47,588 proofs verified in
      39.1 s wall clock, zero failures (Python 3.12, single core, replay logs
      off). What remains of this item: publish the corpus-wide reverse index
      as an artefact rather than a CLI query.
- [x] **Cross-check against a canonical verifier** — `mmverify.py` over the
      same develop snapshot: 47,588 verified, "No errors were found", exact
      count agreement. Still worth repeating with `metamath.exe`/`smm3` before
      any *published* claim rests on an extraction, and worth automating in a
      scheduled CI job.
- [x] **Import a Lean corpus from text.** Done, and larger than planned: the
      September 2026 release of Anthropic's 13-million-line, 29,511-theorem FLT
      proof turned out to be importable with no Lean toolchain at all, because
      the Prove2Me layout makes a proof's imports its citations. Six published
      figures reproduced exactly; see [FORMAL-TRACK.md](FORMAL-TRACK.md) §3a.
- [x] **Import the other AI-written corpora.** Done as `import-lean --style
      lake`: any Lake project at module granularity, every node `draft`, with
      the `formalization.yaml` catalogue and Comparator configurations read so
      the audit can say which catalogued results rest on others and which have
      a `sorry` below them. Run on `NavierStokesAndEuler`, the three
      `fluid_lean` projects and `openai/math`; see
      [FORMAL-TRACK.md](FORMAL-TRACK.md) §3a.
- [ ] **Theorem-level edges for Lake projects.** Module imports are an upper
      bound. Getting from "file A may use file B" to "theorem X uses theorem Y"
      needs the term-level extraction below; no amount of text parsing gets
      there honestly.
- [ ] **`leandojo-to-proofweb` converter.** LeanDojo already extracts
      tactic-level premises from mathlib; converting its traced format into
      this repository's extracted-JSON puts `uses`/`why`/the viewer over
      mathlib data. Integration, not invention — a weekend, not a thesis.
- [ ] **The Rocq extractor** ([FORMAL-TRACK.md §4](FORMAL-TRACK.md)) — the
      genuine greenfield. Needs a collaborator who knows `rocq-lsp`; this item
      is the single most valuable thing an outside contributor could pick up.
- [ ] **Measure the text against the kernel.** The FLT import attributes
      citations to proof lines *textually*, and grades each occurrence
      (81.1% fully qualified, 4.0% field notation that text cannot resolve at
      all). Building a sample of low-closure theorems with `lake build
      Theorems.Thm_X` and comparing the textual `by` lists against the kernel's
      constants would turn that grading into a measured precision and recall.
      Unlike the withdrawn Erdős experiment this compares **two extractions of
      the same proof**, so divergence is a genuine error rate. Pre-register the
      thresholds.

## Phase 4 — The one contribution that might be real

Pick **one** of the three unoccupied areas. Not all three. The failure mode of a
solo project is breadth.

**Recommended: stable identity for sub-proof nodes.**

It is the only one of the three that is a *design* problem rather than an
engineering-effort problem, which means a small project can plausibly make
progress on it, and it is prerequisite to the other two. Concretely:

- [ ] Write down what "step 3 of the proof of X" should mean after the proof is
      reordered, a step is split in two, or the proof is replaced wholesale.
- [ ] Implement it, and demonstrate it by **actually refactoring a pilot proof**
      and showing which external references survived and which broke, correctly.
- [ ] Compare against how the Stacks Project handles tag permanence and how
      `leanblueprint` handles `\uses` under refactoring. Write up the difference.

The alternatives, deliberately deprioritised:

- *Rocq step-level extraction* (the cleanest greenfield) — real, valuable, and
  needs someone who genuinely knows `rocq-lsp`. If that person appears, this
  jumps the queue. It is an ecosystem contribution worth more than the graph.
- *Informal step-level provenance at scale* — the natural extension, but it is
  the one that needs contributor supply we do not have.

**Exit test:** a written artefact a Lean or Rocq person would argue with.
**Falsified if:** six months pass with no external contributor and no artefact.
See the kill criteria in [RISKS.md](RISKS.md).

---

## What is explicitly not on the roadmap

**Millennium Problems.** Not as a goal, not as motivation, not in a grant
application. See [RISKS.md](RISKS.md#overclaiming). The gap between 8 group
theory lemmas and the Hodge conjecture is not a matter of scaling.

**Ramanujan notebook identities.** Genuinely interesting, and the
[Ramanujan Challenge](https://arxiv.org/abs/2607.09721) is a well-designed
benchmark — but it tests *proof discovery*, which this project does not do, and
it prioritises formal proofs in Lean/Rocq/Isabelle, which this project has no
pipeline for and zero verified nodes to show. Note it as a future benchmark, not
a current target.

The honest connection is narrower and worth stating: formalizing those ten
statements would expose which supporting lemmas are missing from existing formal
libraries. That is a dependency-gap analysis, which is the one thing a proof
graph is genuinely good at. It depends on Phases 1–3 succeeding first.

Proving unproven Lost Notebook entries requires expertise in q-series and modular
forms that this project does not have and that a graph does not supply. A graph
could track which entries have proofs, where, resting on what machinery — but
that is a bibliography with edges, and Berndt's volumes already are one.

**LLM-driven bulk population.** Not until there is an answer to who reviews the
output. The characteristic error of a machine-drafted proof is a citation that is
plausible and wrong, and verifying one costs about what writing one costs.
Generating faster than reviewing converts the graph from a checked artefact into
an unchecked one, which is the only way to destroy the sole property it has.

**A hosted web service.** The single-file HTML export is sufficient until someone
who is not the maintainer asks for more.
