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

- [ ] **Replace the `OWNER` placeholder** with the real GitHub org/user in four
      places, before the repository is public: the CI badge in `README.md`,
      `$id` in `schema/node.schema.json`, and the two links in
      `.github/ISSUE_TEMPLATE/config.yml`.
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

## Phase 3 — Ground-truth the method against a kernel

**This is the most important milestone on the page**, because it is the only one
where the project's central claim can be checked against something other than an
opinion.

The [Erdős problems database](https://www.erdosproblems.com/) has roughly 1,100
problems, about 40% solved, with **~240 statements formalized in Lean but only
~17 *solutions* formalized** ([Buzzard, Dec 2025](https://xenaproject.wordpress.com/2025/12/05/formalization-of-erdos-problems/)).
That 240-versus-17 gap needs no exaggeration to be interesting.

The experiment:

- [ ] For each of those ~17, take the **human-readable published proof** — not
      the Lean file — and author it as ProofGraph nodes with per-step
      justifications.
- [ ] Derive the dependency edges.
- [ ] Compare them against the premise references extracted from the
      corresponding Lean proof. [LeanDojo](https://leandojo.org/leandojo.html)
      already provides step-level premise data for exactly this comparison.
- [ ] **Publish the confusion matrix**: edges the human proof implies that the
      Lean proof does not use, and premises the Lean proof needs that the human
      proof never mentions.

Why this and not something bigger: it is sized for one person, it is bounded, the
Lean side is already done by someone else, and it has **ground truth**. Every
other validation of a hand-authored proof graph is somebody's judgement; this one
is checkable against a kernel. It also lands in a live corpus with an active
maintainer and forum, so the output is visible to people who can evaluate it.

**Exit test:** the confusion matrix is published, whatever it says.
**Falsified if:** hand-authored step-level provenance systematically diverges from
kernel-verified provenance. That is a kill-criterion result — and the point is to
find it out in weeks rather than years.

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
