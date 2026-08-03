# Prior art: does this already exist?

**Yes. Emphatically, and in several mature forms.** This page exists because the
honest answer to "has anyone built a graph connecting axioms to theorems to
proofs?" is not "no, what a good idea" — it is "yes, since the 1990s, at a scale
of hundreds of thousands of nodes, and here is where to find it."

Everything below was verified against a live URL in July 2026. Where something
could not be verified, that is stated.

If you are about to invest time in this project, read this page first. It is
also the page that tells you what is *not* solved, which is where any honest
contribution has to live.

---

## 1. The graph exists inside every formal proof library

In a formal library, "theorem A's proof used theorem B" is not curated by a
human. The proof checker records it. Extracting the graph is a script.

| Project | Scale | Node / edge | |
|---|---|---|---|
| [Metamath / set.mm](https://us.metamath.org/mpeuni/mmset.html) | 20 axioms + 2 rules; 26k+ theorems (41k+ with mathboxes) | theorem / "this proof step invokes that statement" | Every theorem page publishes the proof with each step hyperlinked to its justification, a *"referenced by"* reverse-dependency list, and the full transitive closure of axioms used. The `2+2=4` page reports its own closure: 2,913 subtheorems, 26,323 steps. |
| [mathlib4](https://leanprover-community.github.io/mathlib_stats.html) | 134,791 definitions, 283,487 theorems, 772 contributors | declaration | The richest substrate available. Note the trap: the *official* docs expose statement-level hyperlinks and module imports, **not** proof dependencies. |
| [Isabelle AFP](https://www.isa-afp.org/statistics/) | 1,012 entries, 604 authors, ~323,000 lemmas | entry (coarse) | Comparable in size to mathlib; publishes no theorem-level dependency graph. |
| [Mizar MML](https://mizar.uwb.edu.pl/library/) | 1,493 articles, 35+ years of continuous maintenance | article, natively | The longest-running proof that community-maintained formal mathematics is sustainable. |
| [MMLKG](https://mmlkg.uwb.edu.pl/) | Mizar-derived | typed nodes + ontology, in **Neo4j** | If you are imagining "a Neo4j of mathematics" — it exists, it is deployed, and it is published in *Nature Scientific Data*. |

**This is the single most important fact on the page.** Metamath has been
publishing an axiom→theorem→proof graph with forward edges, reverse edges, and
full axiom traceability, on the open web, for roughly twenty-five years.

## 2. It exists for *informal*, human-written mathematics too

The usual hope at this point is "yes, but only for formal libraries — nobody has
done it for ordinary mathematical prose." That is also not true.

**[The Stacks Project](https://stacks.math.columbia.edu/statistics)** — 21,446
tags (12,587 lemmas, 330 propositions, 214 theorems, 1,721 definitions), written
in LaTeX by humans, with forward *and transitive reverse* dependencies computed
for every result. Nakayama's lemma ([tag 00DV](https://stacks.math.columbia.edu/tag/00DV))
reports 3 results used in its proof, 5 in preliminaries, 119 tags citing it
directly, and **6,705 results transitively depending on it**.

This is the closest existing thing to "a knowledge graph of mathematics that a
mathematician actually reads," and it is a success. Its two decisive design
choices — permanent immutable identifiers per result, and precomputed transitive
closure in both directions — are worth copying outright.

**[leanblueprint](https://github.com/PatrickMassot/leanblueprint)** is the most
widely *used* dependency graph in mathematics today. Authors declare `\uses{}`
edges by hand; the graph is rendered coloured by formalization progress. Tao's
PFR project and the Fermat's Last Theorem project both run on it. The lesson: the
killer application of a proof graph turned out to be **project management for
collaborative formalization**, not browsing.

**[KnowTeX](https://arxiv.org/abs/2601.15294)** (2026) generalises the `\uses`
idea to arbitrary LaTeX documents, decoupled from Lean.

## 3. It has already been extracted at scale and analysed in the literature

- **[The Network Structure of Mathlib](https://arxiv.org/abs/2604.24797)**
  (Li–Peng–Severini–Shafto, Apr 2026) — a multilayer graph of **308,129
  declarations, 8.4 million edges, 7,563 modules**. Distinguishes genuine
  mathematical dependency from compiler-synthesized noise. Finds that centrality
  is dominated by language *infrastructure*, not mathematical importance, and
  that 50.9% of coupling crosses the human namespace taxonomy.
- **[TheoremGraph / theoremsearch.com](https://arxiv.org/abs/2606.25363)**
  (Jun 2026) — 388,105 formal declaration nodes, 11.3M typed edges across 25 Lean
  projects, joined against **11.7M theorem-like environments parsed from arXiv**.
  The most ambitious existing attempt at a knowledge graph of all mathematics.
  Sobering number: only ~48k confident formal↔informal matches out of 11.7M.
- **[Structure in Theorem Proving](https://arxiv.org/abs/2209.13305)** (2022) —
  the AFP dependency graph is scale-free. If you were planning to discover that,
  it is discovered.
- **[Mathematical Knowledge Bases as Grammar-Compressed Proof Terms](https://arxiv.org/abs/2505.12305)**
  (Wernhard & Zombori) — reframes the whole enterprise: a library of named lemmas
  *is* a compression scheme over flat proof trees back to the axioms. The
  dependency graph and the knowledge base are the same object viewed differently.

## 4. Step-level granularity is also taken — for Lean

This is the specific claim most likely to be made by a new project, so it needs
the sharpest answer.

**[LeanDojo](https://leandojo.org/leandojo.html) has done step-level premise
attribution since 2023.** LeanDojo Benchmark 4 records **122,517 theorems,
259,580 tactics, 167,779 premise references**. Its
[`TracedTactic.get_annotated_tactic()`](https://leandojo.readthedocs.io/en/latest/traced_data.html)
returns the tactic string with premises marked inline plus their file positions —
documented example: `rw [add_comm b]` → `rw [<a>add_comm</a> b]`, together with
the proof state before and after.

That is, verbatim, "which step used which prior result," for all of mathlib.

**And "just look at the proof term" is substantially correct.** A Lean proof term
is a typed `Expr` whose `const` subnodes name every lemma used, at a specific
structural position. Rocq is the same — `Print Assumptions` and
`Print All Dependencies` already walk the term. The information is not missing
from either system. It is **unexposed and unindexed, not undiscovered.** Anyone
claiming to "recover hidden structure" is overselling.

[Lean Atlas](https://github.com/NyxFoundation/lean-atlas) (Mar 2026) is the
current frontier for navigable graphs: it classifies each edge eight ways by
source kind × dependency site (in the *type* vs in the *value*) × target kind,
and prunes to the minimal node set whose correctness affects a target theorem.
That "type vs value" axis stops exactly one level above proof-step granularity.

## 5. What is genuinely not solved

Verified gaps, roughly in order of how defensible they are:

1. **Reverse step-level lookup.** No index anywhere answers *"show me every proof
   step in mathlib that invoked `add_comm`, with the goal state at that step."*
   LeanDojo has the raw data and ships it as a flat ML training corpus on Zenodo.
   The three search engines that serve queries — [Loogle](https://loogle.lean-lang.org/),
   LeanSearch, LeanExplore — all index what a declaration *says*, never where it
   is *used*. LeanExplore even computes PageRank over a dependency graph and then
   discards the graph, keeping the scalar.
2. **Rocq has no LeanDojo.** Step-level premise attribution does not exist for
   Rocq in any form. `coq-dpdgraph` is object-level. Alectryon gives per-sentence
   goal states with zero premise links. And the substrate just shifted:
   **SerAPI is discontinued** — its successor is `coq-lsp`/`rocq-lsp` — so there
   is no incumbent to displace. The Rocq roadmap does not mention dependency
   graphs.
3. **Stable addressing for sub-proof nodes.** If an edge points at "step 3 of the
   proof of X", that node needs an identity surviving a refactor of the proof.
   Nothing provides this. Declaration-level tools get identity free from
   fully-qualified names. **This is the actual hard technical content** — not the
   extraction. (The Rocq 9.0 stdlib rename, `Coq.` → `Stdlib.`, shows even
   declaration names churn.)
4. **Proof-term subterm → source span as a queryable artefact.** Both kernels
   know it; no released tool emits it. `doc-gen4` renders no proof body at all —
   the richest structure in the ecosystem is invisible in the official docs of
   both provers.
5. **Cross-prover edges.** Lean↔Rocq linking does not exist at any granularity.
   Fair warning: partly because aligning two different type theories is genuinely
   hard, not merely unbuilt.
6. **Research-level mathematics.** [Formal Abstracts](https://formalabstracts.github.io/)
   — Tom Hales' project to attach formal statements to every research paper — is
   **dormant**. The README still says "currently in the design phase" and "not
   actively seeking contributions" (223 commits, 0 open PRs). This is the largest
   unoccupied territory, and the fact that Hales did not carry it through should
   be read as a signal about difficulty, not as an opening.

## 6. Things frequently mistaken for this, which are not

- **[nLab](https://ncatlab.org/nlab/show/HomePage)** — hyperlinks mean "related
  to," not "used in the proof of." Multiple theorems per page. Rich, but not a
  dependency graph.
- **[OEIS](https://en.wikipedia.org/wiki/On-Line_Encyclopedia_of_Integer_Sequences)**
  — 390,000+ sequences, 60 years, thriving. But `Cf.` links are human-authored
  *relatedness*, not entailment. The transferable lesson is **governance**:
  permanent unique identifiers and a real editorial board. Not the graph model.
- **[import-graph](https://github.com/leanprover-community/import-graph)** — file
  level. An import edge is a coarse over-approximation of logical dependency;
  median scope utilization measured at **1.6%**.
- **[Connected Theorems](https://arxiv.org/abs/2508.17596)** — bibliometrics.
  "Paper A cites paper B" is a sociological relation, not a logical one.
- **ProofWiki** — theorem-level by construction and the right shape, but
  dependencies are raw hyperlinks, never computed or transitively closed.
  *Unverified:* proofwiki.org returned HTTP 403 to every automated fetch, so its
  current size and health are not established here.

---

## What this means for ProofWeb

Three conclusions, stated plainly because the alternative is wasting people's
time:

1. **Do not build a new axiom→theorem→proof graph from scratch and expect it to
   be novel.** It is extractable in minutes from set.mm, mathlib4, or the Stacks
   Project, and at least four 2025–2026 papers have already published
   large-scale analyses.
2. **The defensible sentence is not "we record which step uses which lemma."**
   LeanDojo does that. It is, at most: *step-level proof provenance as a
   first-class navigable, reverse-queryable object across a whole library — and
   the first such thing for Rocq at all.* That is an increment over a March 2026
   system, not open field.
3. **The hard problem is stable identity for sub-proof nodes** (gap 3), and it is
   a design problem, not a scraping problem. A project that solves that has
   something. A project that produces another pretty picture of mathlib does not.

See [RISKS.md](RISKS.md) for the argument that even the defensible version fails.

### Coverage caveats

Stated so this page is not over-trusted. proofwiki.org blocked all automated
access (403). The Lean FRO Year-3 roadmap could not be fetched (the documented
URL 404s) — if the FRO has proof-exploration tooling planned, gaps 1 and 4 shrink
and **you should check this manually before committing to either**. LeanDojo's
current maintenance status and whether Benchmark 4 tracks recent mathlib were not
verified; if it has bit-rotted, gap 1 gets easier, and if it has been extended,
harder. Mizar's theorem counts and the "AFP is 2–3× mathlib" claim come from
search snippets, not fetched pages.
