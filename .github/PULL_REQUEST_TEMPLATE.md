<!-- Thanks for contributing. Keep this short; the checklist matters more than prose. -->

## What this changes

<!-- One or two lines. -->

## Which steps are you least sure about?

<!-- Name them. A PR that flags its own weak points gets reviewed faster and
     better than one that claims to be finished. "None" is a valid answer for a
     typo fix and a suspicious one for a new proof. -->

## Checklist

- [ ] `cd tools && python -m proofweb validate --strict` passes
- [ ] `cd tools && python -m pytest` passes
- [ ] I read each new node back with `python -m proofweb why <id>` and the
      dependencies it printed are the ones I intended
- [ ] Every step cites what it uses, and nothing it does not use
- [ ] `provenance.source` says where the mathematics comes from
- [ ] If a language model drafted any part of this, `provenance.assisted_by`
      names it **and I have personally checked every step**
- [ ] No node is marked `verified` without a `formalization` link
