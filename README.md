# ProofGraph

**A knowledge graph of mathematics whose edges are derived from proofs, not
declared beside them.**

[![CI](https://github.com/OWNER/proofgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/proofgraph/actions/workflows/ci.yml)
&nbsp;·&nbsp; 14 nodes &nbsp;·&nbsp; 52 proof edges &nbsp;·&nbsp; MIT (tools) + CC BY 4.0 (content)

```
T6 — The inverse of a product reverses the order
  For all a, b in G, (a·b)' = b'·a'.

  Proof:
    ...
     12. (a·b)' = b'·a'
         by s10, s11, T4 (Inverses are unique), L1 (Equality is an equivalence relation)

  Rests on 8 node(s), transitively:
    A2     Associativity                  — used directly at step 2, 3
    A4     Existence of inverses          — used directly at step 1, 4, 9, 11
    T2     Left cancellation              — indirectly
    T4     Inverses are unique            — used directly at step 12
```

That last line is the whole project. `T6 → T4` is not a fact about two theorems.
It is the fact that **step 12 of T6** is where uniqueness of inverses enters, and
the graph knows it because the proof said so.

---

## The idea in one paragraph

Most mathematical knowledge graphs ask an author to write, next to each theorem,
a list of what it depends on. That list is an opinion, and it drifts from the
proof the moment either changes. Here, **a node never declares its dependencies**
— it declares a proof, each of whose steps carries its own justification, and the
edges are derived from those justifications. You cannot cite a lemma you did not
use (the citation would be an unjustified step). You cannot use one without the
edge appearing (the step would have no justification). The graph becomes an
assertion about the mathematics that can be checked, and CI fails when it is
wrong about itself.

## Try it in two minutes

```bash
git clone <repo-url> && cd proofgraph/tools
pip install -r requirements.txt

python -m proofgraph validate --strict     # every machine-checkable invariant
python -m proofgraph why T6                # what it rests on, and at which step
python -m proofgraph stats
python -m proofgraph render html -o ../build/proofgraph.html
```

Open `build/proofgraph.html`, click node **T6**, then click **step 12**. Exactly
the two edges that step created light up — `T6→T4` and `T6→L1` — while `s10` and
`s11` create none, because they are references to earlier steps of the same
proof. That is the thesis, made clickable. The file is self-contained: no build
step, no network, no dependencies.

## What is in here

| | |
|---|---|
| [`graph/group-theory-elementary/`](graph/group-theory-elementary) | The pilot. 4 group axioms, 2 background principles about equality, 8 theorems. Every proof cites only nodes in this module. |
| [`schema/node.schema.json`](schema/node.schema.json) | What a node file may contain. |
| [`tools/proofgraph/`](tools/proofgraph) | Loader, validator, graph queries, exporters (dot / mermaid / json / html). ~1,000 lines, two dependencies. |
| [`docs/SPEC.md`](docs/SPEC.md) | What a node file *means*. Start here to contribute mathematics. |
| [`docs/PRIOR-ART.md`](docs/PRIOR-ART.md) | **Read this before anything else.** Who has already done this, and what is genuinely left. |
| [`docs/RISKS.md`](docs/RISKS.md) | An adversarial review arguing this project should fail. Kept in its own repository on purpose. |

The pilot is deliberately boring mathematics — results in every first algebra
course — because what is being tested is the **method**, not the content. If
elementary group theory cannot survive the validator, nothing harder will.

## Honesty about prior art

**Graphs connecting axioms to theorems to proofs already exist, at scale, and
have for decades.** This project does not claim otherwise, and
[docs/PRIOR-ART.md](docs/PRIOR-ART.md) sets out the evidence in detail:

- **[Metamath / set.mm](https://us.metamath.org/mpeuni/mmset.html)** — 20 axioms,
  26k+ theorems, every proof step hyperlinked to its justification, reverse
  dependencies, full transitive axiom closure. On the open web since the 1990s.
- **[The Stacks Project](https://stacks.math.columbia.edu/statistics)** — 21,446
  tags of human-written LaTeX with precomputed transitive dependencies both ways.
  Nakayama's lemma reports 6,705 results depending on it.
- **[LeanDojo](https://leandojo.org/leandojo.html)** — step-level premise
  attribution across mathlib since 2023: 122,517 theorems, 259,580 tactics,
  167,779 premise references.
- **[mathlib4](https://leanprover-community.github.io/mathlib_stats.html)** —
  283,487 theorems; [network analysis published](https://arxiv.org/abs/2604.24797)
  at 308,129 declarations and 8.4M edges.
- **[TheoremGraph](https://arxiv.org/abs/2606.25363)** — 388k formal nodes and
  11.3M edges joined against 11.7M arXiv statements.

And Lean and Rocq proof terms *are* the dependency structure — it is unexposed
and unindexed, not undiscovered. Anyone claiming to recover hidden structure is
overselling.

**What appears genuinely unoccupied**, and all this project can honestly aim at:

1. Step-level provenance for mathematics that has **not** been formalized.
   LeanDojo reads proofs a kernel already checked; Stacks and `leanblueprint`
   handle prose but at *statement* granularity.
2. **Rocq has no LeanDojo.** No step-level premise attribution exists for Rocq at
   all, and `SerAPI` is discontinued — no incumbent to displace.
3. **Stable identity for a sub-proof node.** What is "step 3 of the proof of X"
   after someone reorders the proof? Nothing solves this. It is a design problem,
   and it is the real technical content.

## Honesty about failure

[docs/RISKS.md](docs/RISKS.md) is an adversarial review of this project,
commissioned against itself and kept in the repository. It argues, among other
things, that a hand-authored graph is a drift-prone duplicate of what a compiler
already computes exactly; that verification cost equals authoring cost, so LLM
assistance saves nothing; that contributor supply, not tooling, is the binding
constraint; and that a beautiful 14-node demo systematically misleads about
feasibility at 10,000 nodes.

It also lists **kill criteria** — the observable conditions under which this
should be abandoned. A project unwilling to write those down is not being serious
with the people it is asking for help.

## Status

Fourteen nodes. One module. **Zero nodes are `verified`**, because none has been
checked by a proof assistant yet — and `verified` without a `formalization` link
is a CI failure here, not a judgement call. One maintainer, not a mathematician
by training.

That is the entire state of the project.

## Contributing

The most valuable contribution is **finding a proof step that does not follow**.
See [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/CALL-FOR-COLLABORATION.md](docs/CALL-FOR-COLLABORATION.md). LLM-assisted
contributions are welcome and must be disclosed; bulk generation is not, because
nobody can review it.

---

## Reading list

Curated and dated. Entries marked ⚑ are the ones worth your time if you read
nothing else.

### Proof assistants

- ⚑ [Lean](https://lean-lang.org/) · [mathlib4 statistics](https://leanprover-community.github.io/mathlib_stats.html) · [Lean Zulip](https://leanprover.zulipchat.com/)
- ⚑ [The Rocq Prover](https://rocq-prover.org/) (formerly Coq; v9.2.0, Mar 2026) · [Rocq Discourse](https://discourse.rocq-prover.org/)
- [Coq vs Lean, honestly compared](https://proofassistants.stackexchange.com/questions/153/what-are-the-main-differences-between-coq-and-lean) · [r/math thread](https://www.reddit.com/r/math/comments/vmzuot/coq_vs_lean_what_are_your_opinions/)
- [itp_proof_education](https://github.com/rmahinpei/itp_proof_education) — teaching materials for interactive theorem proving

### Existing graphs of mathematics — read before proposing anything

- ⚑ [Metamath Proof Explorer](https://us.metamath.org/mpeuni/mmset.html) — the original, and still the clearest
- ⚑ [Stacks Project statistics](https://stacks.math.columbia.edu/statistics) — the proof that this works for informal mathematics
- ⚑ [LeanDojo](https://leandojo.org/leandojo.html) — step-level premise data, already extracted
- [The Network Structure of Mathlib](https://arxiv.org/abs/2604.24797) (Apr 2026)
- [TheoremGraph](https://arxiv.org/abs/2606.25363) / [theoremsearch.com](https://www.theoremsearch.com) (Jun 2026)
- [leanblueprint](https://github.com/PatrickMassot/leanblueprint) — the dependency graph mathematicians actually use daily
- [MMLKG](https://mmlkg.uwb.edu.pl/) — a deployed Neo4j knowledge graph of Mizar
- [Mathematical Knowledge Bases as Grammar-Compressed Proof Terms](https://arxiv.org/abs/2505.12305) — a library of lemmas *is* a compression of proof trees
- [Formal Abstracts](https://formalabstracts.github.io/) — the great unrealized ambition; dormant, and instructive

### AI for mathematics — 2025–2026 milestones

- ⚑ [Towards Autonomous Mathematics Research](https://arxiv.org/abs/2602.10177) (Feb 2026) — DeepMind's **Aletheia**; the primary source. Solved four open problems from the Erdős database.
- ⚑ [Accelerating discovery with Gemini Deep Think](https://deepmind.google/blog/accelerating-mathematical-and-scientific-discovery-with-gemini-deep-think/) (Feb 2026)
- [AI disproves a decades-old conjecture](https://www.smithsonianmag.com/smart-news/ai-disproves-a-decades-old-mathematical-idea-the-biggest-conjecture-that-the-tech-has-played-a-role-in-yet-180989189/) (Smithsonian, Jul 2026) — Levent Alpoge disproves the Jacobian conjecture with a 3-D counterexample
- [Amateur armed with ChatGPT settles a 60-year-old problem](https://www.scientificamerican.com/article/amateur-armed-with-chatgpt-vibe-maths-a-60-year-old-problem/) (Scientific American, Apr 2026) — an Erdős conjecture on primitive sets
- [ChatGPT resolves a conjecture in geometry](https://scitechdaily.com/for-the-first-time-chatgpt-has-solved-an-unproven-math-problem-in-geometry/) (Mar 2026) — VUB press release; Conjecture 20 of Ran & Teng
- [Erdős Problems database](https://www.erdosproblems.com/) — where several of the above landed

### Hard targets

- ⚑ [The Ramanujan Challenge for AI](https://arxiv.org/abs/2607.09721) (Jun 2026) — ten unpublished formulas posed as a benchmark, eight with proofs withheld, two genuinely open
- [The Ramanujan Machine](https://www.ramanujanmachine.com/) — automated conjecture generation for constants
- [Clay Millennium Problems](https://www.claymath.org/millennium-problems/) — see [RISKS.md](docs/RISKS.md#overclaiming) before putting these in a proposal

### Funding and competitions

See [docs/FUNDING.md](docs/FUNDING.md) for status as of July 2026 — what is open,
what is closed, and why money is not the binding constraint.

- [AI for Math Fund](https://www.renaissancephilanthropy.org/ai-for-math-fund) — seed grants rolling
- [SAIR Foundation competitions](https://competition.sair.foundation/) — highest strategic alignment
- [AIMO Prize](https://aimoprize.com/) · [AI Grant](https://aigrant.org/) · [ARIA](https://www.aria.org.uk/opportunity-spaces/mathematics-for-safe-ai/) · [OSV Fellowship](https://www.osvfellowship.com/) · [1517 Medici](https://www.1517fund.com/medici)

---

*Tools MIT, content CC BY 4.0. See [LICENSE](LICENSE) and [LICENSE-CONTENT](LICENSE-CONTENT).*
