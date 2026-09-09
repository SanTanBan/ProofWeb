"""Audit an imported corpus, and say what the numbers do and do not establish.

Importing 29,511 machine-written theorems is easy. Knowing whether the import
*read them correctly* is the hard part, and there is exactly one honest way to
find out: recompute the figures the upstream project published about itself and
see whether they match to the unit. If they do, two independent parsers agree
about the same text. If they do not, one of them is wrong and the difference
says where to look.

Everything else here answers questions a reader of a corpus this size cannot
answer by reading: what is actually load-bearing for the goal, what is stranded,
which statements are duplicates of each other, and whether the prose route
through the proof matches the dependency graph.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from .leantext import canonical_signature, tokens
from .model import Graph, Node

_LANDMARK_TICK = re.compile(r"`([A-Za-z_][A-Za-z0-9_.'₀-ₜ]*)`")
_LANDMARK_DEF = re.compile(r"Def_([A-Za-z0-9_]+)\.lean")


@dataclass
class Section:
    title: str
    lines: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def say(self, line: str = "") -> None:
        self.lines.append(line)


@dataclass
class AuditReport:
    sections: list[Section] = field(default_factory=list)

    def section(self, title: str) -> Section:
        s = Section(title)
        self.sections.append(s)
        return s

    def to_markdown(self) -> str:
        out: list[str] = ["# Corpus audit", ""]
        for s in self.sections:
            out.append(f"## {s.title}")
            out.append("")
            out.extend(s.lines)
            out.append("")
        return "\n".join(out)

    def to_dict(self) -> dict:
        return {s.title: s.data for s in self.sections}


def _theorems(graph: Graph) -> list[Node]:
    return [n for n in graph if n.is_theorem]


def _cmp(label: str, ours: int, theirs: int | None) -> str:
    """One line comparing our count with the published one."""
    if theirs is None:
        return f"  {label:<44} {ours:>8}"
    mark = "match" if ours == theirs else f"DIFFERS by {ours - theirs:+}"
    return f"  {label:<44} {ours:>8}   upstream {theirs:>8}   {mark}"


def audit(graph: Graph, *, root: str | None = None, proof_path_text: str | None = None,
          jaccard: float = 0.9, top: int = 25, upstream: dict | None = None,
          ) -> AuditReport:
    """Produce the report. ``upstream`` holds published figures to compare against."""
    upstream = upstream or {}
    report = AuditReport()
    thms = _theorems(graph)
    defs = [n for n in graph if n.kind == "definition"]
    meta = graph.meta or {}

    # -- 1. what was read ---------------------------------------------------
    s = report.section("Counts")
    pairs = {(e.src, e.dst) for e in graph.edges("proof")}
    step_edges = graph.edges("proof")
    def_ids = {n.id for n in defs}
    # Split by target kind: the upstream docs generator counts citations of
    # *theorems* only, so a like-for-like comparison has to do the same.
    thm_pairs = {p for p in pairs if p[1] not in def_ids}
    def_pairs = pairs - thm_pairs
    s.say("```")
    s.say(_cmp("theorem nodes", len(thms), upstream.get("theorems")))
    s.say(_cmp("definition modules", len(defs), upstream.get("definitions")))
    s.say(_cmp("theorem -> theorem citations", len(thm_pairs),
               upstream.get("citation_edges")))
    s.say(_cmp("theorem -> definition citations", len(def_pairs), None))
    s.say(_cmp("step-level proof edges", len(step_edges), None))
    s.say(_cmp("vocabulary edges", len(graph.edges("vocabulary")), None))
    s.say(_cmp("parse problems", meta.get("problem_count", 0), None))
    s.say("```")
    s.say(f"Edges were derived by `{meta.get('derivation', '?')}`; step attribution "
          f"is `{meta.get('step_attribution', '?')}`. Checked by: "
          f"{meta.get('checked_by', 'unknown')}.")
    s.data = {"theorems": len(thms), "definitions": len(defs),
              "citation_pairs": len(pairs), "theorem_citations": len(thm_pairs),
              "definition_citations": len(def_pairs),
              "step_edges": len(step_edges), "problems": meta.get("problem_count", 0)}

    # -- 2. what the goal actually rests on ---------------------------------
    s = report.section("Closure of the goal theorem")
    root = root or meta.get("root")
    if root and root in graph:
        closure = graph.ancestors(root, ("proof",))
        in_closure = {root} | closure
        thm_ids = {n.id for n in thms}
        inside = in_closure & thm_ids
        outside = sorted(thm_ids - inside)
        depended_on = {e.dst for e in graph.edges("proof")}
        uncited = [t for t in outside if t not in depended_on]
        s.say("```")
        s.say(_cmp(f"theorems reachable from {root}", len(inside),
                   upstream.get("in_closure")))
        s.say(_cmp("theorems outside the closure", len(outside),
                   upstream.get("outside")))
        s.say(_cmp("  of those, cited by nobody", len(uncited),
                   upstream.get("uncited")))
        s.say("```")
        if outside[:20]:
            s.say("Outside: " + ", ".join(outside[:20])
                  + (f" (+{len(outside) - 20} more)" if len(outside) > 20 else ""))
        s.data = {"root": root, "in_closure": len(inside),
                  "outside": len(outside), "uncited": len(uncited),
                  "outside_ids": outside[:200]}
    else:
        s.say(f"No root theorem given or found (`{root}`); closure not computed.")
        s.data = {"root": root}

    # -- 3. citations that are never named ----------------------------------
    s = report.section("Citations never named in the proof script")
    unhit_pairs: list[tuple[str, str]] = []
    for n in thms:
        for dep in n.provenance.get("lean", {}).get("unused_imports", ()) or ():
            unhit_pairs.append((n.id, dep))
    simp_targets = {t.id for t in thms if "simp" in t.tags}
    via_simp = [p for p in unhit_pairs if p[1] in simp_targets]
    s.say("```")
    s.say(_cmp("imported but never named", len(unhit_pairs), upstream.get("unhit")))
    s.say(_cmp("  target is @[simp] (legitimately unnamed)", len(via_simp), None))
    s.say("```")
    s.say("A citation with no textual occurrence is not an error: `simp` and other "
          "automation use lemmas without naming them. It is the honest measure of "
          "how much of the graph the *text* alone can account for.")
    s.data = {"unhit": len(unhit_pairs), "via_simp": len(via_simp),
              "examples": [f"{a} -> {b}" for a, b in unhit_pairs[:20]]}

    # -- 4. hit forms: how much confidence the attribution deserves ---------
    s = report.section("Confidence of line attribution")
    forms: Counter = Counter()
    for n in thms:
        for k, v in (n.provenance.get("lean", {}).get("hit_forms") or {}).items():
            forms[k] += v
    total = sum(forms.values())
    s.say("```")
    for form in ("qualified", "bare-open", "dot", "bare-unopened"):
        v = forms.get(form, 0)
        pct = f"{100 * v / total:5.1f}%" if total else "    —"
        s.say(f"  {form:<20} {v:>8}  {pct}")
    s.say("```")
    s.say("`qualified` means the occurrence carried the theorem's own namespace — "
          "near-certain. `dot` is field notation, where the prefix is a term and the "
          "match is unverifiable without elaboration. Only a term-level extraction "
          "(kernel, not text) can settle the rest.")
    s.data = dict(forms)

    # -- 5. unfinished proofs ------------------------------------------------
    s = report.section("sorry / admit / native_decide")
    holes = [(n.id, n.provenance.get("lean", {})) for n in graph
             if (n.provenance.get("lean", {}) or {}).get("sorry")]
    natives = [n.id for n in graph
               if (n.provenance.get("lean", {}) or {}).get("native_decide")]
    drafts = [n.id for n in thms if n.status != "verified"]
    s.say("```")
    s.say(_cmp("nodes containing sorry/admit", len(holes), None))
    s.say(_cmp("nodes using native_decide", len(natives), None))
    s.say(_cmp("theorem nodes not marked verified", len(drafts), None))
    s.say("```")
    if drafts[:10]:
        s.say("Not verified: " + ", ".join(drafts[:10]))
    s.data = {"sorry": [h[0] for h in holes], "native_decide": natives,
              "not_verified": drafts[:200]}

    # -- 6. duplicate statements --------------------------------------------
    s = report.section("Duplicate and near-duplicate statements")
    by_canon: dict[str, list[str]] = defaultdict(list)
    for n in thms:
        if n.statement_natural:
            key = hashlib.sha1(
                canonical_signature(n.statement_natural).encode("utf-8")).hexdigest()
            by_canon[key].append(n.id)
    exact = [ids for ids in by_canon.values() if len(ids) > 1]
    near = _near_duplicates(thms, threshold=jaccard)
    tagged_dup = [n.id for n in thms if "dup" in n.tags]
    s.say("```")
    s.say(_cmp("exact duplicate groups (binders renamed)", len(exact), None))
    s.say(_cmp("  theorems involved", sum(len(g) for g in exact), None))
    s.say(_cmp(f"near-duplicate candidate pairs (J>={jaccard})", len(near), None))
    s.say(_cmp("tagged P2M.Dup upstream", len(tagged_dup), None))
    s.say("```")
    for group in exact[:5]:
        s.say(f"- exact: {', '.join(group[:6])}")
    for a, b, j in near[:5]:
        s.say(f"- near ({j:.2f}): {a} / {b}")
    s.say("Near-duplicates are *candidates*: token-set Jaccard is order-blind, so "
          "`a ≤ b` and `b ≤ a` score 1.0. They are a reading list, not a finding.")
    s.data = {"exact_groups": exact[:200], "near_pairs": [(a, b, round(j, 3)) for a, b, j in near[:200]],
              "tagged_dup": len(tagged_dup)}

    # -- 7. shape of the dependency graph -----------------------------------
    s = report.section("Shape")
    depths = graph.depths(("proof",))
    cyc = graph.cycles(("proof",))
    deepest = max(depths.items(), key=lambda kv: kv[1]) if depths else ("", 0)
    closure_sizes = graph.closure_sizes(("proof",))
    in_degree = Counter(e.dst for e in {(e.src, e.dst): e for e in graph.edges("proof")}.values())
    s.say("```")
    s.say(_cmp("acyclic", 1 if not cyc else 0, None) + ("" if not cyc else f"  {len(cyc)} cycle(s)!"))
    s.say(_cmp("longest dependency chain", deepest[1], None) + f"   ({deepest[0]})")
    s.say("```")
    s.say("")
    s.say(f"**Most-cited** (distinct citing theorems):")
    s.say("```")
    for node_id, count in in_degree.most_common(top):
        title = graph.get(node_id).title if graph.get(node_id) else "?"
        s.say(f"  {count:>6}  {node_id[:60]:<60} {title[:40]}")
    s.say("```")
    s.say(f"**Largest closures** (rests on the most, transitively):")
    s.say("```")
    for node_id, size in sorted(closure_sizes.items(), key=lambda kv: -kv[1])[:top]:
        s.say(f"  {size:>6}  {node_id[:70]}")
    s.say("```")
    s.data = {"acyclic": not cyc, "longest_chain": deepest[1], "deepest": deepest[0],
              "top_cited": in_degree.most_common(top),
              "largest_closures": sorted(closure_sizes.items(), key=lambda kv: -kv[1])[:top]}

    # -- 8. does the prose route match the graph? ---------------------------
    s = report.section("Landmark route")
    names = list(meta.get("landmarks") or [])
    if proof_path_text:
        seen: list[str] = []
        for name in (_LANDMARK_TICK.findall(proof_path_text)
                     + [f"Def_{d}" for d in _LANDMARK_DEF.findall(proof_path_text)]):
            if name not in seen:
                seen.append(name)
        names = seen
    if not names:
        s.say("No PROOF-PATH landmarks available.")
        s.data = {}
    else:
        by_title = {n.title: n.id for n in graph}
        resolved: list[str] = []
        unresolved: list[str] = []
        for name in names:
            node_id = by_title.get(name) or (name if name in graph else None)
            (resolved if node_id else unresolved).append(node_id or name)
        closure = ({root} | graph.ancestors(root, ("proof",))) if root and root in graph else set()
        outside = [r for r in resolved if closure and r not in closure]
        s.say("```")
        s.say(_cmp("landmark names in PROOF-PATH.md", len(names), upstream.get("landmarks")))
        s.say(_cmp("  resolved to a node", len(resolved), None))
        s.say(_cmp("  not in this corpus (Mathlib, prose)", len(unresolved), None))
        s.say(_cmp("  resolved but OUTSIDE the goal closure", len(outside), None))
        s.say("```")
        if unresolved[:12]:
            s.say("Unresolved: " + ", ".join(unresolved[:12]))
        if outside:
            s.say("**Outside the closure:** " + ", ".join(outside[:12])
                  + " — a landmark the goal does not rest on is either prose "
                    "scaffolding or a gap in the import graph.")
        # Does the narrative order agree with the dependency order?
        breaks = 0
        for earlier, later in zip(resolved, resolved[1:]):
            if later != earlier and earlier not in graph.ancestors(later, ("proof",)):
                breaks += 1
        s.say(f"Consecutive landmark pairs where the later one does not depend on "
              f"the earlier: {breaks}/{max(len(resolved) - 1, 0)} — expected to be "
              f"non-zero, since a prose route is a narrative, not a chain.")
        s.data = {"landmarks": len(names), "resolved": len(resolved),
                  "unresolved": unresolved[:50], "outside_closure": outside[:50],
                  "order_breaks": breaks}

    # -- 9. internal consistency --------------------------------------------
    s = report.section("Consistency")
    problems = Counter(p["code"] for p in (meta.get("problems") or []))
    no_axioms = sum(1 for n in thms
                    if not (n.provenance.get("lean", {}) or {}).get("has_print_axioms"))
    s.say("```")
    for code, count in problems.most_common():
        s.say(f"  {code:<44} {count:>8}")
    s.say(_cmp("proofs without #print axioms", no_axioms, None))
    s.say("```")
    s.say("`#print axioms` appears in only a small fraction of proof files, so it is "
          "recorded but not required for `verified`: the kernel guarantee comes from "
          "the statement/solution tail and the upstream build, not from that command.")
    s.data = {"problems": dict(problems), "without_print_axioms": no_axioms}

    return report


def _near_duplicates(thms: Iterable[Node], *, threshold: float,
                     bands: int = 6, sample_cap: int = 40000,
                     ) -> list[tuple[str, str, float]]:
    """Candidate duplicate statements, via MinHash banding then exact Jaccard.

    Comparing every pair of 29,511 statements is 435 million comparisons. Banded
    MinHash puts likely pairs in the same bucket first; the exact score is then
    computed only for those, so the result is exact for what it reports and may
    miss a pair with probability at most ``(1 - J^1)^bands``.
    """
    items = [(n.id, tokens(n.statement_natural)) for n in thms if n.statement_natural]
    if len(items) > sample_cap:
        items = random.Random(0).sample(items, sample_cap)

    def sig(toks: set[str], salt: int) -> int:
        return min((hash((salt, t)) for t in toks), default=0)

    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, (_, toks) in enumerate(items):
        if len(toks) < 3:
            continue
        for band in range(bands):
            buckets[(band, sig(toks, band))].append(i)

    seen: set[tuple[int, int]] = set()
    out: list[tuple[str, str, float]] = []
    for members in buckets.values():
        if len(members) < 2 or len(members) > 50:
            continue
        for a_i in range(len(members)):
            for b_i in range(a_i + 1, len(members)):
                pair = (members[a_i], members[b_i])
                if pair in seen:
                    continue
                seen.add(pair)
                a_id, a_t = items[pair[0]]
                b_id, b_t = items[pair[1]]
                union = len(a_t | b_t)
                if not union:
                    continue
                j = len(a_t & b_t) / union
                if j >= threshold:
                    out.append((a_id, b_id, j))
    out.sort(key=lambda r: -r[2])
    return out
