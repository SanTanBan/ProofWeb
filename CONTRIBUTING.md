# Contributing

Thank you for looking. This document is longer than it needs to be for a project
this small, because the failure mode of a mathematics knowledge graph is not too
few contributions — it is contributions nobody can trust, arriving faster than
anyone can check them.

Read [docs/SPEC.md](docs/SPEC.md) for what a node file means. This document is
about the social contract.

---

## The one rule

**Every step of every proof cites what justifies it, and nothing else.**

Not what feels relevant. Not every axiom in the neighbourhood. What that step
actually uses. If you cannot point at where a citation is used in the claim,
delete it.

This is the rule the whole project rests on, because it is what makes the graph
an assertion rather than a decoration. A graph whose edges are approximately
right is worth less than no graph, since it invites people to rely on it.

---

## What we most want

In rough order of value:

1. **Review of existing nodes.** Unglamorous and the binding constraint. Pick a
   node, read every step, and try to find a citation that is wrong, missing, or
   spurious. Open an issue if you find one. This is worth more than new content.
2. **A `formalization:` link for a node that lacks one.** If you know the
   mathlib or Metamath name for a statement, that single line moves a node
   closer to `verified` and costs you two minutes.
3. **Bug reports against the validator.** A graph you can break is a graph
   telling you something.
4. **New nodes**, in a module that already exists.
5. **A new module** — but read *Proposing a module* below first.

## What we do not want yet

- **Original mathematics.** Not because it is unwelcome in principle, but
  because this project has no mechanism to referee it. Contribute proofs that
  are already standard and checkable against a textbook.
- **Large auto-generated dumps.** See *LLM-assisted contributions*.
- **New file formats, databases, or web frontends** before the graph is big
  enough for anyone to need them.
- **Speculative physics or claimed solutions to open problems.** There is a
  separate place for open problems ([docs/OPEN-PROBLEMS.md](docs/OPEN-PROBLEMS.md))
  and it has a specific format for a reason.

---

## Adding a node

1. Find or propose the module it belongs to under `graph/`.
2. Copy an existing node in that module. Do not start from the spec — start
   from something that already passes review.
3. Write the statement so that two mathematicians would formalise it the same
   way. If that is hard, the statement is the problem, not the format.
4. Write the proof one step at a time. For each step ask: *what exactly makes
   this true?* That answer is the `by:` list.
5. Run the checks:

```bash
cd tools && python -m proofweb validate --strict && python -m pytest
```

6. Read your own node back with `python -m proofweb why <id>` and see whether
   the dependency list it prints matches what you believe.
7. Open a pull request. Say in the description which steps you are least sure
   about — a PR that flags its own weak points gets reviewed faster and better.

### Proposing a module

Open an issue first, with:

- what is in scope and, more importantly, **what is out of scope**
- which existing modules it would `import`
- the first five nodes you intend to write

Modules are cheap to create and expensive to merge later. The `scope` field in
the manifest is what stops the graph becoming one undifferentiated blob, and it
only works if it is written before the content, not after.

---

## Review

A node reaches `reviewed` when **two people other than the author** have checked
every step. Reviewing means, for each step:

- Does the claim follow from the cited justifications *alone*?
- Is anything cited that the step does not use?
- Is anything used that the step does not cite? *(This is the one that gets
  missed, and it is the one that matters.)*
- Does the final step actually establish the stated theorem?

You do not need to be a professional mathematician to review elementary modules.
You need to be willing to be pedantic in public.

A node reaches `verified` only when a proof assistant has checked it and
`formalization:` points at the checked artefact. This is enforced in CI. It is
the only claim in the repository that does not depend on trusting a human, and
it must not be weakened.

---

## LLM-assisted contributions

**Allowed, and disclosed.** Set `provenance.assisted_by` to the model. Nodes in
this repository were drafted this way.

The rule exists because of a specific, well-understood failure: the
characteristic error of a machine-drafted proof is not gibberish, it is a
citation that is *plausible and wrong*. It reads correctly, it names a real
theorem, and it does not justify the step. Human errors have a different shape,
so reviewers must read differently depending on the origin.

Two hard limits:

- **You must have read and checked every step you submit.** "The model produced
  this and it looked right" is not a contribution; it is a request that someone
  else do the work. Undisclosed or unchecked machine output will be reverted.
- **No bulk generation.** A pull request adding fifty nodes will be closed
  unqualified, however good they look, because nobody can review it and merging
  it would convert the graph from a checked artefact into an unchecked one. If
  you want to work at that scale, open an issue and let us design the review
  pipeline first — that is a genuinely interesting problem and the project needs
  an answer to it.

---

## Style

- Prose in statements and claims, not symbol soup. `latex:` is there for the
  symbols.
- One node per file. Filenames `<id>-<kebab-slug>.yml`.
- Steps small enough that a reader can check each one without pen and paper. If
  a step needs a paragraph of justification, it is several steps.
- `note:` is for the reader's orientation and is never load-bearing. If deleting
  a note would make a step unjustified, that content belongs in `claim` or `by`.
- British or American spelling, we do not care, be consistent within a file.

---

## Licensing

By contributing you agree that:

- code under `tools/` is contributed under the **MIT License**
- graph content under `graph/` and prose under `docs/` is contributed under
  **CC BY 4.0**

Two licences because they are two different things. The tools are software; the
graph is a reference work that should be as reusable and as easy to cite as
possible, including by projects that will not want our code. If you copy
mathematics out of a source that permits it, record where in
`provenance.source`. Do not copy proof text from a source that does not.

---

## Conduct

Be precise, be direct about errors, and be kind about people. Pointing out that
step 7 does not follow is the most useful thing you can do here and is never
rude. Speculating about whether the author understands mathematics is not the
same act, and is not welcome.

Disagreements about mathematics are settled by proofs. Disagreements about
conventions are settled by writing the convention down in the module manifest
and moving on.
