"""Every invariant of a proof graph that a machine can check.

The point of this file is to make the graph *falsifiable*. A knowledge graph
nobody can check is a diagram; a knowledge graph that fails CI when a proof
cites a lemma it never uses is an assertion about mathematics.

Two severities:

``error``
    The graph is broken. CI fails. Examples: a step cites a node that does not
    exist, a proof depends on itself, a node claims ``verified`` with nothing
    to back it.

``warning``
    The graph is suspicious but coherent. CI passes unless ``--strict``.
    Examples: a declared hypothesis no step ever uses, a theorem no other
    theorem builds on.

What is deliberately NOT checked: whether a step's claim actually follows from
its justifications. No program can do that for informal mathematics — that is
what human review and the ``formalization`` cross-links are for. This module
checks the *bookkeeping* is honest, not that the mathematics is right.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from .loader import load_graph, load_manifests, load_schema
from .model import Graph, Node, classify_token

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    node: str | None
    message: str
    where: str = ""

    def __str__(self) -> str:
        loc = f"{self.where}: " if self.where else ""
        who = f"[{self.node}] " if self.node else ""
        return f"{self.severity.upper():7} {self.code:22} {loc}{who}{self.message}"


class Report:
    def __init__(self, findings: Iterable[Finding] = ()) -> None:
        self.findings: list[Finding] = list(findings)

    def add(self, severity: Severity, code: str, node: str | None, message: str, where: str = "") -> None:
        self.findings.append(Finding(severity, code, node, message, where))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    def ok(self, strict: bool = False) -> bool:
        return not self.errors and (not strict or not self.warnings)

    def __len__(self) -> int:
        return len(self.findings)


# ---------------------------------------------------------------------------
# individual checks
# ---------------------------------------------------------------------------


def check_schema(graph: Graph, report: Report) -> None:
    """Validate every node against ``schema/node.schema.json``."""
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - environment without the dep
        report.add("warning", "schema.unavailable", None,
                   "jsonschema is not installed; per-node schema validation skipped")
        return

    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    for node in graph:
        for err in sorted(validator.iter_errors(node.raw), key=lambda e: list(e.path)):
            path = "/".join(str(p) for p in err.path) or "<root>"
            report.add("error", "schema.invalid", node.id,
                       f"{path}: {err.message}", node.source_path)


def check_duplicate_ids(graph: Graph, report: Report) -> None:
    for node_id, first, second in graph.duplicate_ids:
        report.add("error", "id.duplicate", node_id,
                   f"id defined twice: {first} and {second}")


def check_references_resolve(graph: Graph, report: Report) -> None:
    """No edge may point at a node that does not exist."""
    for node in graph:
        for dep in node.context:
            if dep not in graph:
                report.add("error", "ref.dangling", node.id,
                           f"statement context names '{dep}', which does not exist",
                           node.source_path)
        for step in node.steps:
            for dep in step.node_refs():
                if dep not in graph:
                    report.add("error", "ref.dangling", node.id,
                               f"step {step.n} cites '{dep}', which does not exist",
                               node.source_path)


def check_step_numbering(graph: Graph, report: Report) -> None:
    """Steps must be numbered 1..n with no gaps and no repeats."""
    for node in graph:
        if not node.steps:
            continue
        seen = [s.n for s in node.steps]
        expected = list(range(1, len(seen) + 1))
        if seen != expected:
            report.add("error", "step.numbering", node.id,
                       f"steps are numbered {seen}, expected {expected}",
                       node.source_path)


def check_step_back_references(graph: Graph, report: Report) -> None:
    """A step may only cite *earlier* steps of the same proof.

    Forward references are circular reasoning in miniature, and they are easy to
    introduce by accident when a proof is reordered.
    """
    for node in graph:
        available = {s.n for s in node.steps}
        for step in node.steps:
            for ref in step.step_refs():
                if ref not in available:
                    report.add("error", "step.missing", node.id,
                               f"step {step.n} cites step s{ref}, which does not exist",
                               node.source_path)
                elif ref >= step.n:
                    report.add("error", "step.forward-reference", node.id,
                               f"step {step.n} cites step s{ref}; a step may only "
                               f"cite steps before it",
                               node.source_path)


def check_step_identity(graph: Graph, report: Report) -> None:
    """Stable step ids must be unique, and citations should use them.

    Ordinals renumber the moment a step is inserted. If ``s3`` is used as a
    justification and a step is later added at position 2, the citation silently
    changes meaning — it still resolves, still validates, and now points at the
    wrong line. That is the worst class of defect this project can have, because
    nothing surfaces it. Stable ids exist to make it impossible.
    """
    for node in graph:
        if not node.steps:
            continue

        seen: dict[str, int] = {}
        for step in node.steps:
            if step.sid is None:
                continue
            if step.sid in seen:
                report.add("error", "step.duplicate-id", node.id,
                           f"step {step.n} reuses the id '{step.sid}', already used by "
                           f"step {seen[step.sid]}; ids must be unique and are never reused",
                           node.source_path)
            seen[step.sid] = step.n

        by_id = {s.sid: s for s in node.steps if s.sid}
        for step in node.steps:
            for ref in step.step_id_refs():
                target = by_id.get(ref)
                if target is None:
                    report.add("error", "step.missing-id", node.id,
                               f"step {step.n} cites 's:{ref}', which is not a step of "
                               f"this proof",
                               node.source_path)
                elif target.n >= step.n:
                    report.add("error", "step.forward-reference", node.id,
                               f"step {step.n} cites 's:{ref}' (step {target.n}); a step "
                               f"may only cite steps before it",
                               node.source_path)

            # Ordinal citations are fragile wherever stable ids are available.
            if step.step_refs() and any(s.sid for s in node.steps):
                report.add("warning", "step.ordinal-citation", node.id,
                           f"step {step.n} cites an earlier step by ordinal (s<n>); use "
                           f"'s:<id>' so the citation survives a step being inserted",
                           node.source_path)


def check_hypotheses(graph: Graph, report: Report) -> None:
    """Cited hypotheses must be declared, and declared hypotheses should be used."""
    for node in graph:
        declared = set(node.hypothesis_names)
        used: set[str] = set()
        for step in node.steps:
            for name in step.hyp_refs():
                if name is None:
                    # bare 'hyp' is only meaningful when there is exactly one
                    if len(declared) > 1:
                        report.add("error", "hyp.ambiguous", node.id,
                                   f"step {step.n} says 'hyp' but {len(declared)} "
                                   f"hypotheses are declared; name it 'hyp:<name>'",
                                   node.source_path)
                    elif not declared:
                        report.add("error", "hyp.undeclared", node.id,
                                   f"step {step.n} cites 'hyp' but the proof declares none",
                                   node.source_path)
                    used |= declared
                elif name not in declared:
                    report.add("error", "hyp.undeclared", node.id,
                               f"step {step.n} cites hypothesis '{name}', which is not declared",
                               node.source_path)
                else:
                    used.add(name)
        for name in sorted(declared - used):
            report.add("warning", "hyp.unused", node.id,
                       f"hypothesis '{name}' is declared but no step uses it",
                       node.source_path)


def check_kind_obligations(graph: Graph, report: Report) -> None:
    """Theorems prove something; axioms do not."""
    for node in graph:
        if node.is_theorem and not node.steps:
            report.add("error", "kind.no-proof", node.id,
                       "declared as a theorem but carries no proof steps",
                       node.source_path)
        if node.kind == "module":
            # A module carries at most one step: the file's imports. Anything
            # else would be dressing an import list up as a proof.
            if any(st.sid != "imports" for st in node.steps) or len(node.steps) > 1:
                report.add("error", "kind.module-steps", node.id,
                           "a module node may carry only its single 'imports' step",
                           node.source_path)
        elif not node.is_theorem and node.steps:
            report.add("error", "kind.unexpected-proof", node.id,
                       f"kind '{node.kind}' must not carry a proof",
                       node.source_path)
        if node.is_theorem and node.steps and not node.proof_deps():
            report.add("warning", "kind.self-contained", node.id,
                       "no step cites any other node; this theorem is disconnected "
                       "from the graph, which is almost always a missing citation",
                       node.source_path)


def check_acyclic(graph: Graph, report: Report) -> None:
    """A result may not, transitively, be used in its own proof."""
    for cycle in graph.cycles(("proof",)):
        report.add("error", "graph.cycle", cycle[0],
                   "circular dependency: " + " -> ".join(cycle))
    # Vocabulary edges may legitimately look circular (A4 mentions e from A3
    # while T1 is about e), so they are reported separately and only as a warning.
    proof_cycles = {frozenset(c) for c in graph.cycles(("proof",))}
    for cycle in graph.cycles(("proof", "vocabulary")):
        if frozenset(cycle) not in proof_cycles:
            report.add("warning", "graph.vocabulary-cycle", cycle[0],
                       "cycle through statement-context edges: " + " -> ".join(cycle))


def check_module_imports(graph: Graph, report: Report, root: Path | None = None) -> None:
    """A module may only cite its own nodes and those of modules it imports."""
    manifests = load_manifests(root)
    if not manifests:
        return
    module_of = {n.id: n.module for n in graph}
    visible: dict[str, set[str]] = {}
    for mid, data in manifests.items():
        visible[mid] = {mid} | {str(i) for i in (data.get("imports") or [])}

    for node in graph:
        allowed = visible.get(node.module, {node.module})
        for edge in node.edges():
            target_module = module_of.get(edge.dst)
            if target_module is None or target_module in allowed:
                continue
            report.add("error", "module.undeclared-import", node.id,
                       f"cites '{edge.dst}' from module '{target_module}', which "
                       f"module '{node.module}' does not import",
                       node.source_path)


def check_verification_claims(graph: Graph, report: Report) -> None:
    """``status: verified`` is a claim about a machine, so it needs a machine.

    This is the check that keeps the project honest. Without it, 'verified'
    degrades into 'someone felt good about it'.
    """
    for node in graph:
        if node.status == "verified" and not node.formalization:
            report.add("error", "status.unbacked", node.id,
                       "status is 'verified' but no formalization is linked; a node is "
                       "verified only when a proof assistant checked it",
                       node.source_path)
        if node.status == "reviewed":
            reviewers = node.provenance.get("reviewed_by") or []
            if len(reviewers) < 2:
                report.add("warning", "status.thin-review", node.id,
                           f"status is 'reviewed' but {len(reviewers)} reviewer(s) are "
                           f"recorded; CONTRIBUTING.md asks for two",
                           node.source_path)


def check_provenance(graph: Graph, report: Report) -> None:
    """LLM assistance must be disclosed. Undisclosed machine text is the single
    fastest way for a project like this to lose the trust it needs."""
    for node in graph:
        if node.is_theorem and not node.provenance.get("source"):
            report.add("warning", "provenance.no-source", node.id,
                       "no provenance.source; say where the proof comes from "
                       "(textbook, paper, or 'original')",
                       node.source_path)


def check_orphans(graph: Graph, report: Report) -> None:
    """Informational: nodes nothing builds on. Fine at the frontier, suspicious in bulk."""
    depended_on = {e.dst for e in graph.edges()}
    for node in graph:
        if node.kind in ("axiom", "background", "definition") and node.id not in depended_on:
            report.add("warning", "graph.unused-assumption", node.id,
                       f"nothing in the graph uses this {node.kind}; either a proof is "
                       f"missing a citation or the assumption is not needed",
                       node.source_path)


CHECKS = (
    check_duplicate_ids,
    check_schema,
    check_references_resolve,
    check_step_numbering,
    check_step_back_references,
    check_step_identity,
    check_hypotheses,
    check_kind_obligations,
    check_acyclic,
    check_verification_claims,
    check_provenance,
    check_orphans,
)


def validate(root: Path | None = None) -> tuple[Graph, Report]:
    graph, load_errors = load_graph(root)
    report = Report()
    for message in load_errors:
        report.add("error", "load.failed", None, message)
    for check in CHECKS:
        check(graph, report)
    check_module_imports(graph, report, root)
    return graph, report
