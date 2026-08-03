# The ProofWeb node format

This is the normative description of what a node file means. It is short on
purpose. If you are here to add mathematics, read [CONTRIBUTING.md](../CONTRIBUTING.md)
first and come back when you hit something surprising.

---

## 1. The one design decision

**A node never declares its dependencies. It declares a proof, and the edges are
derived from the proof.**

Everything else follows from this. A conventional knowledge graph asks you to
write, next to each theorem, a list of what it uses. That list is an opinion. It
drifts from the proof the moment anyone edits either one, and nothing detects the
drift, because nothing connects them.

Here, the only way to create an edge `T6 → T4` is for some step of T6's proof to
cite T4 as its justification. The consequences are worth stating plainly:

- You cannot claim a dependency you did not use. An unused citation is an
  unjustified step, and review catches it.
- You cannot use a result without the edge appearing. Removing a citation to
  make the graph tidier leaves a step with no justification.
- Every edge carries the step number that created it. `T6 → T4` is not a fact
  about two theorems; it is the fact that **step 12 of T6** is where uniqueness
  of inverses is used. That is the query the whole format exists to answer.

This is why `proofweb why T6` can tell you not just *what* T6 rests on but
*where*, and why a diff to a proof is automatically a diff to the graph.

---

## 2. File layout

```
graph/
  <module-id>/
    manifest.yml         module metadata, and the modules it may cite
    axioms/*.yml         one node per file
    theorems/*.yml
```

A **module** is any directory under `graph/` containing a `manifest.yml`. The
subdirectory names (`axioms/`, `theorems/`) are for humans; the loader reads
every `.yml` under the module regardless of folder. Node `kind` is what counts.

One node per file, named `<id>-<slug>.yml`. Node ids are unique across the
*entire* graph, not just the module — this keeps citations unambiguous and the
cost is a naming convention, not a lookup.

### manifest.yml

```yaml
id: group-theory-elementary
title: Elementary group theory
description: >
  What this module contains and why it is drawn where it is drawn.
scope: >
  Explicitly what is OUT of scope. This is the field that stops modules sprawling.
conventions:                  # optional; see §6
  - id: closure-citations
    text: >
      A convention the whole module follows, stated once so that reviewers can
      apply it consistently instead of relitigating it per node.
imports: []                   # module ids this module may cite. Enforced.
meta:
  language: informal-rigorous
  status: pilot
  license: CC-BY-4.0
```

`imports` is enforced by the validator. A node may cite nodes in its own module
and in imported modules, and nothing else. This is the only structural defence
against the graph turning into one undifferentiated blob.

---

## 3. A node

```yaml
id: T6                        # unique; A* axiom, D* definition, L* background, T* theorem
kind: theorem                 # axiom | definition | background | theorem
title: The inverse of a product reverses the order

statement:
  natural: "For all a, b in G, (a·b)' = b'·a'."
  latex: '\forall a, b \in G:\; (a \cdot b)'' = b'' \cdot a'''
  context: [A1, A3, A4]       # see §5

proof:                        # required for kind: theorem, forbidden otherwise
  strategy: >
    One or two sentences orienting a human before the steps. Never load-bearing.
  hypotheses:                 # optional; named assumptions the statement discharges
    - "comm: a·b = b·a"
  steps:
    - n: 1                    # presentation ordinal: 1-based, contiguous. NOT stable.
      id: candidate-in-g      # immutable address, never reused. See §4a.
      claim: "b'·a' is an element of G"
      by: [A1, A4]            # see §4
    - n: 2
      id: reassociate-outer
      claim: "..."
      by: [s:candidate-in-g, A2]
      note: "Optional commentary. Never load-bearing."

status: draft                 # draft | reviewed | verified — see §7
formalization:                # cross-links into real proof assistants
  lean: mul_inv_rev
  metamath: grpinvadd
provenance:
  source: 'Standard; any first course in algebra.'
  contributed_by: 'name or handle'
  reviewed_by: ['reviewer one', 'reviewer two']
  assisted_by: 'Claude (drafted), human review by ...'   # required if an LLM helped
tags: [inverse, product]
```

### `kind`

| kind | proof | meaning |
|---|---|---|
| `axiom` | forbidden | Assumed. The thing the module is *about*. |
| `definition` | forbidden | Introduces vocabulary. Proves nothing. |
| `background` | forbidden | A principle of the ambient logic, not of the subject: equality is an equivalence relation, substitution is valid. Separated from `axiom` so that "what does group theory assume?" has an honest answer. |
| `theorem` | required | Must carry a proof whose every step is justified. |

The `background` kind exists because of a real problem. Every informal proof
silently uses substitution and transitivity of equality. If you call those
axioms, the group axioms get lost among them; if you leave them out, half the
steps in the graph have no justification. Naming them and marking them
`background` makes the logical debt visible without pretending it is algebra.

---

## 4. `by:` — the justification list

Each entry is one of:

| Token | Creates an edge? | Meaning |
|---|---|---|
| `A1`, `T4`, `D2`, … | **yes** | Another node. Becomes `this → that`, tagged with the step's ordinal *and* its stable id. |
| `s:candidate-in-g` | no | The step with that `id`, **in this same proof**. Must be strictly earlier — forward references are circular reasoning and are rejected. |
| `s3` | no | Step 3 by ordinal. Still accepted, and **warned about** whenever stable ids are available: see §4a. |
| `hyp` | no | The proof's single declared hypothesis. Rejected if the proof declares zero, or more than one. |
| `hyp:comm` | no | The hypothesis named `comm`. Must be declared. |
| `assumption` | no | An assumption local to a subproof (e.g. inside a proof by contradiction). |

`by` must be non-empty. A step with no justification is not a step.

**A step should cite what it uses, not everything nearby.** The temptation is to
list every axiom that feels relevant. Resist it: a citation you cannot point at
in the claim is noise, and noise here is indistinguishable from the graph being
wrong.

---

## 4a. Step identity: n is not an address

Every step carries two names, and confusing them is the single most expensive
mistake this format could make.

| | `n` | `id` |
|---|---|---|
| what it is | presentation ordinal, contiguous from 1 | immutable identifier |
| stable? | **no** — inserting a step renumbers everything after it | **yes**, assigned once |
| reused? | necessarily | **never**, not even after the step is deleted |
| address a step from outside? | never | always: `T6#conclude` |

The reason this matters is specific. Suppose a proof cites `s3`, and someone
later inserts a step at position 2. The citation still resolves. The validator
still passes. And it now points at a different line. **A silent change of meaning
that no check can detect is the worst defect this project can have**, and ordinal
addressing produces it structurally.

The same argument applies with more force to references from *outside* a proof —
another module, a paper, an issue, a URL. `T6 step 12` is not a durable name for
anything. `T6#conclude` is.

This is also the project's one substantive technical claim.
[PRIOR-ART.md](PRIOR-ART.md) records that stable identity for sub-proof nodes is
unsolved, and an earlier version of this schema *forbade* the fix: steps were
required to be numbered exactly `1..n`, so every insertion renumbered. The format
named the problem in its documentation and designed it out in its schema.

**Choosing ids.** Name what the step *does*, not where it sits. `collapse-inner`,
`drop-identity`, `conclude` — never `step-3`, `first`, `next`. Lowercase, digits
and hyphens; unique within the proof.

**Deleting a step.** Remove it and renumber `n`. Do **not** reuse its `id` for
anything, ever — a stale external reference should fail to resolve, which is
recoverable, rather than silently resolve to an unrelated line, which is not.

## 5. `context:` — vocabulary edges are not proof edges

`statement.context` lists nodes whose **vocabulary** the statement uses, as
distinct from what its proof depends on. These become `vocabulary` edges, drawn
dotted, and excluded from depth and dependency queries by default.

The distinction is not pedantry. T4 ("inverses are unique") cannot even be
*stated* without A3 (there is an identity) and A4 (inverses exist) — the words
"identity" and "inverse" come from there. But T4's *proof* may legitimately not
cite A3 at all. Collapsing the two relations would make it impossible to ask
"what does this proof actually rest on?", which is the question that matters.

Rule of thumb: if deleting the other node would make the statement
*ungrammatical*, it is context. If it would make the proof *invalid*, it is a
proof dependency. Both can be true; list it in both places.

---

## 6. Conventions, and the closure convention

Some questions have no universally right answer and must simply be answered
consistently. The mechanism is `conventions` in the module manifest: state the
rule once, and reviewers apply it instead of arguing per node.

### <a id="the-closure-convention"></a>The closure convention

Closure (A1: `a·b ∈ G`) is what makes every product term denote an element of G.
Deciding when to cite it is the module's hardest convention question, and the
pilot got it wrong the first time. The history is worth keeping, because it is a
concrete example of how a convention can quietly void an edge set.

**The rule now:** a step cites A1 exactly when it **instantiates a quantified
statement at a term that is itself a product**. Every axiom and theorem here
quantifies over elements of G, so that instantiation is licensed only once the
product is known to lie in G. If an earlier step already established that
particular membership, cite the step instead.

**The rule before:** cite A1 only where a step's *content* was specifically that
some element lies in G.

An adversarial review rejected the old rule, correctly. The objection was not
that it hid too much — it was that **it was not a predicate on the mathematics
at all.** Which steps have membership as their content is the author's choice of
what to write down, so two contributors could apply the rule to the same proof
and disagree, with no fact settling it. The consequences in the pilot were
measurable: closure was load-bearing but uncited at seven steps (T2 s5, T3 s5,
T6 s2/s5/s8/s11, T8 s4), while A1's only two edges came from optional
bookkeeping lines — one of which nothing cited, so it was dead. A1 had edges,
and they pointed at the wrong places. Fixing the rule took the module from 52 to
63 proof edges.

The general principle, which generalises past closure:

> A convention must be a predicate on the mathematics, not on the prose. If two
> careful contributors can apply it to the same proof and disagree, it is not a
> convention — it is a gap, and the edges it governs carry no information.

The secondary principle: **the validator cannot enforce this.** No program can
tell which terms in a natural-language claim are products. It is enforced by
review, which is exactly why it has to be written down where reviewers will read
it. Later modules may choose a different rule as long as the manifest states it
and it survives that test.

---

## 7. `status` — what the project is willing to assert

| status | Means | Enforced by |
|---|---|---|
| `draft` | Someone wrote it. Nothing more. | default |
| `reviewed` | Two independent humans checked every step. | warning if fewer than two `reviewed_by` |
| `verified` | **A proof assistant checked it**, and `formalization` points at what. | **error** if `formalization` is empty |

That last row is the load-bearing one. A graph of informal proofs has no oracle:
nothing can automatically tell you whether step 7 really follows. The honest
response is not to pretend otherwise, but to make the strongest claim
machine-checkable and refuse to let anything else wear its name. `verified`
without a link is a CI failure, not a judgement call.

Note what this implies: **most of the graph will say `draft` for a long time.**
That is the accurate state of affairs, and a project that finds this embarrassing
will be tempted to fix it the wrong way.

### `provenance.assisted_by`

If a language model drafted any part of a node — statement, proof, or the
citation list — say so. This is not a purity test; LLM-drafted nodes are welcome
and this repository contains some. It is that a reviewer's job differs completely
depending on the answer, because the characteristic failure of a machine-drafted
proof is a citation that is plausible and wrong. Undisclosed machine text is the
fastest way for a project like this to lose the only thing it has.

---

## 8. What the validator checks, and what it cannot

`python -m proofweb validate` enforces:

- every node validates against `schema/node.schema.json`
- node ids are unique; every cited id exists
- steps are numbered `1..n`; step ids are unique and never reused within a proof
- both `s:<id>` and `sK` references resolve and point strictly backwards
- (warning) a step cites an earlier step by ordinal where a stable id exists
- cited hypotheses are declared; `hyp` is unambiguous
- theorems have proofs; axioms, definitions and background do not
- **the proof graph is acyclic** — nothing is used, transitively, in its own proof
- a module cites only itself and its declared `imports`
- `status: verified` has a `formalization`
- (warnings) unused hypotheses, unused assumptions, disconnected theorems,
  missing provenance

It cannot check whether a step's claim follows from its justifications. No
program can, for informal mathematics. That gap is the reason `formalization`
exists, and the reason `reviewed` requires two humans.

Be clear-eyed about what this buys: the validator guarantees the graph is
**internally honest**, not that the mathematics is **true**. Those are different
properties, and only one of them is automatable at this layer.

---

## 9. Stability

The format is version 0. Breaking changes are possible and will come with a
migration script under `tools/`. The one thing that will not change is §1: if
dependencies ever become hand-declared, this stops being the same project.
