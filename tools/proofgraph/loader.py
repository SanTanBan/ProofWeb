"""Read YAML node files off disk into a :class:`~proofgraph.model.Graph`."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .model import Graph, Node, Step

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_DIR = REPO_ROOT / "graph"
SCHEMA_PATH = REPO_ROOT / "schema" / "node.schema.json"


class LoadError(Exception):
    """A file could not be parsed at all. Distinct from a validation failure."""


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    """Repo-relative when we can, absolute when we cannot.

    ``--graph`` may point anywhere — a scratch directory, a contributor's fork
    checked out elsewhere — so this must never raise.
    """
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _node_from_dict(data: dict, module: str, path: Path) -> Node:
    statement = data.get("statement") or {}
    proof = data.get("proof") or {}

    steps = tuple(
        Step(
            n=int(s["n"]),
            claim=str(s["claim"]),
            by=tuple(str(b) for b in s.get("by", ())),
            note=s.get("note"),
            sid=s.get("id"),
        )
        for s in proof.get("steps", ())
    )

    return Node(
        id=str(data["id"]),
        kind=data["kind"],
        title=str(data.get("title", "")),
        statement_natural=str(statement.get("natural", "")),
        statement_latex=statement.get("latex"),
        context=tuple(str(c) for c in statement.get("context", ())),
        strategy=proof.get("strategy"),
        hypotheses=tuple(str(h) for h in proof.get("hypotheses", ())),
        steps=steps,
        status=data.get("status", "draft"),
        formalization=dict(data.get("formalization") or {}),
        provenance=dict(data.get("provenance") or {}),
        tags=tuple(data.get("tags") or ()),
        module=module,
        source_path=_display_path(path),
        raw=data,
    )


NODE_SUFFIXES = (".yml", ".yaml")


def iter_node_files(root: Path | None = None) -> list[tuple[Path, str]]:
    """Every node file under ``graph/``, paired with its module id.

    A module is any directory under ``graph/`` containing a ``manifest.yml``.

    Each file is assigned to its *nearest* enclosing manifest. Without that, a
    module nested inside another module's tree would have every one of its nodes
    loaded twice, and the duplicate-id check would report a legitimate layout as
    broken. Both suffixes are accepted so a contributor who writes ``.yaml`` gets
    a node rather than silence.
    """
    root = root or GRAPH_DIR
    out: list[tuple[Path, str]] = []
    if not root.exists():
        return out

    modules: dict[Path, str] = {}
    for manifest in sorted(root.rglob("manifest.yml")):
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise LoadError(f"{manifest}: {exc}") from exc
        modules[manifest.parent] = data.get("id", manifest.parent.name)

    def nearest_module(path: Path) -> str | None:
        """The module whose directory is the deepest ancestor of ``path``."""
        best: tuple[int, str] | None = None
        for module_dir, module_id in modules.items():
            if module_dir == path.parent or module_dir in path.parents:
                depth = len(module_dir.parts)
                if best is None or depth > best[0]:
                    best = (depth, module_id)
        return best[1] if best else None

    seen: set[Path] = set()
    for module_dir in sorted(modules):
        for suffix in NODE_SUFFIXES:
            for path in sorted(module_dir.rglob(f"*{suffix}")):
                if path.stem == "manifest" or path in seen:
                    continue
                module_id = nearest_module(path)
                if module_id is None:  # pragma: no cover - unreachable by construction
                    continue
                seen.add(path)
                out.append((path, module_id))
    return sorted(out, key=lambda pair: str(pair[0]))


def load_graph(root: Path | None = None) -> tuple[Graph, list[str]]:
    """Load every node. Returns the graph plus a list of hard parse errors."""
    nodes: list[Node] = []
    errors: list[str] = []
    for path, module_id in iter_node_files(root):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{path}: not valid YAML: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{path}: expected a YAML mapping at the top level")
            continue
        if "id" not in data or "kind" not in data:
            errors.append(f"{path}: missing required key 'id' or 'kind'")
            continue
        try:
            nodes.append(_node_from_dict(data, module_id, path))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{path}: malformed node: {exc}")
    return Graph(nodes), errors


def load_manifests(root: Path | None = None) -> dict[str, dict]:
    root = root or GRAPH_DIR
    out: dict[str, dict] = {}
    if not root.exists():
        return out
    for manifest in sorted(root.rglob("manifest.yml")):
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        out[data.get("id", manifest.parent.name)] = data
    return out
