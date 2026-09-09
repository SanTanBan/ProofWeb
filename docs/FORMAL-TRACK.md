# The formal track: mechanistic extraction from proof assistants

This document is the design for the half of ProofWeb where the edges are
**facts, not judgements**: graphs extracted mechanically — no AI, no human
citation-typing — from machine-checked proofs. It exists because of a specific
piece of feedback that reshaped the project:

> Build a mechanistic codebase that develops the ProofWeb by extracting
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
and a populated ProofWeb is the right substrate for it.

## 2. What is built and working today: the Metamath extractor

[`tools/proofweb/metamath.py`](../tools/proofweb/metamath.py) — roughly 600
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
per the Metamath spec — and emits ProofWeb nodes whose steps are the logical
(`|-`) replay steps, each carrying machine-derived `by` lists: the earlier
steps it consumed, in mandatory-hypothesis order, plus the assertion it
applied. Grammar steps (wff assembly) become vocabulary edges rather than
proof edges, so the graph is about mathematics rather than parsing. Nodes
whose proofs verify are marked `verified`; incomplete proofs stay `draft` with
the reason recorded.

```bash
# extract everything up to and including set.mm's `id`, with the viewer
python -m proofweb extract corpora/set.mm --stop-at id \
    -o examples/setmm-through-id.json --html build/setmm.html

# what does mp2 rest on, and at which steps?
python -m proofweb why mp2 --json examples/setmm-through-id.json

# every proof step in the extract that invokes ax-mp — the reverse
# step-level lookup that no existing search engine serves
python -m proofweb uses ax-mp --json examples/setmm-through-id.json
```

**Evidence, from this repository's own runs.** The full set.mm — **all 47,588
proofs, ~51 MB, 873k lines** — parses and verifies in **39.1 s wall clock with
zero failures** (Python 3.12, single core, `keep_steps=False`). That count and
verdict agree exactly with the canonical `mmverify.py` run over the same
develop-branch snapshot (47,588 verified, "No errors were found"). The
extracted proof of set.mm's `id` matches the Metamath Proof Explorer page for
it step for step. And one more result worth recording: the first hand-written
proof in the test fixture — written carefully, on paper, by the person
building the verifier — **was wrong** (a misinstantiated `ax-1`), and the
verifier refused it. The error rate of careful humans is the project's
founding observation, and it reproduced itself at the first opportunity.

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

## 3a. Lean, part one: importing a Prove2Me corpus from text (built)

In September 2026 the situation this document described changed. Anthropic
released [a 13-million-line Lean proof of Fermat's Last Theorem](https://github.com/anthropics/fermats-last-theorem)
(Apache-2.0), written by Claude agents in eleven days on the **Prove2Me**
platform, kernel-checked and independently replayed by `comparator` and
`nanoda`. Days later, OpenAI published [Lean certificates for Navier–Stokes and
Euler blowup](https://github.com/openai/NavierStokesAndEuler) and Buckmaster and
Alpöge published [theirs](https://github.com/tristanbuckmaster/fluid_lean).

Three machine-written formal corpora in one month, the largest of them five
times the size of Mathlib and read end to end by nobody. That is the demand this
project was betting on — [RISKS.md](RISKS.md) §15 called it "a bet on the
auditing market" — arriving earlier than expected.

### Why this corpus can be imported without a toolchain

Prove2Me (Peng et al., Columbia) coordinates proving agents around a DAG of
theorem statements, and lays the result out so the DAG survives in the
filesystem:

| Path | Contents |
|---|---|
| `Theorems/Thm_<stem>.lean` | one immutable statement; its body is `:= by p2m_exact_reverting @_root_.P2MW.S_<stem>.solution` |
| `P2M/Sol/S_<stem>.lean` | the proof, importing **exactly** the theorems it cites as `Theorems.Thm_<X>` |
| `Definitions/Def_<stem>.lean` | shared vocabulary |

Two consequences. The `p2m_exact_reverting` tail means the statement file fails
to build unless the solution proves exactly the reverted statement, so
**statement/proof identity is kernel-enforced**. And because a proof's imports
are its citations by construction, the dependency graph is recoverable by
reading text — no `lake`, no Mathlib cache, no 67 GB build.

So the importer is pure Python, in the same posture as the Metamath verifier:
[`tools/proofweb/leantext.py`](../tools/proofweb/leantext.py) (Lean-aware text
utilities) and [`tools/proofweb/leanp2m.py`](../tools/proofweb/leanp2m.py) (the
corpus reader).

```bash
git clone --filter=blob:none --sparse --depth 1 \
    -c core.longpaths=true -c core.autocrlf=false \
    https://github.com/anthropics/fermats-last-theorem corpora/fermats-last-theorem
git -C corpora/fermats-last-theorem sparse-checkout set \
    Theorems P2M Definitions verification tools/docs-site/gen

cd tools
python -m proofweb import-lean ../corpora/fermats-last-theorem \
    --root fermat_last_theorem -o ../build/flt.json
python -m proofweb audit --json ../build/flt.json --root fermat_last_theorem \
    --proof-path ../corpora/fermats-last-theorem/PROOF-PATH.md \
    --compare flt --report ../build/flt-audit.md
```

`--filter=blob:none --sparse` matters: the repository ships a 390 MB pre-rendered
HTML site that a plain clone would download. `core.autocrlf=false` matters too —
the global Windows default would rewrite every line ending and change the file
hashes recorded in provenance.

### What the import produced, and what it proves

The audit recomputes figures the corpus publishes about itself in its own
`html/about.html`, generated by *their* text-only tool. Reproducing them to the
unit means two independently written parsers agree about 13 million lines:

| Quantity | ProofWeb | Upstream | |
|---|---:|---:|---|
| theorem nodes | 29,511 | 29,511 | match |
| definition modules | 1,450 | 1,450 | match |
| theorem → theorem citations | 106,853 | 106,853 | match |
| reachable from `fermat_last_theorem` | 29,489 | 29,489 | match |
| theorems outside that closure | 22 | 22 | match |
| of those, cited by nobody | 19 | 19 | match |

Plus what only the step-level view can say: **273,252 step-level proof edges**,
each addressed to a line of a named proof file, and 129,505 theorem → definition
citations that upstream's count does not include. Import takes about twelve
minutes single-threaded; the audit under a minute.

**Two figures do not match, and they are the more instructive half.**

*Citations never named in the proof script.* Upstream reports 2,890. ProofWeb's
default `--hit-mode strict` reports 3,644, because its identifier pattern is
Unicode-aware and theirs is ASCII-only, so the two disagree wherever a name
touches `ℕ`, `₀` and the like. `--hit-mode anthropic` uses their exact pattern
and lands at 3,142 — closer, and still 252 above. The residue is a difference in
which lines count as proof script (this importer excludes `attribute`, `open`
and other non-proof lines, which upstream's body region does not). Neither
number is wrong; they measure slightly different things, which is why both modes
exist and why the audit prints DIFFERS rather than quietly picking one.

*Landmark names in PROOF-PATH.md.* Upstream reports 49; the same two regexes
over the same file give 52 here. The extra three are bare namespace names used
as prose (`ModularCurve`, `AlgebraicGeometry`) and a literal `X.y` placeholder,
which their generator evidently filters. This was left as a recorded difference
rather than tuned away: a match obtained by adjusting a filter until the number
agrees would establish nothing, whereas an explained difference of three
establishes that both tools are reading the same file.

The general rule this follows: **an audit that can only report agreement is not
an audit.** Every count carries `match` or `DIFFERS by ±n`, and the two that
differ are documented here rather than in a footnote.

### What an imported node claims

Every node carries the basis of its own status, because at this scale nobody can
re-derive it by reading:

```yaml
status: verified                       # the statement/solution tail + no sorry
provenance:
  derivation: imports                  # imports | kernel-replay | manual
  step_attribution: textual            # textual | kernel | human | none
  checked_by: "lean-kernel (upstream build; comparator; nanoda)
               — not replayed by proofweb"
  source: "fermats-last-theorem@aa2d8b34692b (Apache-2.0)"
  lean: {thm: ..., sol: ..., sha256_thm: ..., unused_imports: [...], hit_forms: {...}}
```

Three claims of different strength, kept apart on purpose:

1. **The kernel check is real, and it is not ours.** The upstream build,
   `comparator` and `nanoda` all accepted this proof. ProofWeb replayed none of
   it — `derivation: imports`, never `kernel-replay` — and `proofweb stats`
   prints "0 replayed here" next to the verified count so the distinction cannot
   be missed at a glance. `--trust none` marks everything `draft` for anyone who
   declines to inherit somebody else's check.
2. **Citation edges are exact at statement level, by convention.** Lean imports
   are transitive, so a proof *could* use something it does not directly import;
   the Prove2Me discipline says it does not, and the audit's "never named" column
   is the measure of how far the text alone corroborates that.
3. **Line attribution is textual, and graded.** Of 103,214 attributed
   occurrences in the FLT corpus, **81.5% are `qualified`** (the occurrence
   carried the theorem's own namespace — near-certain), 14.9% `bare-open`
   (unqualified, but the namespace is open here), 3.5% `dot` (field notation,
   where the prefix is a term and the match cannot be verified from text at all),
   and 0.1% `bare-unopened`. Only a term-level extraction can settle the last
   two categories — which is what §3b is for.

A `claim` on an imported step is **a line of a proof script, not an asserted
proposition**. The goal state at that line is unknowable without running Lean,
and pretending otherwise would be exactly the overclaim this project exists to
avoid.

### What it is for

`uses` becomes a reverse index over 13 million lines — every proof step in the
corpus that invokes a given theorem, with the line that invokes it:

```bash
python -m proofweb uses ModularForm_S2_Gamma0_2_eq_zero --json ../build/flt.json
python -m proofweb why FLT_fermatLastTheorem --json ../build/flt.json --limit 20
python -m proofweb render html --json ../build/flt.json \
    --focus FreyPackage_of_counterexample --radius 2 -o ../build/flt-focus.html
```

This is the gap [PRIOR-ART.md](PRIOR-ART.md) §5 identified — search engines index
what a declaration *says*, never where it is *used* — now answerable over a
corpus that did not exist when that page was written.

### Prove2Me and ProofWeb are not competitors

Prove2Me's DAG is **construction-time coordination**: it exists so agents can
decide what to prove next, it is statement-level, its API needs authentication,
and it publishes no bulk export. ProofWeb reads the artefact those agents left
behind, from files anyone can clone, and asks the questions a reader has
afterwards. The [Prove2Me paper](https://arxiv.org/abs/2608.28433) lists among
its open problems: *"How to extract human-legible insight from machine-generated
proofs remains an open problem."* This is one small, checkable answer to that.

Worth stating plainly, in the same spirit as the set.mm note: **"no AI" describes
this pipeline, not this corpus.** Every proof in it was written by Claude agents.
The kernel does not care who wrote a proof, and neither does the importer — but
a project that advertises a mechanical pipeline should say exactly where that
boundary falls.

## 3b. Lean, part two: term-level extraction (designed; needs a toolchain)

A Lean proof term is an `Expr` whose constant subterms name every lemma used,
at a specific structural position. The mechanistic extractor is therefore a
metaprogram, not a parser: iterate `Environment.constants`, and for each
`thmInfo`/`defnInfo` walk its `value` with an `Expr` traversal collecting used
constants — `Lean.Util.FoldConsts` (`getUsedConstants`) does the collection
today, though it discards positions, so a positional variant is a small custom
fold emitting `SubExpr.Pos` paths. One boundary to know before designing
around it: those positions are *structural* (paths within the term). Kernel
`Expr`s carry no source ranges — sub-declaration *source-text* positions
require `InfoTree`s, which only exist while re-running the elaborator over the
source. That is precisely the line between term-level and tactic-level
extraction. No AI anywhere.

Two granularities exist and they are genuinely different:

- **Term-level** (what the kernel checked): exact, complete, but
  post-elaboration — `simp` becomes a large generated term, and the structure
  reflects the elaborator's output more than the human's argument.
- **Tactic-level** (what the human wrote): `intro`, `rw [add_comm]`,
  `exact mul_left_cancel …` — this is the layer matching ProofWeb's notion
  of a "step". **[LeanDojo](https://leandojo.org/leandojo.html) already
  extracts this**, with premises annotated per tactic and goal states before
  and after, for all of mathlib.

Consequence, stated plainly so this project does not waste a volunteer's year:
**the Lean work is integration, not invention.** A `leandojo-to-proofweb`
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
valuable contribution an outside collaborator could make). One fact narrows it
considerably, verified against the interfaces rather than assumed:
**`rocq-lsp`'s machine API (Petanque) does not expose kernel proof terms.**
Its `premises` call lists what is *available* in the environment, not what a
proof *used*; `goals` returns reified strings; `ast` returns surface syntax.
The proof terms exist — `constant_body` in `kernel/declarations.mli`, with
`Qed`-opaque terms lazily loadable from the `.vo` opaque segment
(`kernel/opaqueproof.mli`) — but reaching them means OCaml, not JSON-RPC.

So the honest architecture is two components:

1. **An OCaml plugin against the Rocq API** (`Global.env`, `constant_body`,
   forcing the opaque table): walk each constant's term for the constants it
   uses — the exact analogue of Lean's `getUsedConstants` — and dump
   whole-proof dependency JSON. This alone, run over the Rocq stdlib, would be
   the first artefact of its kind.
2. **Sentence attribution via `rocq-lsp`/Petanque** on top: replay the `.v`
   source, diff the goal state across sentences, and join against the plugin's
   term data to attribute premises to proof steps. This is the LeanDojo
   analogue and is genuinely harder; it is version two, not version one.

Emit the same extracted-JSON this repository already loads, and the viewers
and queries come for free.

## 5. After construction: how a ProofWeb helps attack open problems

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

Every edge in the graph carries a `derivation` saying how it was obtained, and
they are not equal:

| `derivation` | Meaning | Where |
|---|---|---|
| `kernel-replay` | a checker in this repository replayed the proof before emitting the edge | Metamath (§2) |
| `imports` | read off a corpus whose convention makes imports exact, kernel-checked elsewhere | Lean/Prove2Me (§3a) |
| `manual` | a human wrote the citation and other humans reviewed it | the YAML pilot |

| | Formal track | Informal track |
|---|---|---|
| Edge provenance | kernel-replayed (Metamath) or import-derived and checked upstream (Lean) | typed by a human, reviewed by two more |
| Correctness criterion | the proof itself (RISKS §1 answered) | inter-annotator agreement (RISKS §1 stands) |
| Populates | `extract` → JSON corpora | `graph/` YAML modules |
| Its open question | can the extraction reach Lean/Rocq scale and stay honest? | is step-level attribution a well-defined human judgement at all? |

Same schema, same queries, same viewer — `why`, `uses`, `T6#conclude`-style
stable addresses — over both. The informal track is the measurement study
([ROADMAP.md](ROADMAP.md) Phase 3); the formal track is the infrastructure
build. Each is the other's control group, which is the most honest structural
relationship the two could have.
