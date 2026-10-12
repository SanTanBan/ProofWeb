"""Command line entry point.  ``python -m proofweb <command>``

    validate    check every machine-checkable invariant (this is what CI runs)
    stats       counts, depths, and how much of the graph is machine-backed
    why         what a node rests on, and at which step of which proof
    uses        every proof step in the graph that invokes a given node
    extract     mechanically build a graph from a Metamath database (no AI)
    import-lean mechanically import a Lean corpus laid out by Prove2Me (no AI)
    audit       check an imported corpus against what its makers published
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
from .metamath import nodes_to_json
from .model import Graph
from .render import explain, summarise, to_dot, to_json, to_mermaid
from .validate import validate


def _read_extracted(path: Path):
    """Load an extracted-graph document, gzipped or not."""
    from .metamath import nodes_from_json
    if path.suffix == ".gz":
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = _json.load(fh)
    else:
        data = _json.loads(path.read_text(encoding="utf-8"))
    return nodes_from_json(data), data.get("meta")


def _write_json(payload: dict, out: Path, *, compact: bool) -> None:
    """Write the document, gzipping when the name says so.

    A 30,000-node corpus is ~60 MB pretty-printed; indentation is a luxury that
    stops being one somewhere around a thousand nodes.
    """
    kw = dict(ensure_ascii=False)
    text = (_json.dumps(payload, separators=(",", ":"), **kw) if compact
            else _json.dumps(payload, indent=1, **kw))
    if out.suffix == ".gz":
        import gzip
        with gzip.open(out, "wt", encoding="utf-8") as fh:
            fh.write(text + chr(10))
    else:
        out.write_text(text + chr(10), encoding="utf-8")


def _root(args: argparse.Namespace) -> Path | None:
    return Path(args.graph).resolve() if args.graph else None


def _load(args: argparse.Namespace):
    """The graph the user pointed at: extracted JSON, or the YAML tree.

    Extracted graphs skip the YAML validators on purpose: their invariants
    were enforced by the proof verifier at extraction time, which is a
    stronger guarantee than the schema could add after the fact.
    """
    if getattr(args, "json", None):
        nodes, meta = _read_extracted(Path(args.json))
        return Graph(nodes, meta=meta)
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
    print(explain(graph, args.node, limit=args.limit))
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
    shown = 0
    limit = getattr(args, "limit", None) or 10 ** 9
    for node in sorted(graph, key=lambda n: n.id):
        for step in node.steps:
            if args.node in step.node_refs():
                hits += 1
                if shown < limit:
                    shown += 1
                    where = f"#{step.sid}" if step.sid else f"step {step.n}"
                    print(f"{node.id:<40} {where:<12} {step.claim[:90]}")
    if hits > shown:
        print(f"... and {hits - shown} more (raise --limit to see them)")

    print(f"\n{args.node} — {target.title}")
    print(f"invoked at {hits} step(s) across the graph")
    users = sorted(graph.descendants(args.node, ('proof',)))
    if users:
        print(f"transitively load-bearing for {len(users)} node(s)")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    from .metamath import extract_file

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
        title = f"ProofWeb — {Path(args.database).name}"
        Path(args.html).write_text(to_html(graph, title=title), encoding="utf-8")
        print(f"wrote {args.html}", file=sys.stderr)
    return 0


def cmd_import_lean(args: argparse.Namespace) -> int:
    """Import a Lean corpus laid out by Prove2Me. No Lean toolchain required.

    What comes out is honest about how it was made: citation edges from the
    import discipline, step attribution from the text, and the upstream kernel
    check recorded as somebody else's, not ours.
    """
    import time

    if args.style == "lake":
        return _import_lake(args)

    from .leanp2m import extract_dir

    started = time.perf_counter()
    corpus, nodes, meta = extract_dir(
        args.directory, limit=args.limit, usage_lines=not args.no_usage_lines,
        hit_mode=args.hit_mode, trust=args.trust, module=args.module,
        root=args.root)
    graph = Graph(nodes, meta=meta)

    n_thm = sum(1 for n in graph if n.is_theorem)
    n_def = sum(1 for n in graph if n.kind == "definition")
    n_ver = sum(1 for n in graph if n.status == "verified")
    pairs = {(e.src, e.dst) for e in graph.edges("proof")}
    unhit = sum(len(n.provenance.get("lean", {}).get("unused_imports", ()))
                for n in graph if n.is_theorem)

    say = lambda m: print(m, file=sys.stderr)
    say(f"imported {len(graph)} nodes ({n_thm} theorems, {n_def} definition "
        f"modules) from {args.directory}")
    say(f"  {len(pairs)} distinct citation pairs, "
        f"{len(graph.edges('proof'))} step-level proof edges, "
        f"{len(graph.edges('vocabulary'))} vocabulary edges")
    say(f"  {unhit} citations with no textual use in the proof script")
    say(f"  {n_ver} nodes marked verified "
        f"(derivation: {meta['derivation']}, checked upstream — not replayed here)")
    if corpus.problems:
        say(f"  {len(corpus.problems)} parse problem(s); first few:")
        for code, path, message in corpus.problems[:5]:
            say(f"    {code}: {path} — {message}")

    out = Path(args.out)
    _write_json(nodes_to_json(list(graph), module=nodes[0].module if nodes else "empty",
                              source=Path(args.directory).name, meta=meta),
                out, compact=len(graph) > 5000)
    say(f"wrote {out} in {time.perf_counter() - started:.1f}s")
    return 0


def _import_lake(args: argparse.Namespace) -> int:
    """An ordinary Lake project, read at module granularity. Claims nothing checked."""
    import time

    from .leanlake import extract_dir

    started = time.perf_counter()
    project, nodes, meta = extract_dir(args.directory, libs=args.lib or None,
                                       limit=args.limit, module=args.module)
    graph = Graph(nodes, meta=meta)
    say = lambda m: print(m, file=sys.stderr)
    holes = sum(1 for n in graph if "sorry" in n.tags)
    results = meta["main_results"]
    say(f"imported {len(graph)} modules from {args.directory} "
        f"(libraries: {', '.join(project.libs) or 'all .lean files'})")
    say(f"  {len(graph.edges('proof'))} project import edges; "
        f"{holes} module(s) contain sorry/admit")
    if results:
        say(f"  {len(results)} catalogued main results, "
            f"{sum(1 for r in results if r['declaration_found'])} located in their files")
    say("  every node is draft: module granularity, nothing checked by proofweb")
    if project.problems:
        say(f"  {len(project.problems)} problem(s); first few:")
        for code, path, message in project.problems[:5]:
            say(f"    {code}: {path} — {message}")
    out = Path(args.out)
    _write_json(nodes_to_json(list(graph), module=nodes[0].module if nodes else "empty",
                              source=meta["corpus"], meta=meta),
                out, compact=len(graph) > 5000)
    say(f"wrote {out} in {time.perf_counter() - started:.1f}s")
    return 0


#: Figures Anthropic published about their own Fermat's Last Theorem corpus.
#: Recomputing them is how this importer proves it read the same text they did:
#: two independent parsers agreeing to the unit is evidence; one parser agreeing
#: with itself is not.
UPSTREAM_FLT = {
    "theorems": 29511,
    "definitions": 1450,
    "citation_edges": 106853,
    "in_closure": 29489,
    "outside": 22,
    "uncited": 19,
    "unhit": 2890,
    "landmarks": 49,
}


def cmd_audit(args: argparse.Namespace) -> int:
    from .audit import audit

    graph = _load(args)
    proof_path = None
    if args.proof_path:
        proof_path = Path(args.proof_path).read_text(encoding="utf-8", errors="replace")

    upstream = UPSTREAM_FLT if args.compare == "flt" else {}
    report = audit(graph, root=args.root, proof_path_text=proof_path,
                   jaccard=args.jaccard, top=args.top, upstream=upstream)

    text = report.to_markdown()
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
        print(f"wrote {args.report}", file=sys.stderr)
    else:
        print(text)
    if args.out:
        Path(args.out).write_text(
            _json.dumps(report.to_dict(), indent=1, ensure_ascii=False, default=str) + chr(10),
            encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


def _focus(graph, args):
    """Narrow a large graph to something a viewer can draw.

    A layered picture of 30,000 nodes is not a picture. Two ways to ask for a
    readable one: a neighbourhood around a node, or the route from a node to the
    corpus goal.
    """
    subtitle = None
    if args.path_to_root:
        root = args.root or (graph.meta or {}).get("root")
        if not root or root not in graph:
            print(f"--path-to-root needs a root in the graph (got {root!r})",
                  file=sys.stderr)
            return graph, None
        # Edges run from a theorem to what it depends on, so the route the goal
        # takes to reach this node is a path *from* the root.
        path = graph.shortest_path(root, args.path_to_root)
        if path is None:
            print(f"{root} does not depend on {args.path_to_root}", file=sys.stderr)
            return graph, None
        subtitle = (f"shortest dependency route from {root} down to "
                    f"{args.path_to_root} — {len(path)} nodes")
        return graph.subgraph(path), subtitle
    if args.focus:
        if args.focus not in graph:
            print(f"no such node: {args.focus}", file=sys.stderr)
            return graph, None
        ids, truncated = graph.neighbourhood(
            args.focus, radius=args.radius, direction=args.direction,
            max_nodes=args.max_nodes)
        subtitle = (f"within {args.radius} hop(s) of {args.focus} "
                    f"({args.direction})" + (" — truncated" if truncated else ""))
        return graph.subgraph(ids), subtitle
    return graph, subtitle


def cmd_render(args: argparse.Namespace) -> int:
    graph = _load(args)
    graph, subtitle = _focus(graph, args)
    if args.format == "dot":
        text = to_dot(graph, include_vocabulary=not args.proof_only)
    elif args.format == "mermaid":
        text = to_mermaid(graph, include_vocabulary=not args.proof_only)
    elif args.format == "html":
        from .site import to_html
        text = to_html(graph, subtitle=subtitle)
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
        prog="proofweb",
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
    p.add_argument("--limit", type=int, default=100,
                   help="cap the transitive lists (a corpus node can rest on 29,000)")
    p.set_defaults(func=cmd_why)

    p = sub.add_parser("uses", help="every proof step that invokes a node "
                                    "(reverse step-level lookup)")
    p.add_argument("node", help="node id, e.g. ax-mp")
    p.add_argument("--json", metavar="FILE", help="read an extracted graph instead of graph/")
    p.add_argument("--limit", type=int, default=200, help="cap the number of hits shown")
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

    p = sub.add_parser("import-lean",
                       help="mechanically import a Lean corpus laid out by "
                            "Prove2Me (statements, proofs, definitions; no AI)")
    p.add_argument("directory", help="corpus root, e.g. corpora/fermats-last-theorem")
    p.add_argument("-o", "--out", required=True,
                   help="output JSON path (.json or .json.gz)")
    p.add_argument("--style", choices=["p2m", "lake"], default="p2m",
                   help="corpus layout: 'p2m' (Prove2Me: one statement and one "
                        "proof file per theorem; citation-level edges) or 'lake' "
                        "(any Lake project; module-level import edges, all draft)")
    p.add_argument("--lib", action="append", metavar="ROOT",
                   help="lake style: library root(s) to read, e.g. OAI "
                        "(default: every lean_lib in the lakefile)")
    p.add_argument("--root", default=None, metavar="ID",
                   help="the corpus's goal theorem, e.g. fermat_last_theorem")
    p.add_argument("--module", default=None, help="override the module name")
    p.add_argument("--limit", type=int, default=None,
                   help="stop after this many theorem (p2m) or module (lake) "
                        "files, for dev loops")
    p.add_argument("--no-usage-lines", action="store_true",
                   help="record statement-level citations only, without "
                        "attributing them to proof-script lines")
    p.add_argument("--hit-mode", choices=["strict", "anthropic"], default="strict",
                   help="'anthropic' reproduces the upstream docs generator's "
                        "ASCII-only matching, for comparing counts")
    p.add_argument("--trust", choices=["upstream", "none"], default="upstream",
                   help="'none' refuses to mark anything verified on the "
                        "strength of a check this tool did not run")
    p.set_defaults(func=cmd_import_lean)

    p = sub.add_parser("audit",
                       help="check an imported corpus: closure, unnamed citations, "
                            "duplicates, landmarks, and the figures its makers published")
    p.add_argument("--json", metavar="FILE", required=True,
                   help="an extracted graph, from import-lean or extract")
    p.add_argument("--root", default=None, metavar="ID",
                   help="the goal theorem (defaults to the one recorded at import)")
    p.add_argument("--proof-path", default=None, metavar="FILE",
                   help="PROOF-PATH.md, to validate the prose route against the graph")
    p.add_argument("--jaccard", type=float, default=0.9,
                   help="near-duplicate threshold on statement tokens")
    p.add_argument("--top", type=int, default=25, help="how many rows in each ranking")
    p.add_argument("--compare", choices=["none", "flt"], default="none",
                   help="'flt' compares against the figures Anthropic published "
                        "for the Fermat's Last Theorem corpus")
    p.add_argument("--report", default=None, metavar="FILE", help="write Markdown here")
    p.add_argument("--out", default=None, metavar="FILE", help="write JSON here")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("render", help="export the graph")
    p.add_argument("--json", metavar="FILE", help="read an extracted graph instead of graph/")
    p.add_argument("format", choices=["dot", "mermaid", "json", "html"],
                   help="html is a single self-contained page: open it, click a "
                        "proof step, watch the edges it created light up")
    p.add_argument("-o", "--out", help="write to a file instead of stdout")
    p.add_argument("--proof-only", action="store_true",
                   help="omit statement-context (vocabulary) edges")
    p.add_argument("--focus", default=None, metavar="ID",
                   help="draw only the neighbourhood of this node")
    p.add_argument("--radius", type=int, default=1, help="hops around --focus")
    p.add_argument("--direction", choices=["both", "up", "down"], default="both",
                   help="follow dependencies (down), dependents (up), or both")
    p.add_argument("--max-nodes", type=int, default=300,
                   help="stop expanding the neighbourhood past this many nodes")
    p.add_argument("--path-to-root", default=None, metavar="ID",
                   help="draw the shortest dependency route from this node to the goal")
    p.add_argument("--root", default=None, metavar="ID",
                   help="the goal theorem for --path-to-root "
                        "(defaults to the one recorded at import)")
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
