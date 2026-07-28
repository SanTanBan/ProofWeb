# Call for collaboration

**Short version:** there is a working, machine-checked pilot of 14 nodes and 52
proof edges where every edge is derived from a specific step of a specific proof.
It needs people to attack it. The most useful thing you can do is find a step
that does not follow.

---

## What this is

A format and a validator for writing mathematics so that **dependencies are
derived from proofs rather than declared alongside them**.

A node declares a proof. Each step carries its own justifications. Edges come
from those justifications and remember which step created them. So `T6 → T4` is
not a fact about two theorems — it is the fact that *step 12 of T6* is where
uniqueness of inverses is used, and `proofgraph why T6` will tell you that.

The consequence that matters: you cannot cite a lemma you did not use, and you
cannot use one without the edge appearing. The graph is falsifiable. CI fails
when it is wrong about itself.

## What this is not

Read [PRIOR-ART.md](PRIOR-ART.md) before getting excited. Briefly:

- Metamath has published an axiom→theorem→proof graph, with reverse edges and
  full axiom traceability, since the 1990s.
- The Stacks Project does it for human-written LaTeX: 21,446 tags with
  precomputed transitive closure in both directions.
- LeanDojo has extracted step-level premise attribution from all of mathlib
  since 2023 — 259,580 tactics, 167,779 premise references.
- Lean and Rocq proof terms *are* the dependency structure. Nothing is hidden.

**We are not the first people to think of this and we do not claim to be.** If a
pitch reaches you saying otherwise, it did not come from this repository.

## What is actually unoccupied

Three things, in descending order of confidence:

1. **Step-level provenance for mathematics that is not formalized.** LeanDojo
   works by reading proofs a kernel already checked. The Stacks Project and
   `leanblueprint` handle informal mathematics but at *statement* granularity —
   `\uses{}` hangs off a whole lemma. Step-level structure for prose mathematics,
   written and reviewed by humans, is not done.
2. **Rocq has no LeanDojo.** Step-level premise attribution does not exist for
   Rocq in any form, and `SerAPI` is discontinued, so there is no incumbent. This
   is the cleanest greenfield in the area.
3. **Stable identity for a sub-proof node.** If an edge points at "step 3 of the
   proof of X", what happens when someone reorders the proof? Nothing solves
   this. It is a design problem, not a scraping problem, and it is the real
   technical content here.

## What we need, concretely

**Reviewers (most needed, least glamorous).** Take one node. Read every step.
Try to find a citation that is wrong, missing, or unnecessary. You do not need a
doctorate to review elementary group theory — you need to be willing to be
pedantic in public. This is the binding constraint on everything else.

**Someone who knows Rocq.** Gap 2 above. Specifically: can `rocq-lsp` expose
proof-term subterms with source spans? If yes, that is a real contribution to the
Rocq ecosystem independent of anything else here.

**Someone who knows mathlib.** Every node carries a `formalization:` link.
Several are approximate — `T4` points at `inv_eq_of_mul_eq_one_right`, whose
statement is close to but not the same as ours. Correcting those, or telling us
the honest answer is "mathlib has no exact counterpart", is a half-hour of work
that materially improves the repository.

**Someone with an opinion on identity.** Gap 3. If you have thought about stable
addressing in versioned structured documents, we would rather argue with you now
than discover the problem at ten thousand nodes.

**Someone to say this is a bad idea and why.** [RISKS.md](RISKS.md) is an
adversarial review of this project kept in its own repository. If your objection
is not in it, it belongs there, and a pull request adding it will be merged.

## What we do not need

Original mathematics (no mechanism to referee it), bulk LLM-generated nodes
(nobody can review them and merging them destroys the only property the graph
has), a web frontend, or a rewrite in a faster language. See
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Getting started in five minutes

```bash
git clone <repo-url> && cd proofgraph/tools
pip install -r requirements.txt
python -m proofgraph validate --strict
python -m proofgraph why T6
python -m proofgraph render html -o ../build/proofgraph.html
```

Then open `build/proofgraph.html`, click node T6, and click step 12. Exactly the
edges that step created will light up. That interaction is the entire thesis of
the project; if it does not seem interesting, this is not the project for you and
that is a useful thing to learn in five minutes.

## Honest status

Fourteen nodes. One module. Elementary group theory that every algebra textbook
contains — chosen deliberately, so that what is being tested is the *method*, not
the mathematics. Zero nodes are `verified` because none has been checked by a
proof assistant yet. One maintainer, who is not a mathematician by training.

That is the whole state of the project. Anyone telling you it is more than that
is selling something.

---

## A short post, if you want to share this

> I have been building **ProofGraph**: a format for writing mathematics where a
> proof's dependencies are *derived from its steps* rather than listed beside
> them. Each step cites what justifies it; the graph edges come from those
> citations and remember which step produced them. So the edge isn't "T6 uses
> T4" — it's "step 12 of T6 is where uniqueness of inverses enters."
>
> There is a working pilot: 14 nodes, 52 proof edges, elementary group theory,
> machine-validated in CI, plus a single-file interactive viewer where clicking a
> proof step lights up exactly the edges it created.
>
> Important caveat I want to state up front, because the field is crowded and I
> would rather be corrected early than late: **this is not a new idea.** Metamath
> has published axiom→theorem dependency graphs since the 1990s. The Stacks
> Project does it for human-written mathematics at 21,446 tags. LeanDojo has
> extracted step-level premise data from all of mathlib since 2023. The
> repository ships a prior-art document saying so, and a risks document arguing
> the project should probably fail.
>
> What I think is genuinely unoccupied is narrower: step-level provenance for
> mathematics that has *not* been formalized, stable identity for sub-proof
> nodes, and the fact that Rocq has no equivalent of LeanDojo at all.
>
> I am looking for people to attack it — especially anyone who knows Rocq,
> mathlib, or has an opinion about stable addressing in versioned documents. The
> single most useful contribution is finding a proof step that does not follow.
>
> Repository: <url> · Start with docs/PRIOR-ART.md and docs/RISKS.md.

Post it where formal-methods people actually are — the
[Lean Zulip](https://leanprover.zulipchat.com/), the
[Rocq Discourse](https://discourse.rocq-prover.org/), `r/math`,
[Proof Assistants Stack Exchange](https://proofassistants.stackexchange.com/) —
rather than only on a general-purpose network. The people who can help are
concentrated in about four places, and they respond to a specific technical
question far better than to an announcement.
