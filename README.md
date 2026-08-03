# ProofWeb

**A knowledge graph of mathematics whose edges are derived from proofs, not
declared beside them.**

[![CI](https://github.com/SanTanBan/ProofWeb/actions/workflows/ci.yml/badge.svg)](https://github.com/SanTanBan/ProofWeb/actions/workflows/ci.yml)
&nbsp;·&nbsp; 14 nodes &nbsp;·&nbsp; 63 proof edges &nbsp;·&nbsp; 0 reviewed &nbsp;·&nbsp; MIT (tools) + CC BY 4.0 (content)

> Renamed from **ProofGraph** in August 2026 — "proof graph" is a generic term
> used by several unrelated projects, and this one would rather be findable
> than fought over. Old links redirect. (The name ProofWeb also has history:
> Radboud University's web interface for teaching Coq, ~2007–2013. See the
> [comparison table](#how-this-differs-from-neighbouring-projects) below.)

```
T6 — The inverse of a product reverses the order
  For all a, b in G, (a·b)' = b'·a'.

  Proof:
    ...
     12. (a·b)' = b'·a'  [T6#conclude]
         by s:candidate-in-g, s:product-is-e, s:canonical-inverse,
            T4 (Inverses are unique), L1 (Equality is an equivalence relation), A1 (Closure)

  Rests on 8 node(s), transitively:
    A2     Associativity          — used at #reassociate-outer, #reassociate-inner
    A4     Existence of inverses  — used at #candidate-in-g, #inner-inverse, #outer-inverse
    T2     Left cancellation      — indirectly
    T4     Inverses are unique    — used at #conclude
```

That last line is the whole project. `T6 → T4` is not a fact about two theorems.
It is the fact that **`T6#conclude`** is where uniqueness of inverses enters, and
the graph knows it because the proof said so.

Note the address. Not "step 12" — an ordinal goes stale the moment somebody
inserts a step, and a citation that silently changes meaning is the worst defect
this format could have. Every step carries an immutable id; `n` is presentation
only. See [SPEC.md §4a](docs/SPEC.md#4a-step-identity-n-is-not-an-address).

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

## Two tracks, one graph

**The formal track (mechanistic, no AI).** Edges extracted from machine-checked
proofs by [`proofweb.metamath`](tools/proofweb/metamath.py): a pure-Python
Metamath parser, compressed-proof decoder and **verifier** that replays every
proof — substitution, stack discipline, disjoint-variable conditions — before
emitting a single edge. An extracted edge is a fact about a checked proof, not
anyone's opinion. Scale-tested against the real thing: **all 47,588 proofs of
set.mm verify in 39 seconds, zero failures**, matching the canonical
`mmverify.py` verdict on the same snapshot. The Lean and Rocq paths are
designed in [docs/FORMAL-TRACK.md](docs/FORMAL-TRACK.md).

**The informal track (human, reviewed).** The YAML format under `graph/` for
mathematics that has *no* formal proof yet — where step-level provenance is a
human judgement, which is exactly why it is the subject of the measurement
study in [docs/ROADMAP.md](docs/ROADMAP.md) rather than a settled method.

Same schema, same queries, same viewer over both. Each track is the other's
control group.

## Try it in two minutes

```bash
git clone https://github.com/SanTanBan/ProofWeb && cd ProofWeb/tools
pip install -r requirements.txt

python -m proofweb validate --strict     # every machine-checkable invariant
python -m proofweb why T6                # what it rests on, and at which step
python -m proofweb stats
python -m proofweb render html -o ../build/proofweb.html
```

And the formal track, on real mathematics:

```bash
curl -L -o ../corpora/set.mm https://raw.githubusercontent.com/metamath/set.mm/develop/set.mm
python -m proofweb extract ../corpora/set.mm --stop-at id -o ../examples/setmm.json --html ../build/setmm.html
python -m proofweb why id --json ../examples/setmm.json       # id, back to ax-1/ax-2/ax-mp
python -m proofweb uses ax-mp --json ../examples/setmm.json   # every STEP that invokes ax-mp
```

That last query — *every proof step in the corpus that invoked a given theorem,
with the claim proved at that step* — is the reverse step-level lookup that,
per [the prior-art survey](docs/PRIOR-ART.md), no existing search engine serves.

Open `build/proofweb.html`, click node **T6**, then click its last step. Exactly
the edges that step created light up — `T6→T4`, `T6→L1`, `T6→A1` — while the
`s:`-prefixed citations create none, because they point at earlier steps of the
same proof. That is the thesis, made clickable. The file is self-contained: no
build step, no network, no dependencies.

## What is in here

| | |
|---|---|
| [`tools/proofweb/metamath.py`](tools/proofweb/metamath.py) | **The formal track.** Metamath parser + verifier + step-level extractor. Mechanistic: no AI anywhere in the pipeline. |
| [`graph/group-theory-elementary/`](graph/group-theory-elementary) | The informal-track pilot. 4 group axioms, 2 background principles about equality, 8 theorems. |
| [`examples/setmm-through-id.json`](examples/setmm-through-id.json) | A sample extraction from set.mm (public domain), through the theorem `id`: 23 nodes, 17 kernel-checked theorems. |
| [`schema/node.schema.json`](schema/node.schema.json) | What a node file may contain. |
| [`tools/proofweb/`](tools/proofweb) | Loader, validator, graph queries, exporters (dot / mermaid / json / html). ~2,000 lines, two dependencies, 63 tests. |
| [`docs/FORMAL-TRACK.md`](docs/FORMAL-TRACK.md) | The extraction architecture: Metamath (built), Lean (integration with LeanDojo), Rocq (greenfield spec), and how a proof graph honestly helps attack open problems. |
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
   after someone reorders the proof? Nothing in the literature solves this. It is
   a design problem, and it is the real technical content — so this repository
   has taken a position on it (`T6#conclude`, immutable ids, a test that inserts
   a step and asserts every address survives). Whether that position is the right
   one is exactly the kind of argument worth having.

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

Informal track: fourteen hand-written nodes, one module, **zero reviewed** —
two independent humans have to sign off on a node and none has yet.

Formal track: the Metamath pipeline is real and tested (63 tests, including
replaying the opening of set.mm with zero failures), and extracted nodes are
`verified` in the strict sense: a machine replayed each proof from the axioms
before any edge was emitted. Lean and Rocq extraction are designs, not code.

One maintainer, not a mathematician by training. That is the entire state of
the project.

## Citing

Code is MIT; graph content and extracted datasets are CC BY 4.0 — use anything
here for anything, including commercially, with attribution back to this
repository. [CITATION.cff](CITATION.cff) has the reference; GitHub's "Cite this
repository" button reads it. Extractions of set.mm inherit nothing restrictive:
set.mm is public domain.

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
