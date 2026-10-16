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

**The formal track (mechanistic, no AI).** Edges read off machine-checked
proofs, never typed by hand. Two corpora, two strengths of claim:

- **Metamath** — [`proofweb.metamath`](tools/proofweb/metamath.py) is a
  pure-Python parser, compressed-proof decoder and **verifier** that replays
  every proof (substitution, stack discipline, disjoint-variable conditions)
  before emitting a single edge. **All 47,588 proofs of set.mm verify in 39
  seconds, zero failures**, matching `mmverify.py` on the same snapshot.
  `derivation: kernel-replay`.
- **Lean / Prove2Me** — [`proofweb.leanp2m`](tools/proofweb/leanp2m.py) imports
  Anthropic's **13-million-line, 29,511-theorem Lean proof of Fermat's Last
  Theorem** from text alone, no toolchain. Six of the figures its authors
  published about it are reproduced exactly (see below).
  `derivation: imports` — checked upstream, not replayed here, and the tools
  say so on every node.
- **Any Lake project, at module level** —
  [`proofweb.leanlake`](tools/proofweb/leanlake.py) reads ordinary Lean
  libraries such as `openai/math` and the Navier–Stokes certificates, where
  text supports only file-level edges. Every node is `draft`, and the audit
  reads each project's `formalization.yaml` catalogue to report which results
  import other results and which have a `sorry` below them.

The Rocq path is specified in [docs/FORMAL-TRACK.md](docs/FORMAL-TRACK.md) and
is the most valuable thing an outside contributor could pick up.

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

And on the largest machine-written proof in existence:

```bash
git clone --filter=blob:none --sparse --depth 1 -c core.autocrlf=false \
    https://github.com/anthropics/fermats-last-theorem ../corpora/fermats-last-theorem
git -C ../corpora/fermats-last-theorem sparse-checkout set Theorems P2M Definitions

python -m proofweb import-lean ../corpora/fermats-last-theorem \
    --root fermat_last_theorem -o ../build/flt.json      # ~12 min, no Lean needed
python -m proofweb audit --json ../build/flt.json --compare flt \
    --root fermat_last_theorem --report ../build/flt-audit.md
python -m proofweb uses ModularForm_S2_Gamma0_2_eq_zero --json ../build/flt.json
python -m proofweb render html --json ../build/flt.json \
    --focus FreyPackage_of_counterexample --radius 2 -o ../build/focus.html
```

**The audit recomputes what the corpus's authors published about it** — their
figures come from their own text-only generator, so agreement means two
independently written parsers read 13 million lines the same way:

| | ProofWeb | Upstream | |
|---|---:|---:|---|
| theorem nodes | 29,511 | 29,511 | match |
| definition modules | 1,450 | 1,450 | match |
| theorem → theorem citations | 106,853 | 106,853 | match |
| reachable from the goal | 29,489 | 29,489 | match |
| theorems outside that closure | 22 | 22 | match |
| of those, cited by nobody | 19 | 19 | match |

Plus what only a step-level view can say: **276,403 step-level proof edges**,
each addressed to a line of a named proof file, so `uses` becomes a reverse
index over the whole corpus. 81.1% of the citations found in the text are fully
qualified; the audit grades the rest rather than hiding them. A seventh figure,
citations never named in a proof, matches exactly when upstream's rule is
replayed. Getting there found two bugs in this importer, described in
[FORMAL-TRACK.md](docs/FORMAL-TRACK.md) §3a.

Open `build/proofweb.html`, click node **T6**, then click its last step. Exactly
the edges that step created light up — `T6→T4`, `T6→L1`, `T6→A1` — while the
`s:`-prefixed citations create none, because they point at earlier steps of the
same proof. That is the thesis, made clickable. The file is self-contained: no
build step, no network, no dependencies.

## What is in here

| | |
|---|---|
| [`tools/proofweb/metamath.py`](tools/proofweb/metamath.py) | **Formal track, Metamath.** Parser + verifier + step-level extractor; replays every proof before emitting an edge. |
| [`tools/proofweb/leanp2m.py`](tools/proofweb/leanp2m.py) | **Formal track, Lean.** Imports a Prove2Me corpus (statements, proofs, definitions) from text, with no Lean toolchain. |
| [`tools/proofweb/leanlake.py`](tools/proofweb/leanlake.py) | **Formal track, any Lake project.** One node per source file, import edges labelled as an upper bound, catalogued results and Comparator configurations located. Nothing marked verified. |
| [`tools/proofweb/audit.py`](tools/proofweb/audit.py) | Checks an imported corpus against the figures its makers published, and reports what the text alone cannot account for. |
| [`graph/group-theory-elementary/`](graph/group-theory-elementary) | The informal-track pilot. 4 group axioms, 2 background principles about equality, 8 theorems. |
| [`examples/setmm-through-id.json`](examples/setmm-through-id.json) | A sample extraction from set.mm (public domain), through the theorem `id`: 23 nodes, 17 kernel-checked theorems. |
| [`schema/node.schema.json`](schema/node.schema.json) | What a node file may contain. |
| [`tools/proofweb/`](tools/proofweb) | Loader, validator, graph queries, exporters (dot / mermaid / json / html / focused views). ~5,000 lines, two dependencies, 141 tests (plus 9 more against the real FLT corpus, skipped unless fetched). |
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
- **[Prove2Me](https://arxiv.org/abs/2608.28433)** — the platform behind the FLT
  corpus: a construction-time DAG of theorem statements that agents coordinate
  around. Statement-level, authenticated API, no bulk export. Its own paper lists
  *"how to extract human-legible insight from machine-generated proofs"* as open.

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

## How this differs from neighbouring projects

The name "proof graph" turns out to be close to generic: a GitHub census (August
2026) finds **18 repositories named `proofgraph`, the earliest from 2017**, most
of them unrelated to mathematics. The table below compares this project against
every close repository found, plus the systems that occupy the adjacent space.
Every date comes from the GitHub API, RDAP/WHOIS, CTAN, or archived pages,
checked in August 2026. The table describes artefacts, not motives.

| Neighbouring project | Core idea | What is in the repo | How edges/content arise | Vision & status (Aug 2026) | How ProofWeb differs |
|---|---|---|---|---|---|
| **[ProofGraph](https://proofgraph.org/)** (proofgraph.org, J. Llovet) — announced 2026‑03‑12 | Network science + spectral graph theory over **declaration-level** dependency graphs of Lean 4 / Mathlib (is Mathlib small-world? scale-free?) | ~16 KB Lean extractor + Python/NetworkX spectral package (Laplacian, Fiedler, recursive bisection), 7 test files; the extracted dataset itself is gitignored, not published | Mechanical: walk Lean `ConstantInfo`, `getUsedConstants` over type+body → one **undirected** `depends_on` edge; direction and type-vs-body distinction discarded; no proof steps; correctness inherited from Lean's kernel | Findings post (2026‑03‑29): 323,489 declarations, 7.5M edges, spectral split isolates tactic infrastructure. Roadmap: Go API, Memgraph, MCP. 3 stars; no code pushed since 2026‑03‑23 | Different unit of meaning: our edges are **per proof step**, directed, and each remembers the step that created it (`T6#conclude`); we **re-verify proofs ourselves** before emitting edges (47,588/47,588 set.mm in 39 s); we also carry an informal track for unformalized mathematics. Their spectral analytics is something we do not do. |
| **[proofgraph](https://ctan.org/pkg/proofgraph)** (CTAN LaTeX package) + **[result-graph](https://github.com/PierreSenellart/result-graph)**, P. Senellart — CTAN 2026‑06‑04 / repo 2026‑07‑27 | Auto-draw the dependency graph between the results of **one LaTeX article** (and, in the Lean port, of one Lean project) | A LaTeX package (LPPL 1.3c, v1.1.0) emitting Graphviz; a small Lean sibling | Inferred from `\ref`/`\cref` cross-references inside proofs (or per-declaration in Lean); result-level | Maintained; useful for papers | Corpus-scale vs article-scale; step-level vs result-level; our edges are verified and queryable (`uses`, `why`) rather than a rendered figure |
| **[proofgraph-phase1](https://github.com/banna652/proofgraph-phase1)** ("ProofGraph V0", banna652) — 2026‑01‑25 | Tamper-evident **audit log for router/network events** (WAN loss, failover) via SHA-256 hash chaining | ~17 KB Python: FastAPI ingest, RutOS/syslog event sources, chain verifier script | One record per network event; the only link is `prev_hash` to the previous record — a linear chain, **no graph structure at all** | Spec self-declared frozen; dormant since 2026‑02‑20; 0 stars | Name-only collision: "proof" there means cryptographic integrity, not mathematics |
| **ProofWeb** (Radboud University, 2006–07; [manual](https://www.cs.ru.nl/~freek/pubs/webded1.pdf)) | Web IDE for **teaching logic with Coq** — server-side provers, Gentzen/Fitch proof rendering, teacher dashboards | Historic; no maintained code found | Students typed Coq proofs in a browser | **Dead**: servers unreachable, last working snapshot ~2020, courses frozen 2019–20 | Unrelated artefact that once carried our name; we note the history and moved on. (Nothing alive collides with the name today.) |
| **[Prove2Me](https://arxiv.org/abs/2608.28433)** + the [FLT corpus](https://github.com/anthropics/fermats-last-theorem) — Sep 2026 | Coordinate proving agents around a DAG of theorem statements; one statement file and one proof file per theorem, imports = citations by discipline | 29,511 theorems, 1,450 definition modules, 13M lines of Lean; kernel + comparator + nanoda checked, 3 axioms, 0 sorry | Agents propose statements and claim them; the DAG is *construction-time coordination*. A text-only generator computes citations and depth for the docs site | Live, published, the largest machine-written proof in existence. Its own paper lists "how to extract human-legible insight from machine-generated proofs" as **open** | ProofWeb imports the same files (no toolchain) and reproduces six of their published figures exactly, then adds what construction-time coordination has no reason to keep: **276,403 step-level edges** addressed to proof lines, a reverse `uses` index, and an audit that grades its own confidence. Their DAG is statement-level, authenticated, and not exported |
| **[TheoremGraph](https://arxiv.org/abs/2606.25363)** / theoremsearch.com — Jun 2026 | Join formal (Lean) and informal (arXiv) mathematics into one searchable graph | 388,105 formal declaration nodes, 11.3M typed edges across 25 Lean projects; 11.7M arXiv theorem environments; site + API + MCP | Mechanical extraction (declaration-level) + statistical formal↔informal alignment (~48k confident matches) | Live, published, the most ambitious neighbour | Declaration-level vs our step-level; their informal side is scraped-and-aligned, ours is authored-and-reviewed; we re-verify at extraction |
| **[Lean Atlas](https://github.com/NyxFoundation/lean-atlas)** — Mar 2026 | Navigable dependency graphs for Lean with 8-way edge typing (dependency in the *type* vs in the *value*) and pruning | Graph tooling + paper | Mechanical, declaration-level | Active research tool | Their edge typing stops exactly one level above proof steps; ours names the step |
| **[LeanDojo](https://leandojo.org/)** — 2023 | Trace all of mathlib at **tactic level** for machine learning | 122,517 theorems, 259,580 tactics, premises annotated per tactic with positions; shipped as an ML corpus | Mechanical tracing of kernel-checked proofs | The standard ML substrate; our Lean plan is a *converter* for its data, not re-extraction | They ship a training dump; we serve queries over a graph (`uses` = reverse step-level lookup, which nothing serves) and cover Metamath + informal mathematics |
| **[leanblueprint](https://github.com/PatrickMassot/leanblueprint)** — used by PFR, FLT | Hand-declared `\uses{}` dependency graphs as **formalization project dashboards** | LaTeX/Lean plugin | Humans declare edges at statement level | The dependency graph working mathematicians actually use daily | Hand-declared edges are precisely what our format forbids — ours are derived from steps and machine-checked for bookkeeping honesty |
| **[Metamath Proof Explorer](https://us.metamath.org/mpeuni/mmset.html)** — 1990s | The original: every theorem page shows each proof step hyperlinked to its justification, plus reverse lists | set.mm: 47,588 machine-checked proofs (CC0) | Proofs are literal step sequences; the site renders them per theorem | Alive for ~25 years; our formal track's corpus | We are downstream and say so: we add an independent re-verifier, a portable graph artefact (JSON), corpus-wide reverse step queries, stable step ids, and one schema shared with informal mathematics |
| **[Stacks Project](https://stacks.math.columbia.edu/)** — 2008– | Tag-level dependency graph over human-written algebraic geometry | 21,446 permanently-tagged results with transitive closures both ways | Humans write LaTeX; the system computes result-level dependencies | The model informal-mathematics reference | Statement-level vs our step-level; its tag-permanence discipline is exactly what we copied into immutable step ids |
| **The other ~14 GitHub repos named `proofgraph`** (2017–2026) | Crypto/TEE reasoning attestation, security-EDR data, compliance evidence graphs, coding-agent hooks, scratch projects | Mostly single-day, 0-star, undescribed | — | Noise; earliest name use is 2017 | Name-only. Their density is why this project is now called ProofWeb |

Deeper technical comparisons live in [docs/PRIOR-ART.md](docs/PRIOR-ART.md),
which also states plainly which parts of this space were already occupied
before this project existed — and which narrow slice (step-level provenance
with verified extraction, reverse step queries, stable sub-proof identity, an
informal track under measurement) it is actually claiming.

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

Formal track: two corpora import and audit cleanly. Metamath nodes are
`verified` in the strictest sense available — this repository's own verifier
replayed each proof from the axioms before emitting an edge. Lean/Prove2Me nodes
are `verified` on somebody else's kernel check, which the tools label
`derivation: imports` and never present as our own; `--trust none` refuses the
inheritance entirely. Rocq extraction is a specification, not code.

One maintainer, not a mathematician by training. That is the entire state of
the project.

## Explainer videos

[ProofWeb-VideoExplainers](https://github.com/SanTanBan/ProofWeb-VideoExplainers)
turns one result of a formal corpus into a narrated Manim explainer whose
closing trust card is computed from this repository's audit rather than typed:
which statements are formalized, what checked them, the axioms permitted,
whether the proof's import closure contains a `sorry`, whether the manuscript
was withdrawn. A lint holds the narration to the paper by file and line. The
first explainer covers result 012 of `openai/math`, the joint Dickman law.

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
