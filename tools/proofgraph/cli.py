"""Command line entry point.  ``python -m proofgraph <command>``

    validate    check every machine-checkable invariant (this is what CI runs)
    stats       counts, depths, and how much of the graph is machine-backed
    why         what a node rests on, and at which step of which proof
    uses        every proof step in the graph that invokes a given node
    extract     mechanically build a graph from a Metamath database (no AI)
    render      export to dot / mermaid / json / html
    list        one line per node

Most commands accept either the YAML graph under ``graph/`` (default) or an
extracted-graph JSON produced by ``extract`` (``--json FILE``).
"""

from __future__ import annotations

import argparse
import json as _json
import sys
from pathlib import Path

from .loader import GRAPH_DIR
from .render import explain, summarise, to_dot, to_json, to_mermaid
from .validate import validate


def _root(args: argparse.Namespace) -> Path | None:
    return Path(args.graph).resolve() if args.graph else None


def _load(args: argparse.Namespace):
    """The graph the user pointed at: extracted JSON, or the YAML tree.

    Extracted graphs skip the YAML validators on purpose: their invariants
    were enforced by the proof verifier at extraction time, which is a
    stronger guarantee than the schema could add after the fact.
    """
    if getattr(args, "json", None):
        from .metamath import nodes_from_json
        from .model import Graph
        data = _json.loads(Path(args.json).read_text(encoding="utf-8"))
        return Graph(nodes_from_json(data))
    graph, _ = validate(_root(args))
    return graph


def cmd_validate(args: argparse.Namespace) -> int:
    graph, report = validate(_root(args))

    for finding in report.findings:
        print(finding, file=sys.stderr if finding.severity == "error" else sys.stdout)

    n_err, n_warn = len(report.errors), len(report.warnings)
    print()
    if not len(report):
        print(f"ok — {len(graph)} nodes, {len(graph.edges('proof'))} proof edges, "
              f"no findings")
    else:
        print(f"{len(graph)} nodes, {len(graph.edges('proof'))} proof edges — "
              f"{n_err} error(s), {n_warn} warning(s)")

    if report.ok(strict=args.strict):
        return 0
    return 1


def cmd_stats(args: argparse.Namespace) -> int:
    graph = _load(args)
    print(summarise(graph))
    return 0


def cmd_why(args: argparse.Namespace) -> int:
    graph = _load(args)
    print(explain(graph, args.node))
    return 0 if args.node in graph else 1


def cmd_uses(args: argparse.Namespace) -> int:
    """Reverse step-level lookup: every proof step that invokes a node.

    This is the query the prior-art survey found nobody serving — search
    engines index what a theorem *says*, never where it is *used*. Here it is
    a five-line scan, because every edge already remembers the step that
    created it.
    """
    graph = _load(args)
    target = graph.get(args.node)
    if target is None:
        print(f"No such node: {args.node}", file=sys.stderr)
        return 1

    hits = 0
    for node in sorted(graph, key=lambda n: n.id):
        for step in node.steps:
            if args.node in step.node_refs():
                hits += 1
                where = f"#{step.sid}" if step.sid else f"step {step.n}"
                print(f"{node.id:<12} {where:<20} {step.claim}")

    print(f"\n{args.node} — {target.title}")
    print(f"invoked at {hits} step(s) across the graph")
    users = sorted(graph.descendants(args.node, ('proof',)))
    if users:
        print(f"transitively load-bearing for {len(users)} node(s)")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    from .metamath import extract_file, nodes_to_json
    from .model import Graph

    db, nodes = extract_file(args.database,
                             stop_after_p=args.limit, stop_at=args.stop_at)
    graph = Graph(nodes)

    n_thm = sum(1 for n in graph if n.is_theorem)
    n_ver = sum(1 for n in graph if n.status == "verified")
    print(f"extracted {len(graph)} nodes ({n_thm} theorems, "
          f"{n_ver} kernel-checked) from {args.database}", file=sys.stderr)
    if db.failures:
        print(f"NOT verified ({len(db.failures)}): "
              f"{', '.join(sorted(db.failures))}", file=sys.stderr)

    # The most-invoked assertions — the working vocabulary of the corpus.
    from collections import Counter
    invoked = Counter(dep for n in graph for s in n.steps for dep in s.node_refs())
    if invoked:
        top = ", ".join(f"{lbl} ({k})" for lbl, k in invoked.most_common(8))
        print(f"most invoked: {top}", file=sys.stderr)

    payload = nodes_to_json(list(graph), module=nodes[0].module if nodes else "empty",
                            source=Path(args.database).name)
    out = Path(args.out)
    out.write_text(_json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {out}", file=sys.stderr)

    if args.html:
        from .site import to_html
        title = f"ProofGraph — {Path(args.database).name}"
        Path(args.html).write_text(to_html(graph, title=title), encoding="utf-8")
        print(f"wrote {args.html}", file=sys.stderr)
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    graph = _load(args)
    if args.format == "dot":
        text = to_dot(graph, include_vocabulary=not args.proof_only)
    elif args.format == "mermaid":
        text = to_mermaid(graph, include_vocabulary=not args.proof_only)
    elif args.format == "html":
        from .site import to_html
        text = to_html(graph)
    else:
        text = to_json(graph)

    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    graph = _load(args)
    for node in sorted(graph, key=lambda n: (n.module, n.kind, n.id)):
        mark = "*" if node.formalization else " "
        print(f"{mark} {node.id:<8} {node.kind:<11} {node.title}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proofgraph",
        description="A knowledge graph of mathematics whose edges are derived from proofs.",
    )
    parser.add_argument("--graph", metavar="DIR", default=None,
                        help=f"graph directory (default: {GRAPH_DIR})")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check every machine-checkable invariant")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("stats", help="counts, depth, and formalization coverage")
    p.add_argument("--json", metavar="FILE", help="read an extracted graph instead of graph/")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("why", help="what a node rests on, and where exactly")
    p.add_argument("node", help="node id, e.g. T6 or mp2")
    p.add_argument("--json", metavar="FILE", help="read an extracted graph instead of graph/")
    p.set_defaults(func=cmd_why)

    p = sub.add_parser("uses", help="every proof step that invokes a node "
                                    "(reverse step-level lookup)")
    p.add_argument("node", help="node id, e.g. ax-mp")
    p.add_argument("--json", metavar="FILE", help="read an extracted graph instead of graph/")
    p.set_defaults(func=cmd_uses)

    p = sub.add_parser("extract",
                       help="mechanically extract a verified graph from a "
                            "Metamath .mm database (no AI involved)")
    p.add_argument("database", help="path to a .mm file, e.g. corpora/set.mm")
    p.add_argument("-o", "--out", required=True, help="output JSON path")
    p.add_argument("--limit", type=int, default=None,
                   help="stop after this many $p statements")
    p.add_argument("--stop-at", default=None, metavar="LABEL",
                   help="stop after this theorem label (inclusive)")
    p.add_argument("--html", default=None, metavar="FILE",
                   help="also write the interactive viewer for the extract")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("render", help="export the graph")
    p.add_argument("--json", metavar="FILE", help="read an extracted graph instead of graph/")
    p.add_argument("format", choices=["dot", "mermaid", "json", "html"],
                   help="html is a single self-contained page: open it, click a "
                        "proof step, watch the edges it created light up")
    p.add_argument("-o", "--out", help="write to a file instead of stdout")
    p.add_argument("--proof-only", action="store_true",
                   help="omit statement-context (vocabulary) edges")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("list", help="one line per node")
    p.set_defaults(func=cmd_list)

    return parser


def _force_utf8() -> None:
    """Mathematics is not ASCII, and the default Windows console encoding is cp1252.

    Without this, ``why T6`` dies on the '·' in a group product. Contributors on
    Windows should not have to discover ``chcp 65001`` to read their own graph.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # pragma: no cover - exotic streams
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
