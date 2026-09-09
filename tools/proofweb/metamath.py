"""Mechanistic extraction of step-level proof graphs from Metamath databases.

This module is the project's answer to RISKS.md section 1 ("there is no
correctness criterion for an edge"). For hand-written YAML nodes that criticism
is structural and stands. For nodes extracted here it does not apply, because
the edges are not authored at all: they are read off a formal proof and checked
by a verifier before a single edge is emitted.

Why Metamath, and not Lean or Rocq, as the first formal substrate:

- A Metamath database is one plain-text file. No toolchain, no build, no
  40-package ecosystem — this file plus ~600 lines of Python is the entire
  pipeline, which is the point of a *mechanistic* extractor.
- The proof format IS the step structure. A Metamath proof is a sequence of
  labels applied RPN-style to a stack; "which prior theorem is used at which
  step" is not reconstructed, it is literally what the file says.
- Verification is simple enough to reimplement and audit (the algorithm is
  Appendix B of the Metamath book; mmverify.py is the canonical ~350-line
  reference). We verify every proof we extract, so an extracted edge means:
  a machine replayed this proof from axioms and it checks.

The Lean and Rocq paths are designed in docs/FORMAL-TRACK.md; they need real
toolchains and are deliberately not faked here.

Trust statement, precisely: an extracted edge is backed by THIS verifier, which
implements substitution, stack replay, and disjoint-variable checks per the
Metamath spec. It is not metamath.exe. Cross-check big claims against the
canonical tools before publishing them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from .model import Node, Step

Sym = str
Stmt = tuple[Sym, ...]

#: Typecodes whose statements are *assertions about mathematics* rather than
#: grammar. Everything else (wff, class, setvar, ...) is syntax: needed to say
#: things, invisible in a dependency argument. set.mm uses '|-'.
LOGICAL_TYPECODES = frozenset({"|-"})


class MMError(Exception):
    """The database is malformed or a proof does not verify."""


class MMIncompleteProof(MMError):
    """The proof contains '?' placeholders: not wrong, just not finished."""


# ---------------------------------------------------------------------------
# tokenizer
# ---------------------------------------------------------------------------


def tokens(text: str) -> Iterator[str]:
    """Metamath tokens with comments stripped.

    The grammar is whitespace-separated tokens, full stop. Comments are
    ``$( ... $)`` and do not nest; file inclusion ``$[ ... $]`` is rejected
    rather than silently ignored, because pretending to have read a file you
    did not read is exactly the kind of lie this project exists to prevent.
    """
    it = iter(text.split())
    for tok in it:
        if tok == "$(":
            for t in it:
                if t == "$)":
                    break
            else:
                raise MMError("unterminated comment $( ...")
            continue
        if tok == "$[":
            raise MMError("file inclusion ($[ ... $]) is not supported; "
                          "flatten the database first")
        yield tok


# ---------------------------------------------------------------------------
# frames and assertions
# ---------------------------------------------------------------------------


@dataclass
class _Frame:
    v: set[Sym] = field(default_factory=set)
    d: set[frozenset[Sym]] = field(default_factory=set)
    # (declaration sequence number, label, ...) — the sequence number exists
    # because mandatory hypotheses are ordered by DECLARATION, and $f and $e
    # may interleave. set.mm happens never to declare an $f after an $e, so an
    # implementation that assumes "all $f first" passes set.mm and silently
    # mis-verifies a database that interleaves. Spec first, corpus second.
    f: list[tuple[int, str, Sym, Sym]] = field(default_factory=list)
    e: list[tuple[int, str, Stmt]] = field(default_factory=list)


#: One mandatory hypothesis: ("f", label, typecode, var) or ("e", label, stmt).
MandHyp = tuple


@dataclass(frozen=True)
class Assertion:
    """A ``$a`` or ``$p`` with the frame it was declared under.

    ``mandatory`` is the full list of mandatory hypotheses **in declaration
    order** — exactly what a proof of a using theorem must supply, in exactly
    that order (the compressed-proof numbering depends on it too). ``dvs`` are
    the disjoint-variable pairs among mandatory variables.
    """

    label: str
    kind: str                                  # '$a' | '$p'
    stmt: Stmt
    mandatory: tuple[MandHyp, ...]
    dvs: frozenset[frozenset[Sym]]

    @property
    def typecode(self) -> Sym:
        return self.stmt[0]

    @property
    def is_logical(self) -> bool:
        return self.typecode in LOGICAL_TYPECODES

    @property
    def n_mandatory(self) -> int:
        return len(self.mandatory)

    @property
    def f_hyps(self) -> list[tuple[str, Sym, Sym]]:
        return [(h[1], h[2], h[3]) for h in self.mandatory if h[0] == "f"]

    @property
    def e_hyps(self) -> list[tuple[str, Stmt]]:
        return [(h[1], h[2]) for h in self.mandatory if h[0] == "e"]


@dataclass(frozen=True)
class StepRecord:
    """One push in the proof replay — the raw material of step-level edges.

    ``args`` are the indices of the step records whose results this step
    consumed, in mandatory-hypothesis order. That is the provenance a
    dependency graph needs and a flat "uses" list throws away.
    """

    index: int
    kind: str            # 'hyp-f' | 'hyp-e' | 'apply'
    label: str
    expr: Stmt
    args: tuple[int, ...] = ()

    @property
    def is_logical(self) -> bool:
        return bool(self.expr) and self.expr[0] in LOGICAL_TYPECODES


@dataclass(frozen=True)
class VerifiedProof:
    label: str
    steps: tuple[StepRecord, ...]
    conclusion: Stmt


# ---------------------------------------------------------------------------
# the database
# ---------------------------------------------------------------------------


class Database:
    """A parsed (and, for every ``$p`` kept, verified) Metamath database.

    Parsing is eager and single-pass: each ``$p`` is verified in the live
    scope it was declared in, which is what makes dummy-variable hypotheses
    and local ``$d`` restrictions come out right without snapshotting frames.
    """

    def __init__(self, *, keep_steps: bool = True) -> None:
        #: keep_steps=False verifies everything but discards the replay logs —
        #: a whole-set.mm verification pass holds tens of millions of step
        #: records otherwise, and a scale test only needs the verdicts.
        self.keep_steps = keep_steps
        self.constants: set[Sym] = set()
        self.variables_ever: set[Sym] = set()
        self.assertions: dict[str, Assertion] = {}
        self.order: list[str] = []                      # $a/$p labels, in file order
        self.proofs: dict[str, VerifiedProof] = {}      # label -> verified replay
        self.failures: dict[str, str] = {}              # label -> why it did not verify
        self._frames: list[_Frame] = [_Frame()]
        self._hyps: dict[str, tuple[str, Stmt]] = {}    # label -> ('f'|'e', stmt)
        self._seq = 0                                   # hypothesis declaration order

    # -- scope helpers ------------------------------------------------------

    def _active_vars(self) -> set[Sym]:
        return set().union(*(fr.v for fr in self._frames))

    def _active_dvs(self) -> set[frozenset[Sym]]:
        return set().union(*(fr.d for fr in self._frames))

    def _active_f(self) -> list[tuple[int, str, Sym, Sym]]:
        return [h for fr in self._frames for h in fr.f]

    def _active_e(self) -> list[tuple[int, str, Stmt]]:
        return [h for fr in self._frames for h in fr.e]

    def _make_assertion(self, label: str, kind: str, stmt: Stmt) -> Assertion:
        e_active = self._active_e()
        mand_vars = {t for hyp in ([s for _, _, s in e_active] + [stmt]) for t in hyp
                     if t in self.variables_ever and t in self._active_vars()}
        f_mand = [h for h in self._active_f() if h[3] in mand_vars]
        declared = {h[3] for h in f_mand}
        missing = mand_vars - declared
        if missing:
            raise MMError(f"{label}: variable(s) {sorted(missing)} have no active $f")

        # Declaration order, with $f and $e interleaved as they were declared.
        merged = sorted(
            [("f", seq, lbl, tc, var) for seq, lbl, tc, var in f_mand]
            + [("e", seq, lbl, s) for seq, lbl, s in e_active],
            key=lambda h: h[1])
        mandatory = tuple(
            ("f", h[2], h[3], h[4]) if h[0] == "f" else ("e", h[2], h[3])
            for h in merged)

        dvs = frozenset(p for p in self._active_dvs() if p <= mand_vars)
        return Assertion(label, kind, stmt, mandatory, dvs)

    # -- parsing ------------------------------------------------------------

    def parse(self, text: str, *, verify: bool = True,
              stop_after_p: int | None = None, stop_at: str | None = None) -> None:
        """Read a database, verifying each kept ``$p`` as it is declared.

        ``stop_after_p`` / ``stop_at`` exist because set.mm is fifty megabytes
        and an extraction demo is not obliged to replay all of it. Stopping
        early is sound: Metamath is strictly declare-before-use, so everything
        parsed so far is self-contained.
        """
        toks = tokens(text)
        p_count = 0
        label: str | None = None

        def read_until(end: str) -> list[str]:
            out = []
            for t in toks:
                if t == end:
                    return out
                out.append(t)
            raise MMError(f"unexpected end of file, expected {end}")

        for tok in toks:
            if tok == "${":
                self._frames.append(_Frame())
            elif tok == "$}":
                if len(self._frames) == 1:
                    raise MMError("unmatched $}")
                closing = self._frames.pop()
                for _, lbl, *_rest in closing.f:
                    self._hyps.pop(lbl, None)
                for _, lbl, _stmt in closing.e:
                    self._hyps.pop(lbl, None)
            elif tok == "$c":
                for sym in read_until("$."):
                    if sym in self.constants:
                        raise MMError(f"constant {sym} declared twice")
                    self.constants.add(sym)
            elif tok == "$v":
                for sym in read_until("$."):
                    self._frames[-1].v.add(sym)
                    self.variables_ever.add(sym)
            elif tok == "$d":
                syms = read_until("$.")
                for i, a in enumerate(syms):
                    for b in syms[i + 1:]:
                        if a == b:
                            raise MMError(f"$d lists {a} twice")
                        self._frames[-1].d.add(frozenset((a, b)))
            elif tok in ("$f", "$e", "$a", "$p"):
                if label is None:
                    raise MMError(f"{tok} statement without a label")
                if tok == "$f":
                    body = read_until("$.")
                    if len(body) != 2:
                        raise MMError(f"{label}: $f must be 'typecode var'")
                    tc, var = body
                    self._seq += 1
                    self._frames[-1].f.append((self._seq, label, tc, var))
                    self._hyps[label] = ("f", (tc, var))
                elif tok == "$e":
                    body = tuple(read_until("$."))
                    self._seq += 1
                    self._frames[-1].e.append((self._seq, label, body))
                    self._hyps[label] = ("e", body)
                elif tok == "$a":
                    stmt = tuple(read_until("$."))
                    a = self._make_assertion(label, "$a", stmt)
                    self.assertions[label] = a
                    self.order.append(label)
                else:  # $p
                    body = read_until("$.")
                    if "$=" not in body:
                        raise MMError(f"{label}: $p without a proof")
                    cut = body.index("$=")
                    stmt, proof = tuple(body[:cut]), body[cut + 1:]
                    a = self._make_assertion(label, "$p", stmt)
                    self.assertions[label] = a
                    self.order.append(label)
                    if verify:
                        try:
                            self.proofs[label] = self._verify(a, proof)
                        except MMIncompleteProof as exc:
                            self.failures[label] = f"incomplete: {exc}"
                        # A hard verification failure is not recorded and
                        # skipped: it means the database is wrong or the
                        # verifier is, and both demand attention, not a flag.
                    p_count += 1
                    if stop_after_p is not None and p_count >= stop_after_p:
                        return
                    if stop_at is not None and label == stop_at:
                        return
                label = None
                continue
            elif tok in ("$.", "$="):
                raise MMError(f"unexpected {tok}")
            else:
                if label is not None:
                    raise MMError(f"two labels in a row: {label} {tok}")
                if not re.fullmatch(r"[A-Za-z0-9._-]+", tok):
                    raise MMError(f"not a valid label: {tok}")
                label = tok
                continue
            label = None

    # -- proof verification --------------------------------------------------

    def _decompress(self, assertion: Assertion, proof: list[str]) -> list[str | int]:
        """Compressed format → a flat list of labels and saved-step references.

        The encoding (Metamath book, Appendix B): within ``( labels ) LETTERS``,
        A–T are base-20 digits completing a number, U–Y are base-5 continuation
        digits, Z tags the previous step for reuse. Numbers mean, in order:
        mandatory hypotheses of the theorem being proved, then the labels in
        parentheses, then tagged steps. References to tagged steps come back as
        ``int`` (index into the saved list); everything else as a label.
        """
        if proof[0] != "(":
            raise MMError(f"{assertion.label}: expected compressed proof")
        close = proof.index(")")
        listed = proof[1:close]
        letters = "".join(proof[close + 1:])
        if "?" in letters:
            raise MMIncompleteProof(assertion.label)

        mand = [h[1] for h in assertion.mandatory]     # declaration order
        m, n = len(mand), len(listed)

        out: list[str | int] = []
        acc = 0
        tag_count = 0
        for ch in letters:
            if "A" <= ch <= "T":
                num = acc * 20 + (ord(ch) - ord("A") + 1)
                acc = 0
                if num <= m:
                    out.append(mand[num - 1])
                elif num <= m + n:
                    out.append(listed[num - m - 1])
                else:
                    ref = num - m - n - 1
                    if ref >= tag_count:
                        raise MMError(f"{assertion.label}: reference to "
                                      f"tagged step {ref} before it is tagged")
                    out.append(ref)
            elif "U" <= ch <= "Y":
                acc = acc * 5 + (ord(ch) - ord("U") + 1)
            elif ch == "Z":
                if not out or out[-1] == "\x00Z":
                    raise MMError(f"{assertion.label}: Z with no step to tag")
                out.append("\x00Z")            # marker consumed by the replayer
                tag_count += 1
            else:
                raise MMError(f"{assertion.label}: bad character {ch!r} in proof")
        if acc:
            raise MMError(f"{assertion.label}: truncated number in proof")
        return out

    @staticmethod
    def _subst(stmt: Stmt, sub: dict[Sym, Stmt]) -> Stmt:
        out: list[Sym] = []
        for t in stmt:
            if t in sub:
                out.extend(sub[t])
            else:
                out.append(t)
        return tuple(out)

    def _verify(self, assertion: Assertion, proof: list[str]) -> VerifiedProof:
        """Replay the proof against a stack machine and check every step.

        This is the whole trust story, so the invariants are spelled out:
        hypothesis labels push their statement; assertion labels pop exactly
        their mandatory hypotheses, which must unify ($f slots define the
        substitution, $e slots must match under it), disjoint-variable
        conditions must hold under the ambient $d set, and the final stack
        must be exactly the theorem's statement. Anything else raises.
        """
        ambient_dvs = self._active_dvs()

        if proof and proof[0] == "(":
            seq = self._decompress(assertion, proof)
        else:
            if "?" in proof:
                raise MMIncompleteProof(assertion.label)
            seq = list(proof)

        steps: list[StepRecord] = []
        stack: list[Stmt] = []
        prov: list[int] = []                    # provenance: step index per entry
        saved: list[tuple[Stmt, int]] = []      # Z-tagged (expr, step index)

        def push(rec: StepRecord) -> None:
            steps.append(rec)
            stack.append(rec.expr)
            prov.append(rec.index)

        for item in seq:
            if item == "\x00Z":
                if not stack:
                    raise MMError(f"{assertion.label}: Z on empty stack")
                saved.append((stack[-1], prov[-1]))
                continue
            if isinstance(item, int):
                expr, idx = saved[item]
                stack.append(expr)
                prov.append(idx)               # a reuse is not a new step
                continue

            if item in self._hyps:
                kind, stmt = self._hyps[item]
                push(StepRecord(len(steps), f"hyp-{kind}", item, stmt))
                continue

            ref = self.assertions.get(item)
            if ref is None:
                raise MMError(f"{assertion.label}: unknown label {item}")
            npop = ref.n_mandatory
            if len(stack) < npop:
                raise MMError(f"{assertion.label}: stack underflow applying {item}")
            popped = stack[len(stack) - npop:]
            popped_prov = prov[len(prov) - npop:]
            del stack[len(stack) - npop:]
            del prov[len(prov) - npop:]

            # Two passes over the popped entries, aligned with the mandatory
            # hypotheses in declaration order. All $f slots must be processed
            # before any $e slot is checked: an $e may precede an $f whose
            # variable it does not use, so checking in a single pass would
            # test the $e against an incomplete substitution.
            sub: dict[Sym, Stmt] = {}
            for hyp, entry in zip(ref.mandatory, popped):
                if hyp[0] != "f":
                    continue
                _, _, tc, var = hyp
                if not entry or entry[0] != tc:
                    raise MMError(f"{assertion.label}: applying {item}, expected "
                                  f"typecode {tc}, got {' '.join(entry) or '<empty>'}")
                sub[var] = entry[1:]
            for hyp, entry in zip(ref.mandatory, popped):
                if hyp[0] != "e":
                    continue
                _, lbl, stmt = hyp
                if self._subst(stmt, sub) != entry:
                    raise MMError(
                        f"{assertion.label}: applying {item}, hypothesis {lbl} "
                        f"wants {' '.join(self._subst(stmt, sub))}, "
                        f"stack has {' '.join(entry)}")

            # Disjoint-variable conditions: for each $d pair of the applied
            # assertion, the substituted expressions must share no variable,
            # and every cross pair must itself be $d in the ambient frame.
            for pair in ref.dvs:
                x, y = tuple(pair)
                xs = [t for t in sub.get(x, (x,)) if t in self.variables_ever]
                ys = [t for t in sub.get(y, (y,)) if t in self.variables_ever]
                for u in xs:
                    for v in ys:
                        if u == v:
                            raise MMError(
                                f"{assertion.label}: applying {item} violates "
                                f"$d {x} {y}: both map through variable {u}")
                        if frozenset((u, v)) not in ambient_dvs:
                            raise MMError(
                                f"{assertion.label}: applying {item} needs "
                                f"$d {u} {v}, which is not in scope")

            # $e provenance only, in declaration order: $f slots carry grammar,
            # and a dependency argument is about the logical premises, not
            # about how their wffs were spelled.
            args = tuple(p for hyp, p in zip(ref.mandatory, popped_prov)
                         if hyp[0] == "e")
            push(StepRecord(len(steps), "apply", item,
                            self._subst(ref.stmt, sub), args))

        if len(stack) != 1:
            raise MMError(f"{assertion.label}: proof ends with "
                          f"{len(stack)} entries on the stack")
        if stack[0] != assertion.stmt:
            raise MMError(f"{assertion.label}: proof concludes "
                          f"{' '.join(stack[0])}, statement says "
                          f"{' '.join(assertion.stmt)}")
        return VerifiedProof(assertion.label,
                             tuple(steps) if self.keep_steps else (),
                             stack[0])


# ---------------------------------------------------------------------------
# extraction into ProofWeb nodes
# ---------------------------------------------------------------------------


def _node_kind(a: Assertion) -> str:
    if a.kind == "$p":
        return "theorem"
    if not a.is_logical:
        return "background"                     # grammar: how to *say* things
    return "definition" if a.label.startswith("df-") else "axiom"


def _title(a: Assertion) -> str:
    if a.kind == "$a" and not a.is_logical:
        return f"Syntax: {a.label}"
    return a.label


def extract(db: Database, *, module: str, source: str) -> list[Node]:
    """Turn a parsed+verified database into ProofWeb nodes.

    The mapping, and the reasoning behind each choice:

    - Steps are the *logical* replay steps only (typecode ``|-``). The grammar
      steps that assemble wffs are real work for the checker but noise in a
      dependency argument; they surface instead as vocabulary (`context`).
    - ``by`` of an application step = the earlier logical steps it consumed
      (as stable ``s:<id>`` references, in mandatory order) plus the label it
      applied. This is exactly the schema's semantics, produced by a machine.
    - A node is ``verified`` only if the proof replayed through the verifier.
      An unverified node (incomplete proof) stays ``draft`` and says why.
    """
    if not db.keep_steps:
        raise MMError("extract() needs a database parsed with keep_steps=True; "
                      "a keep_steps=False parse is a verification pass only")

    nodes: list[Node] = []
    for label in db.order:
        a = db.assertions[label]
        kind = _node_kind(a)

        hypotheses = tuple(f"{lbl}: {' '.join(stmt)}" for lbl, stmt in a.e_hyps)
        statement = " ".join(a.stmt)

        steps: tuple[Step, ...] = ()
        context: tuple[str, ...] = ()
        status = "draft"
        provenance: dict[str, object] = {
            "source": source,
            "contributed_by": "proofweb.metamath extractor (mechanical, no AI)",
        }

        if a.kind == "$p":
            vp = db.proofs.get(label)
            if vp is None:
                provenance["note"] = db.failures.get(
                    label, "proof was not verified; node kept as draft")
            else:
                logical = [s for s in vp.steps if s.is_logical]
                sid_of = {s.index: str(i + 1) for i, s in enumerate(logical)}
                built: list[Step] = []
                syntax_used: set[str] = set()
                for s in vp.steps:
                    if s.kind == "apply":
                        ref = db.assertions[s.label]
                        if not ref.is_logical:
                            syntax_used.add(s.label)
                    if not s.is_logical:
                        continue
                    n = len(built) + 1
                    if s.kind == "hyp-e":
                        by: tuple[str, ...] = (f"hyp:{s.label}",)
                    else:
                        by = tuple(f"s:{sid_of[i]}" for i in s.args
                                   if i in sid_of) + (s.label,)
                    built.append(Step(n=n, sid=sid_of[s.index],
                                      claim=" ".join(s.expr), by=by))
                steps = tuple(built)
                context = tuple(sorted(syntax_used))
                status = "verified"
                provenance["note"] = (
                    "proof replayed and checked by proofweb's Metamath "
                    "verifier (substitution, stack discipline, $d conditions)")

        nodes.append(Node(
            id=label,
            kind=kind,
            title=_title(a),
            statement_natural=statement,
            statement_latex=None,
            context=context,
            strategy=None,
            hypotheses=hypotheses,
            steps=steps,
            status=status,
            formalization={"metamath": label},
            provenance=provenance,
            tags=(),
            module=module,
            source_path=f"{source}:{label}",
            raw={},
        ))
    return nodes


# ---------------------------------------------------------------------------
# extracted-graph JSON: write and read back
# ---------------------------------------------------------------------------


def nodes_to_json(nodes: Iterable[Node], *, module: str, source: str,
                  meta: dict | None = None) -> dict:
    """Serialise nodes to the interchange format.

    ``meta`` carries corpus-level facts an importer knows and a node does not:
    which commit, how the edges were derived, what checked the proofs. It is
    descriptive only — no query reads it — but it is what lets a reader of a
    30,000-node file tell a kernel-replayed graph from a text-derived one.
    """
    payload = {
        "format": "proofweb/extracted",
        "version": 1,
        "module": module,
        "source": source,
        "nodes": [
            {
                "id": n.id, "kind": n.kind, "title": n.title,
                "statement": n.statement_natural,
                "hypotheses": list(n.hypotheses),
                "context": list(n.context),
                "status": n.status,
                "formalization": n.formalization,
                "provenance": n.provenance,
                "tags": list(n.tags),
                "source_path": n.source_path,
                "steps": [
                    {"n": s.n, "id": s.sid, "claim": s.claim, "by": list(s.by),
                     **({"note": s.note} if s.note else {})}
                    for s in n.steps
                ],
            }
            for n in nodes
        ],
    }
    if meta:
        payload["meta"] = meta
    return payload


def nodes_from_json(data: dict) -> list[Node]:
    if data.get("format") != "proofweb/extracted":
        raise MMError("not a proofweb/extracted JSON document")
    module = data.get("module", "extracted")
    source = data.get("source", "")
    out: list[Node] = []
    for nd in data["nodes"]:
        steps = tuple(
            Step(n=s["n"], sid=s.get("id"), claim=s["claim"],
                 by=tuple(s["by"]), note=s.get("note"))
            for s in nd.get("steps", ())
        )
        out.append(Node(
            id=nd["id"], kind=nd["kind"], title=nd["title"],
            statement_natural=nd["statement"],
            statement_latex=None,
            context=tuple(nd.get("context", ())),
            strategy=None,
            hypotheses=tuple(nd.get("hypotheses", ())),
            steps=steps,
            status=nd.get("status", "draft"),
            formalization=dict(nd.get("formalization", {})),
            provenance=dict(nd.get("provenance", {})),
            tags=tuple(nd.get("tags", ())),
            module=module,
            source_path=nd.get("source_path") or f"{source}:{nd['id']}",
            raw={},
        ))
    return out


def extract_file(path: str | Path, *, stop_after_p: int | None = None,
                 stop_at: str | None = None) -> tuple[Database, list[Node]]:
    """Parse, verify and extract a ``.mm`` file in one call."""
    p = Path(path)
    db = Database()
    db.parse(p.read_text(encoding="utf-8"),
             stop_after_p=stop_after_p, stop_at=stop_at)
    module = f"metamath-{p.stem}"
    nodes = extract(db, module=module, source=p.name)
    return db, nodes
