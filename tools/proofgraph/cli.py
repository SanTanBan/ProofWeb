"""Command line entry point.  ``python -m proofgraph <command>``

    validate    check every machine-checkable invariant (this is what CI runs)
    stats       counts, depths, and how much of the graph is machine-backed
    why         what a node rests on, and at which step of which proof
    render      export to dot / mermaid / json
    list        one line per node
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import GRAPH_DIR
from .render import explain, summarise, to_dot, to_json, to_mermaid
from .validate import validate


def _root(args: argparse.Namespace) -> Path | None:
    return Path(args.graph).resolve() if args.graph else None


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
    graph, _ = validate(_root(args))
    print(summarise(graph))
    return 0


def cmd_why(args: argparse.Namespace) -> int:
    graph, _ = validate(_root(args))
    print(explain(graph, args.node))
    return 0 if args.node in graph else 1


def cmd_render(args: argparse.Namespace) -> int:
    graph, _ = validate(_root(args))
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
    graph, _ = validate(_root(args))
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
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("why", help="what a node rests on, and where exactly")
    p.add_argument("node", help="node id, e.g. T6")
    p.set_defaults(func=cmd_why)

    p = sub.add_parser("render", help="export the graph")
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
