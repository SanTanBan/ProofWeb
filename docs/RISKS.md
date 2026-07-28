# Why this project will probably fail

This document is kept in the repository on purpose. A project asking strangers
for unpaid work owes them an honest account of the odds, and a founder who
cannot write down the failure modes has not understood the problem.

Nothing here is hypothetical hand-wringing. Several of these failures have
**already happened at small scale in this repository**, and where they have, the
evidence is cited.

---

## 1. The graph already exists, and the incumbents are enormous

**Severity: fatal. Probability: near-certain — this is already true.**

[PRIOR-ART.md](PRIOR-ART.md) documents it. Metamath has published an
axiom→theorem→proof graph with reverse edges and full axiom traceability since
the 1990s. The Stacks Project does it for human-written LaTeX at 21,446 tags with
precomputed transitive closure in both directions. LeanDojo has extracted
step-level premise attribution from all of mathlib since 2023 — 259,580 tactics,
167,779 premise references. mathlib4 has 283,487 theorems and 772 contributors.

A newcomer's instinct is "but none of them does *exactly* this." That instinct is
how projects die: the residual is real but small, and small residuals do not
attract the contributors needed to close them.

**Mitigation:** none available for the general claim. The only response is to
stop making it — which is why the README leads with prior art instead of burying
it. What remains defensible is narrow, and section 11 argues even that is hard.

## 2. A hand-authored graph is a lossy duplicate of something a compiler computes exactly

**Severity: fatal. Probability: near-certain.**

In Lean and Rocq, the proof term *is* the dependency structure. Every `const`
subterm names a lemma at a specific structural position. `#print axioms` and
`Print Assumptions` already walk it. The information is **unexposed and
unindexed, not undiscovered** — anyone claiming to recover hidden structure is
overselling.

So a hand-written YAML graph is a second copy of a fact the kernel already knows,
produced by a less reliable process, which drifts the moment either side is
edited. Asked "why should I trust your edge over the compiler's?", the honest
answer is: you should not.

**Mitigation, partial and real:** the only defensible territory is mathematics
that has *no* proof term — informal proofs not yet formalized. That is a genuine
gap (Stacks and `leanblueprint` stop at *statement* granularity), but it is much
smaller than "a knowledge graph of mathematics", and it inherits every problem
below.

## 3. The bookkeeping is wrong far more often than it looks — and the validator cannot tell

**Severity: severe. Probability: already happened.**

This is the most important entry, because it is measured rather than argued.

The pilot is eight proofs from first-year algebra, written carefully, and
`proofgraph validate --strict` reported **"ok — 14 nodes, 52 proof edges, no
findings."** An adversarial review of the same files then found:

- **5 blocking defects** — three steps that did not follow from what they cited
  (two asserted the *converse* of associativity without citing symmetry of
  equality; one applied the inverse axiom to a product without citing closure),
  one step that nothing cited although two later steps needed it, and one
  module-wide convention that was not a predicate on the mathematics at all.
- **8 further should-fix defects**, including four `formalization:` links
  pointing at properties the module never uses — L1 linked reflexivity while all
  fifteen of its uses are symmetry or transitivity.
- Two prose passages asserting something **false** about the axiom system.

Correcting them took the module from **52 to 63 proof edges**. Twenty percent of
the true dependency structure was missing, in the easiest mathematics that exists,
in a repository whose entire purpose is getting this right.

Now extrapolate. The interesting structure appears at 10⁴–10⁵ nodes. At the
observed defect rate, an unreviewed graph at that scale is not a slightly noisy
reference — it is a confident-looking artefact that is wrong about a fifth of its
own claims, which is worse than no graph, because people would rely on it.

**Mitigation:** two-reviewer sign-off before `reviewed`, which is policy in
[CONTRIBUTING.md](../CONTRIBUTING.md). Note what this concedes: **the binding
constraint is expert attention, and it does not scale with funding or tooling.**

## 4. Verification cost equals authoring cost, so automation saves nothing

**Severity: severe. Probability: near-certain.**

The obvious response to section 3 is "use an LLM to draft nodes." But an
LLM-proposed dependency edge is cheap to generate and expensive to check. Unlike
code, which has tests, or Lean, which has a kernel, an informal proof graph has
**no cheap oracle**. The characteristic error is not gibberish — it is a citation
that is plausible, names a real theorem, and does not justify the step. Detecting
one requires doing the mathematics.

If checking a node costs roughly what writing it costs, generation throughput is
irrelevant; the review queue is the whole system. Generating faster than
reviewing converts the graph from a checked artefact into an unchecked one, which
destroys the only property it has.

**Mitigation:** the ban on bulk generation, and mandatory `assisted_by`
disclosure. Both are policy, both are weakly enforced by CI, and both will be
under pressure the moment anyone wants the node count to grow.

## 5. Conventions that are not predicates on the mathematics silently void the edges they govern

**Severity: severe. Probability: already happened.**

The pilot's original closure convention said: cite the closure axiom only where a
step's *content* is that some element lies in G. That sounds reasonable and is
not a rule at all — which steps have membership as their content is the author's
choice of what to write down, so two careful contributors can apply it to the
same proof and disagree with no fact settling it.

The measured consequence: closure was load-bearing but uncited at seven steps,
while the axiom's only two edges came from optional bookkeeping lines, one of
which nothing referenced. **The axiom had edges, and they pointed at the wrong
places** — the most dangerous possible state, because the graph looked complete.

Every convention carries this risk, and a growing graph accumulates conventions.
See [SPEC.md](SPEC.md#the-closure-convention) for the corrected rule and the test
a convention must pass.

## 6. Stable identity for sub-proof nodes is unsolved, and it is load-bearing

**Severity: severe. Probability: likely.**

The whole pitch is that an edge points at *step 12 of T6*. What is that node
after someone reorders the proof, splits a step in two, or replaces the proof
entirely? Declaration-level tools get identity free from fully-qualified names.
Step-level tools have no equivalent, and nothing in the literature solves it.

This is the project's most defensible technical claim and simultaneously its
largest unmitigated risk: a design problem, not an engineering-effort problem,
which a small project might crack or might simply be stuck on indefinitely. If it
is not solved, every cross-proof edge rots on the first refactor and the graph
degrades into exactly the hand-maintained index it was built to replace.

**Mitigation:** none yet. It is Phase 4 of [ROADMAP.md](ROADMAP.md) and should be
attacked before the graph is large enough for the answer to matter.

## 7. <a id="overclaiming"></a>Overclaiming destroys the credibility the project runs on

**Severity: fatal. Probability: likely without deliberate restraint.**

The project has 14 nodes of elementary group theory and **zero** verified nodes.
Putting "Millennium Problems" or "prove unproven Ramanujan notebook entries" in a
README, a grant application, or a pitch is the single fastest way to be dismissed
by every mathematician and every funder who matters — and dismissal in this field
is silent. Nobody writes to explain why they stopped reading.

Stated flatly: **a proof graph records the provenance of proofs that already
exist. It cannot supply a proof that does not.** There is no mechanism by which
step-level dependency edges bear on any Millennium Problem. Proving Lost Notebook
entries needs q-series and modular-forms expertise that a graph does not supply.
And the labour of real formalization does not compress — Liquid Tensor took ~18
months and ~25 people; the Fermat's Last Theorem project is funded and scheduled
into 2029.

This failure mode is unusual in being **entirely self-inflicted and entirely
avoidable.** One sentence converts a credible infrastructure project into a crank
signal. The project's own maintainer is the only person who can prevent it.

**Mitigation:** those targets are explicitly out of scope in
[ROADMAP.md](ROADMAP.md), and this paragraph exists so the temptation is
pre-committed against in public.

## 8. Scope diffusion and crank adjacency

**Severity: severe. Probability: likely.**

The repository must convince two audiences — working mathematicians and
prospective contributors — and both decide in about thirty seconds. A repository
that is simultaneously formal-methods infrastructure, a physics research
programme, a collaboration hub, and a grant vehicle reads as none of them.

Hosting a personal speculation about gravity next to a machine-validated proof
artefact is the specific hazard. The mitigation adopted here is to make the
boundary visible and to hold the speculation to a *higher* evidential standard
than the mathematics: [OPEN-PROBLEMS.md](OPEN-PROBLEMS.md) requires an
**Obstruction section stating what already refutes the idea, placed before the
problem**, and OP-1 duly opens by conceding that the shell theorem and the
corollary of Birkhoff's theorem answer the naive form in the negative.

That is a real mitigation, not a cosmetic one, but it is not free: the page still
costs a reader's attention, and some fraction will not read far enough to see the
rigour.

## 9. <a id="the-grant-treadmill"></a>The grant treadmill

**Severity: moderate. Probability: plausible.**

Money is not the binding constraint — section 3 is. Winning LLM credits buys
generation capacity for a pipeline whose bottleneck is review, so the likely
result is a larger unreviewed graph plus a reporting obligation. Grants also
create output pressure precisely where the project most needs the discipline to
go slowly, and when the credits end the node count is higher and the review debt
is worse.

**Mitigation:** [FUNDING.md](FUNDING.md) says to apply when there is something a
reviewer would want to read, not in order to create it, and to budget for paying
people to *check* nodes rather than for tokens.

## 10. The demo trap

**Severity: moderate. Probability: near-certain.**

The pilot was written by people who knew the format, in a domain chosen because
it is easy. It is therefore unrepresentative in at least four ways: it is pure
equational reasoning; it has no induction, no case analysis, and no proof by
contradiction (the `assumption` token exists and has never been used in anger);
it is one module, so `imports` is exercised only by tests; and every proof was
co-designed with the tool that renders it.

An elegant small demo systematically misleads its author about feasibility.
Phase 2 of [ROADMAP.md](ROADMAP.md) exists to break it deliberately.

## 11. Contributor supply, not tooling, is the binding constraint

**Severity: fatal. Probability: likely.**

The pool of people who can both do mathematics and write structured data files is
small, and mathlib is its Schelling point. A new project competes with a
772-contributor incumbent for the same scarce hours while offering less
immediate value.

Worse, the founder is not a mathematician by training. That is not
disqualifying — but it raises the credibility cost of every claim, and
mathematicians tend to ignore outsider projects rather than critique them, so the
feedback that would let the project correct is exactly the feedback it will not
receive.

**Mitigation:** ask for something small, specific, and technical rather than for
belief. [CALL-FOR-COLLABORATION.md](CALL-FOR-COLLABORATION.md) leads with "find a
step that does not follow" for this reason. Partial at best.

## 12. Obsolescence mid-build

**Severity: severe. Probability: plausible.**

Frontier systems are moving into this territory now. DeepMind's Aletheia
autonomously resolved four open problems from the Erdős database
([arXiv:2602.10177](https://arxiv.org/abs/2602.10177)); Gemini Deep Think reports
up to 90% on IMO-ProofBench Advanced. If models can retrieve and chain lemmas
end-to-end, the residual value of a hand-built retrieval graph shrinks while it
is being built.

The counter-argument is the one place this project's thesis strengthens as models
improve: **the more mathematics machines produce, the more valuable
step-level provenance becomes**, because provenance is how a claim is audited. But
that is a bet on the auditing market, not on the retrieval market, and it should
be stated as a bet.

---

## Kill criteria

Observable conditions under which this should be abandoned or radically
rescoped. Written now, while it is cheap to be honest.

1. **Six months from first public release, no external contributor has merged a
   node or filed a substantive correctness issue.** Contributor supply is the
   binding constraint; failing to attract one person is the answer.
2. **The Phase 3 ground-truth experiment shows systematic divergence.** If
   hand-authored step-level provenance disagrees materially with kernel-verified
   premise data on the ~17 Lean-formalized Erdős solutions, the central claim is
   false and no amount of tooling repairs it.
3. **A second adversarial review of reviewed nodes finds blocking defects at a
   similar rate to the first.** Section 3 is survivable if review catches
   defects; it is fatal if review does not.
4. **Stable sub-proof identity has no credible design after a serious attempt.**
   Without it, cross-proof edges rot on refactor and the artefact degrades to a
   hand-maintained index.
5. **The node count grows faster than the reviewed count for two consecutive
   quarters.** That is the graph turning into an unchecked artefact, measurable
   directly from `proofgraph stats`.
6. **A funder or a maintainer of Metamath, mathlib or the Stacks Project reads
   the prior-art page and says the residual gap is not real.** They are better
   placed to judge than the maintainer is.

## The honest summary

The strongest version of this project is **not** "a knowledge graph of
mathematics." It is:

> A format and validator for recording *step-level provenance in informal
> mathematics*, with a solution to stable sub-proof identity, ground-truthed
> against kernel-verified premise data.

That is narrow, unglamorous, achievable by a small team, and genuinely
unoccupied. It is also much less exciting than the idea that brought anyone here,
and the gap between those two things is where projects like this usually die.

If you are deciding whether to contribute: the mathematics in this repository is
correct, the tooling is real, the prior-art page is not hiding anything, and the
odds are still against it. That is the accurate picture.
