# Why this project will probably fail

This document is kept in the repository on purpose. A project asking strangers
for unpaid work owes them an honest account of the odds, and a founder who cannot
write down the failure modes has not understood the problem.

It is the output of a deliberate adversarial review commissioned against this
repository from four independent directions — formal methods, open-source
ecosystem, AI economics, and product scope. Several of the findings below are
about defects that were **found in this repository and have since been fixed**;
those are cited as evidence rather than as reassurance, because the rate at which
they appeared is itself the argument.

Ranked by severity × probability × how early it bites.

---

## 1. There is no correctness criterion for an edge — not merely no oracle

**Severity: fatal. Probability: certain — this is structural.**

Every claim the project makes rests on the edges being right, and nothing in the
design can establish that, even in principle.

`validate.py` concedes in its own docstring that it does not check whether a step
follows from its justifications. And `Node.edges()` is a list comprehension over
the hand-typed `by:` field. So **"derived, not declared" is, strictly, a
relabelling**: the dependency list is still typed by a human, merely sharded
about eight times finer (63 citations across 50 steps rather than 8 per-theorem
lists). The derivation is real in that you cannot write an edge without writing a
justification — but it does not make the edge *true*.

Worse, "the right answer" is not well defined. There is no fact of the matter
about whether a given informal step "uses" transitivity of equality, only a
convention, and conventions are section 5.

**Mitigation:** none that preserves the current scope. The two honest moves are
(a) reposition the artefact as a *measurement of human provenance judgement*,
where inter-annotator agreement is at least a well-defined quantity, or (b)
derive edges from Lean elaboration — at which point LeanDojo already did it. See
the scope recommendation at the end.

## 2. The artefact already exists, built mechanically, at 100–1000× the reachable scale

**Severity: fatal. Probability: certain — already true.**

[PRIOR-ART.md](PRIOR-ART.md) has the full account. The sharpest instance:
**TheoremGraph** (arXiv:2606.25363, June 2026) shipped 388,105 Lean declaration
nodes with 11.3M typed edges across 25 projects, joined against 11.7M arXiv
theorem environments, with a public front-end, an HTTP API **and an MCP
interface** — meaning a frontier model can already call the informal dependency
graph as a tool. LeanDojo supplies 122,517 theorems and 259,580 tactics with
step-level premise annotations. Metamath has done this since the 1990s.

**Mitigation — and this one is concrete and cheap:** run the ablation and publish
it whichever way it comes out. Frontier model + web search, versus frontier model
+ ProofGraph, on step-level attribution for 30 blind steps, judged by a third
party. Two days of work. If the graph does not beat plain retrieval by a wide
margin, the project is finished and should say so.

## 3. The bookkeeping is wrong far more often than it looks — and the validator cannot tell

**Severity: severe. Probability: already happened, measured.**

This is measured rather than argued, which is why it belongs high.

The pilot is eight proofs from first-year algebra, written carefully, and
`proofgraph validate --strict` reported **"ok — 14 nodes, 52 proof edges, no
findings."** An adversarial review of the same files then found:

- **5 blocking defects** — three steps that did not follow from what they cited
  (two asserted the *converse* of associativity without citing symmetry of
  equality; one applied the inverse axiom to a product without citing closure),
  one step nothing cited although two later steps needed it, and a module
  convention that was not a predicate on the mathematics at all.
- **8 further should-fix defects**, including four `formalization:` links
  pointing at properties the module never uses — the equality node linked
  reflexivity while all fifteen of its uses are symmetry or transitivity.
- Two prose passages asserting something **false** about the axiom system.

Correcting them took the module from **52 to 63 proof edges: 17.5% of the true
dependency structure was missing**, in the easiest mathematics that exists, in a
repository whose entire purpose is getting this right.

**Mitigation:** two-reviewer sign-off, which is policy in
[CONTRIBUTING.md](../CONTRIBUTING.md). Note what it concedes: the binding
constraint is expert attention, and it does not scale with funding or tooling.

## 4. Missing edges are structurally undetectable, and error compounds along a closure

**Severity: fatal. Probability: near-certain.**

There are two error classes and they are not symmetric. A **wrong** citation is
detectable by sampling the emitted edges. A **missing** citation is invisible to
any inspection of the emitted set, because absence has no surface. The only
detector for recall failure is re-deriving the proof — which costs what authoring
cost.

So the cheap QA loop any funded project actually runs — sample 200 edges, report
94% precision — is **silent on recall by construction**. And the flagship query is
a transitive closure: per-edge error compounds multiplicatively along exactly the
path the graph is sold on. Section 3 measured recall failure at 17.5% on the
easiest possible input.

**Mitigation, partial:** propagate per-edge status through `ancestors`/`why` so
every query reports the weakest link in its closure. That is honest, and it will
show that every interesting query currently rests on `draft` edges — which is an
argument for not shipping the queries yet.

## 5. Granularity is a free parameter, so every published number measures the author's style

**Severity: fatal. Probability: certain.**

There is no canonical decomposition of an informal proof, and the pilot
demonstrates it against itself: T2 steps 3, 5 and 7 each assert *two* equations
under one step number, and T6 takes twelve steps for a result mathlib proves in
one line and Metamath in tens.

A contributor who splits conjoined claims produces different step counts, a
different edge multiset, and different values for depth and citations-per-step.
Two people's versions of the same theorem are not comparable, so cross-module
queries and every aggregate statistic measure prose style rather than
mathematics.

**Mitigation:** none that keeps both properties. Forcing canonical granularity
means one inference rule per step — which is Metamath: 25 years old, complete,
machine-checked, and read at step level by approximately nobody. Leaving it free
means the aggregates mean nothing. This is a genuine fork in the road and it has
not been resolved.

## 6. Stable sub-proof identity — the one defensible contribution — was designed out on line one

**Severity: was fatal. Status: FIXED, and it is the best evidence in this file.**

[PRIOR-ART.md](PRIOR-ART.md) §5 and the roadmap both named "stable identity for
sub-proof nodes" as the actual hard technical content and the project's most
defensible claim. Meanwhile `schema/node.schema.json` **required** steps to be
numbered exactly `1..n` with no gaps, and `check_step_numbering` hard-errored
otherwise. Inserting one step at position 3 renumbered 3 through 12, breaking
every external reference — including the README's own flagship example, "step 12
of T6".

The format named the problem in its documentation and forbade the fix in its
schema.

**Fixed**, because it was cheap at 14 nodes and would have been impossible at
1,400: steps now carry an immutable `id`, `n` is presentation-only, citations use
`s:<id>`, edges carry both, and addresses are `T6#conclude`. See
[SPEC.md](SPEC.md#4a-step-identity-n-is-not-an-address). There is a test that
inserts a step and asserts every stable address still denotes the same line.

The residual risk is not gone: nothing yet answers what an address should mean
when a step is *split in two*, or when the proof is replaced wholesale.

## 7. The quality ladder is unreachable by construction

**Severity: fatal. Probability: likely.**

`reviewed` requires two non-author experts checking every step. Reviewing a
step-level citation list is **not cheaper than authoring it** — establishing that
`by: [s:pick-inverse, L2, A1]` is both correct and *complete* requires
reconstructing the inference, which is the authoring task. So a trustworthy node
costs roughly three times an untrusted one.

Current state: 0 reviewed, 0 verified, 8 drafts, one maintainer. Contributors
need `reviewed` content to trust the artefact enough to contribute, and
`reviewed` needs contributors. No obtainable grant breaks that loop, because the
grants fund tokens and the bottleneck is expert hours.

**Mitigation, small but real:** get exactly one node to `verified` against a
checked Lean artefact before asking anyone for anything, and make
`proofgraph stats` print reviewed/total on every run so the zero is impossible to
look away from.

## 8. <a id="overclaiming"></a>Overclaiming — and the public surface currently contradicts the repository

**Severity: fatal. Probability: high, and it fires on day one.**

The repository's own documents forbid Millennium-Problem and Ramanujan framing.
**The grant application drafts sitting beside it do not.** `Applications/Pace
Fellowship.txt` names "proving complex theorems, such as those in the last of
Ramanujan's notebooks" as the ambitious goal, says development "should be as
automated as possible; for that, LLM APIs will be necessary", and claims the
graph will reveal "circularity in the references (indicating that a new axiom may
be necessary)" in Physics — a confused claim, since a proof graph is acyclic by
construction and a cycle indicates an error, not a missing axiom.

Two independent crank markers in one paragraph, addressed to exactly the audience
that dismisses silently. Nobody writes to explain why they stopped reading.

Stated flatly: **a proof graph records the provenance of proofs that already
exist; it cannot supply a proof that does not.** Liquid Tensor took ~18 months and
~25 people; the Fermat's Last Theorem project is funded into 2029. That labour
does not compress.

**Mitigation:** rewrite or withdraw the application text before it is submitted,
and audit the Encode / Pillar VC / Agency Fund derivatives line by line against
the "not on the roadmap" section of [ROADMAP.md](ROADMAP.md). This failure mode is
unusual in being entirely self-inflicted and entirely avoidable.

## 9. The validator is a Goodhart target measuring syntax

**Severity: severe. Probability: near-certain under any automation.**

The validator enforces three syntactic properties: citations resolve, no step is
unjustified, schema satisfied. All three are trivially satisfied by citing a
real, well-known lemma **that does not apply** — the characteristic failure of
both an LLM and a tired human.

Under automation it gets actively worse: a model retried against the schema
reaches ~100% CI-green, at which point "all nodes pass strict validation" carries
no information at all. Measured supporting evidence: at n=14, roughly 40% of the
cross-formalism `formalization:` links were defective — pointing at membership
lemmas rather than the equations actually used — and every one passed validation.

**Mitigation, partial:** resolve every `lean` name against a pinned mathlib
declaration index in CI. That catches dangling and malformed names. It cannot
catch statement mismatch, which is the actual defect and requires comparing
propositions across formalisms.

## 10. Verification cost equals authoring cost, so automation saves nothing

**Severity: severe. Probability: near-certain.**

An LLM-proposed edge is cheap to generate and expensive to check. Unlike code
(tests) or Lean (a kernel), an informal proof graph has **no cheap oracle**. If
checking a node costs what writing it costs, generation throughput is irrelevant
— the review queue is the whole system, and generating faster than reviewing
converts a checked artefact into an unchecked one.

**Mitigation:** the ban on bulk generation and mandatory `assisted_by`
disclosure. Both are policy, weakly enforced, and will be under pressure the
moment anyone wants the node count to grow.

## 11. The format has never met the constructs where step attribution is hard

**Severity: severe. Probability: certain.**

Measured in-repo: 14 nodes, 63 proof edges, 50 steps, six assumptions, max depth
3, and six of eight theorems are frontier nodes nothing builds on.

Consequences: the flagship `why` query is close to vacuous at this size — with
six assumptions and depth ≤ 3, "what does this rest on" answers "nearly
everything". There is no induction, no case analysis, no proof by contradiction
(the `assumption` token exists and has never been used in anger). One module, so
`imports` is exercised only by tests. And every proof was co-designed with the
tool that renders it.

**Mitigation, immediate:** invert the roadmap. Transcribe someone else's proof by
induction, unmodified, **before writing node 15**. If the format survives, the
pilot's evidence starts to be worth something; if not, that is learned in a week
rather than a year.

## 12. Bus factor of one, and the substitution pattern has already started

**Severity: severe. Probability: likely.**

The mechanism, not the platitude. Months 0–2 are self-sustaining because building
the system yields daily discrete artefacts requiring no other human — schema,
loader, validator, renderer, exporter, ~1,400 lines, all done. Months 3–12 remove
that fuel: the remaining work is transcribing textbook lemmas that add no
capability and generate no external signal.

The documented substitution is writing *about* the project instead of doing it.
This repository currently has more words in `docs/` than mathematics in `graph/`.

**Mitigation, structural only** — motivation cannot be fixed by resolve. Either an
external deadline owned by somebody else (commit publicly on Lean Zulip to a
named result by a named date, so someone notices if it does not appear), or a
co-maintainer with commit rights.

## 13. Contributor supply, not tooling, is the binding constraint

**Severity: fatal. Probability: likely.**

The pool of people who can both do mathematics and write structured data files is
small, and mathlib — 772 contributors — is its Schelling point. A new project
competes for the same scarce hours while offering less immediate value. And
outsider projects in mathematics get *ignored*, not critiqued, so the feedback
that would let the project correct is exactly the feedback it will not receive.

**Mitigation:** ask for something small, specific and technical rather than for
belief. [CALL-FOR-COLLABORATION.md](CALL-FOR-COLLABORATION.md) leads with "find a
step that does not follow" for this reason. Partial at best.

## 14. <a id="the-grant-treadmill"></a>The grant treadmill

**Severity: moderate. Probability: plausible.**

Money is not the binding constraint; sections 3 and 7 are. Credits buy generation
capacity for a pipeline whose bottleneck is review, so the likely result is a
larger unreviewed graph plus a reporting obligation. When the credits end, the
node count is higher and the review debt is worse.

**Mitigation:** [FUNDING.md](FUNDING.md) says to apply when there is something a
reviewer would want to read, and to budget for paying people to *check* nodes.

## 15. Obsolescence mid-build

**Severity: severe. Probability: plausible.**

DeepMind's Aletheia autonomously resolved four open problems from the Erdős
database ([arXiv:2602.10177](https://arxiv.org/abs/2602.10177)); Gemini Deep
Think reports up to 90% on IMO-ProofBench Advanced. TheoremGraph already exposes
an informal dependency graph as an MCP tool. If models retrieve and chain lemmas
end-to-end, a hand-built retrieval graph loses value while it is being built.

The counter-argument is the one place the thesis strengthens as models improve:
**the more mathematics machines produce, the more valuable provenance becomes**,
because provenance is how a claim is audited. That is a bet on the auditing
market rather than the retrieval market, and it should be stated as a bet.

## 16. Scope diffusion and crank adjacency

**Severity: severe. Probability: likely.**

The repository must convince working mathematicians and prospective contributors,
and both decide in about thirty seconds. A repository that is simultaneously
formal-methods infrastructure, a physics research programme, a collaboration hub
and a grant vehicle reads as none of them.

The mitigation adopted is to hold the speculation to a *higher* evidential
standard than the mathematics: [OPEN-PROBLEMS.md](OPEN-PROBLEMS.md) requires an
Obstruction section stating what already refutes the idea, **placed before the
problem**, and OP-1 duly opens by conceding that the shell theorem and the
corollary of Birkhoff's theorem answer its naive form in the negative. That is
real, not cosmetic — but it still costs a reader's attention, and some fraction
will not read far enough to see it.

---

## Kill criteria

Observable conditions under which this should be abandoned or radically
rescoped. Written now, while it is cheap to be honest.

1. **Six months after the repository is public** (clock starts when the `OWNER`
   placeholder is replaced and the first Zulip/Discourse post goes up): **zero
   nodes have reached `reviewed`** under the unmodified two-non-author rule.
   Tripwires counting as the same failure: the maintainer reviews his own node,
   an LLM pass is counted as a reviewer, or `reviewed` is redefined to mean "the
   validator passes."
2. **Eight weeks after the first public post**, no external person has opened an
   issue or PR touching a file under `graph/`. Courteous replies that lead to no
   clone do not count — terminal politeness is the documented signature of silent
   dismissal.
3. **Inter-annotator agreement fails.** Two people who are not the maintainer
   independently author step-level citations for the same 10 informal proofs and
   their edge sets agree at **Jaccard < 0.7** (≈ Cohen's κ < 0.6 on per-premise
   inclusion). If competent humans cannot agree on what an edge is, there is
   nothing to measure and no basis for the two-reviewer rule.
4. **The head-to-head ablation fails.** On 30 blind steps from outside the pilot,
   a frontier model with web search and no graph reproduces step-level
   attributions within 10 percentage points of the graph's own accuracy, judged
   by a third party. Run within 60 days; **refusing to run it is itself the
   failure condition.**
5. **The format breaks on its first non-equational proof.** Transcribing an
   unmodified textbook induction or case analysis needs more than one ad hoc
   schema field across the first three such proofs.
6. **Output outruns verification.** In any month, nodes added exceed nodes
   reaching `reviewed` by more than 5:1, or words added to `docs/` exceed words
   added to `graph/`. Both are visible from `git diff --stat` alone. *(By this
   measure the project is already failing, and that is the point of writing it
   down.)*

## The scope recommendation

The adversarial review's conclusion, recorded because it is more useful than a
comfortable one:

> **Stop building a knowledge graph. Convert the project into a single bounded,
> pre-registered measurement study with a paper as its deliverable.**

The one question here that is genuinely open, cheap to answer, and useful
whichever way it comes out:

**Do competent humans agree with each other about step-level premise attribution
in informal proofs, and how does that agreement compare to kernel-extracted
premises for the same theorems?**

Nobody has measured this. TheoremGraph, LeanDojo, `leanblueprint` and the Stacks
Project all sidestep it — they either have a kernel, so attribution is exact and
free, or they work at statement granularity, so the question never arises. It is
the one place where this format, validator and pilot are assets rather than
liabilities, and it is answerable by one person in three to four months.

Concretely: 40–60 short informal proofs from a standard source; two annotators
who are not the maintainer, paid ~$40–60/hr — about **$15–25K, which is a
defensible grant ask in a way that "API credits to populate a graph" is not**.
Pre-register the sample size, the agreement statistic and the threshold *before*
any data exists. Report inter-annotator agreement as the primary result, and
divergence against LeanDojo premises as a secondary, descriptive result
explicitly labelled as comparing **two different proofs** rather than as an error
rate. Publish the disagreement cases verbatim — they are the most interesting
output and no existing dataset contains them.

Note this supersedes the Erdős experiment as originally written in the roadmap.
That experiment was **logically invalid**: a human's informal proof and a Lean
formalization of the same theorem are *different proofs*, so divergence between
their premise sets is not an error rate and the kill criterion could never fire.
[ROADMAP.md](ROADMAP.md) has been corrected.

If agreement comes back high, there is a real finding and a basis for asking for
corpus money. If it comes back low, the question is closed in four months instead
of discovered in year three.

---

## The honest summary

The strongest version of this project is **not** "a knowledge graph of
mathematics". It is:

> A pre-registered measurement of whether step-level provenance in informal
> mathematics is a well-defined object at all — using a format with stable
> sub-proof identity, benchmarked against kernel-extracted premises.

That is narrow, unglamorous, achievable by one person, and genuinely unoccupied.
It is much less exciting than the idea that brought anyone here, and the gap
between those two things is where projects like this usually die.

If you are deciding whether to contribute: the mathematics in this repository is
correct, the tooling is real, the prior-art page hides nothing, and the odds are
still against it. That is the accurate picture.
