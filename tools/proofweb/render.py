"""Export the graph to formats other tools can read.

Every exporter preserves the one thing that makes this graph different from an
import graph: each proof edge remembers *which step of which proof* created it.
An exporter that drops the step number has thrown away the whole point.
"""

from __future__ import annotations

import json
from typing import Iterable

from .model import Edge, Graph, Node

_SHAPES = {
    "axiom": ("box", "#b45309"),
    "background": ("box", "#6b7280"),
    "definition": ("folder", "#0f766e"),
    "theorem": ("ellipse", "#1d4ed8"),
}


def _label(node: Node) -> str:
    return f"{node.id}\\n{node.title}"


def to_dot(graph: Graph, include_vocabulary: bool = True) -> str:
    """Graphviz. ``dot -Tsvg graph.dot -o graph.svg``."""
    lines = [
        "digraph proofweb {",
        "  rankdir=BT;",
        '  node [fontname="Helvetica", fontsize=10, style=filled, fillcolor="#f8fafc"];',
        '  edge [fontname="Helvetica", fontsize=8, color="#94a3b8"];',
        "",
    ]
    for node in sorted(graph, key=lambda n: n.id):
        shape, colour = _SHAPES.get(node.kind, ("ellipse", "#000000"))
        lines.append(
            f'  "{node.id}" [label="{_label(node)}", shape={shape}, color="{colour}"];'
        )
    lines.append("")
    for edge in sorted(graph.edges(), key=lambda e: (e.src, e.dst, e.step or 0)):
        if edge.kind == "vocabulary":
            if not include_vocabulary:
                continue
            lines.append(
                f'  "{edge.src}" -> "{edge.dst}" [style=dotted, color="#cbd5e1"];'
            )
        else:
            lines.append(
                f'  "{edge.src}" -> "{edge.dst}" [label="step {edge.step}"];'
            )
    lines.append("}")
    return "\n".join(lines)


def to_mermaid(graph: Graph, include_vocabulary: bool = False) -> str:
    """Mermaid, for pasting straight into a README or an issue.

    Vocabulary edges are off by default here: Mermaid diagrams get unreadable
    fast, and the proof edges are the interesting ones.
    """
    lines = ["graph BT"]
    for node in sorted(graph, key=lambda n: n.id):
        text = f"{node.id}: {node.title}".replace('"', "'")
        if node.kind == "theorem":
            lines.append(f'  {node.id}["{text}"]')
        elif node.kind == "definition":
            lines.append(f'  {node.id}[/"{text}"/]')
        else:
            lines.append(f'  {node.id}("{text}")')
    for edge in sorted(graph.edges(), key=lambda e: (e.src, e.dst, e.step or 0)):
        if edge.kind == "vocabulary":
            if include_vocabulary:
                lines.append(f"  {edge.src} -.-> {edge.dst}")
        else:
            lines.append(f"  {edge.src} -- step {edge.step} --> {edge.dst}")
    return "\n".join(lines)


def to_json(graph: Graph) -> str:
    """A plain node/edge document. The interchange format for anything else —
    a web viewer, a notebook, a machine-learning pipeline."""
    payload = {
        "version": 1,
        "nodes": [
            {
                "id": n.id,
                "kind": n.kind,
                "title": n.title,
                "statement": n.statement_natural,
                "latex": n.statement_latex,
                "module": n.module,
                "status": n.status,
                "formalization": n.formalization,
                "depth": graph.depth(n.id),
                "steps": len(n.steps),
                "source": n.source_path,
                "tags": list(n.tags),
            }
            for n in sorted(graph, key=lambda n: n.id)
        ],
        "edges": [
            {"source": e.src, "target": e.dst, "kind": e.kind, "step": e.step}
            for e in sorted(graph.edges(), key=lambda e: (e.src, e.dst, e.step or 0))
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def explain(graph: Graph, node_id: str) -> str:
    """Human-readable answer to 'what does this rest on, and where exactly?'.

    This is the query the whole schema exists to make possible. A dependency
    list can tell you T6 uses T4. This tells you T6 uses T4 *at step 12*, and
    lets you read the step.
    """
    node = graph.get(node_id)
    if node is None:
        return f"No such node: {node_id}"

    out: list[str] = [f"{node.id} — {node.title}", f"  {node.statement_natural}", ""]

    if node.formalization:
        pairs = ", ".join(f"{k}: {v}" for k, v in sorted(node.formalization.items()))
        out.append(f"  formalized as → {pairs}")
        out.append("")

    if not node.steps:
        out.append(f"  This is a{'n' if node.kind[0] in 'aeiou' else ''} {node.kind}. "
                   f"It is assumed, not proved.")
    else:
        if node.strategy:
            out.append("  Strategy: " + " ".join(node.strategy.split()))
            out.append("")
        out.append("  Proof:")
        for step in node.steps:
            cites = []
            for token in step.by:
                target = graph.get(token)
                cites.append(f"{token} ({target.title})" if target else token)
            addr = f"  [{node.id}#{step.sid}]" if step.sid else ""
            out.append(f"    {step.n:>3}. {step.claim}{addr}")
            out.append(f"         by {', '.join(cites)}")
            if step.note:
                out.append(f"         note: {step.note}")

    deps = sorted(graph.ancestors(node_id, ("proof",)))
    if deps:
        out.append("")
        out.append(f"  Rests on {len(deps)} node(s), transitively:")
        for dep in deps:
            target = graph.get(dep)
            direct = [e for e in node.edges() if e.dst == dep and e.kind == "proof"]
            if direct:
                # Stable addresses, because these are what anything outside the
                # proof should cite. Ordinals are shown only as a reading aid.
                where = " — used at " + ", ".join(
                    (f"#{e.step_id}" if e.step_id else f"step {e.step}") for e in direct)
            else:
                where = " — indirectly"
            out.append(f"    {dep:<6} {target.title if target else '?'}{where}")

    users = sorted(graph.descendants(node_id, ("proof",)))
    if users:
        out.append("")
        out.append(f"  Used by {len(users)} node(s): " + ", ".join(users))

    return "\n".join(out)


def summarise(graph: Graph) -> str:
    """A few numbers, chosen so that they get worse when the graph gets worse."""
    kinds: dict[str, int] = {}
    for node in graph:
        kinds[node.kind] = kinds.get(node.kind, 0) + 1

    proof_edges = graph.edges("proof")
    vocab_edges = graph.edges("vocabulary")
    theorems = [n for n in graph if n.is_theorem]
    steps = sum(len(n.steps) for n in theorems)

    out = [
        f"nodes            {len(graph)}",
        "  " + "  ".join(f"{k} {v}" for k, v in sorted(kinds.items())),
        f"edges            {len(proof_edges)} proof, {len(vocab_edges)} vocabulary",
        f"proof steps      {steps}",
    ]
    if theorems:
        out.append(f"citations/step   {len(proof_edges) / max(steps, 1):.2f}")
    verified = sum(1 for n in graph if n.status == "verified")
    reviewed = sum(1 for n in graph if n.status in ("reviewed", "verified"))
    linked = sum(1 for n in graph if n.formalization)
    out.append(f"formalized       {linked}/{len(graph)} nodes link to a proof assistant")

    # Printed unconditionally, and deliberately hard to look away from: the
    # project's first kill criterion is that this number is still zero in six
    # months. A statistic you have to go looking for is a statistic nobody reads.
    out.append(f"reviewed         {reviewed}/{len(graph)}   verified  {verified}/{len(graph)}")
    if reviewed == 0:
        out.append("                 ^ nothing here has been checked by a second person yet")

    layers = graph.layers(("proof",))
    out.append("")
    out.append("depth (longest chain back to an assumption):")
    for depth, ids in layers.items():
        label = "assumptions" if depth == 0 else f"depth {depth}"
        out.append(f"  {label:<14} {', '.join(ids)}")

    frontier = [n for n in graph.roots() if graph.get(n) and graph.get(n).is_theorem]
    if frontier:
        out.append("")
        out.append("frontier (theorems nothing yet builds on): " + ", ".join(frontier))
    return "\n".join(out)
