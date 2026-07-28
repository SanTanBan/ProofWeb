"""Core data model for a proof graph.

The central design decision lives here: a node never declares its dependencies.
It declares a proof, each of whose steps carries its own justifications, and the
edges are *derived* from those justifications. A dependency that is not used by
some step of some proof cannot exist, and a step that leans on a result without
citing it produces a node whose stated proof does not typecheck against its own
edge set. That is what makes the graph an assertion about the mathematics rather
than a hand-maintained index alongside it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Literal

NodeKind = Literal["axiom", "definition", "background", "theorem"]
EdgeKind = Literal["proof", "vocabulary"]

#: Justification tokens that refer to something local to the proof and therefore
#: create no edge: the theorem's own hypotheses, and earlier steps.
_LOCAL_HYP = re.compile(r"^hyp(?::(?P<name>[A-Za-z0-9_.-]+))?$")
_LOCAL_STEP = re.compile(r"^s(?P<n>\d+)$")
_LOCAL_OTHER = frozenset({"assumption"})


def classify_token(token: str) -> tuple[str, str | None]:
    """Classify a `by:` entry.

    Returns ``(kind, payload)`` where kind is one of ``"hyp"``, ``"step"``,
    ``"assumption"``, or ``"node"``. Only ``"node"`` tokens become edges.
    """
    m = _LOCAL_HYP.match(token)
    if m:
        return "hyp", m.group("name")
    m = _LOCAL_STEP.match(token)
    if m:
        return "step", m.group("n")
    if token in _LOCAL_OTHER:
        return "assumption", None
    return "node", token


@dataclass(frozen=True)
class Step:
    n: int
    claim: str
    by: tuple[str, ...]
    note: str | None = None

    def node_refs(self) -> list[str]:
        return [t for t in self.by if classify_token(t)[0] == "node"]

    def step_refs(self) -> list[int]:
        return [int(p) for k, p in map(classify_token, self.by) if k == "step"]

    def hyp_refs(self) -> list[str | None]:
        return [p for k, p in map(classify_token, self.by) if k == "hyp"]


@dataclass(frozen=True)
class Edge:
    """A dependency, always traceable to the line of proof that created it."""

    src: str
    dst: str
    kind: EdgeKind
    step: int | None = None

    def __str__(self) -> str:
        where = f" (step {self.step})" if self.step is not None else ""
        return f"{self.src} -> {self.dst} [{self.kind}]{where}"


@dataclass
class Node:
    id: str
    kind: NodeKind
    title: str
    statement_natural: str
    statement_latex: str | None = None
    context: tuple[str, ...] = ()
    strategy: str | None = None
    hypotheses: tuple[str, ...] = ()
    steps: tuple[Step, ...] = ()
    status: str = "draft"
    formalization: dict[str, str] = field(default_factory=dict)
    provenance: dict[str, object] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    module: str = ""
    source_path: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def is_theorem(self) -> bool:
        return self.kind == "theorem"

    @property
    def hypothesis_names(self) -> list[str]:
        """Hypotheses are written ``'name: text'``; the name is what steps cite."""
        names = []
        for h in self.hypotheses:
            names.append(h.split(":", 1)[0].strip() if ":" in h else h.strip())
        return names

    def edges(self) -> list[Edge]:
        """Every edge this node induces, derived from its proof and its statement."""
        out: list[Edge] = []
        for dep in self.context:
            out.append(Edge(self.id, dep, "vocabulary", None))
        for step in self.steps:
            for dep in step.node_refs():
                out.append(Edge(self.id, dep, "proof", step.n))
        return out

    def proof_deps(self) -> set[str]:
        return {e.dst for e in self.edges() if e.kind == "proof"}


class Graph:
    """A loaded, in-memory proof graph. Construction does no validation."""

    def __init__(self, nodes: Iterable[Node]) -> None:
        self.nodes: dict[str, Node] = {}
        self.duplicate_ids: list[tuple[str, str, str]] = []
        for node in nodes:
            if node.id in self.nodes:
                self.duplicate_ids.append(
                    (node.id, self.nodes[node.id].source_path, node.source_path)
                )
                continue
            self.nodes[node.id] = node

    def __len__(self) -> int:
        return len(self.nodes)

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes.values())

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.nodes

    def get(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def edges(self, kind: EdgeKind | None = None) -> list[Edge]:
        out = [e for n in self for e in n.edges()]
        return [e for e in out if kind is None or e.kind == kind]

    # -- graph queries -----------------------------------------------------

    def adjacency(self, kinds: tuple[EdgeKind, ...] = ("proof", "vocabulary")) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = {n: set() for n in self.nodes}
        for e in self.edges():
            if e.kind in kinds and e.src in adj:
                adj[e.src].add(e.dst)
        return adj

    def cycles(self, kinds: tuple[EdgeKind, ...] = ("proof", "vocabulary")) -> list[list[str]]:
        """All elementary cycles reachable by DFS, as node-id paths.

        A proof graph must be acyclic: a cycle means some result is, transitively,
        used in its own proof. Iterative DFS with an explicit stack so that deep
        graphs cannot blow the recursion limit.
        """
        adj = self.adjacency(kinds)
        found: list[list[str]] = []
        seen_signatures: set[frozenset[str]] = set()
        colour: dict[str, int] = dict.fromkeys(adj, 0)  # 0 white, 1 grey, 2 black

        for root in sorted(adj):
            if colour[root] != 0:
                continue
            stack: list[tuple[str, Iterator[str]]] = [(root, iter(sorted(adj[root])))]
            path = [root]
            colour[root] = 1
            while stack:
                node, children = stack[-1]
                advanced = False
                for child in children:
                    if child not in colour:
                        continue  # dangling reference; reported separately
                    if colour[child] == 1:
                        cycle = path[path.index(child):] + [child]
                        sig = frozenset(cycle)
                        if sig not in seen_signatures:
                            seen_signatures.add(sig)
                            found.append(cycle)
                    elif colour[child] == 0:
                        colour[child] = 1
                        path.append(child)
                        stack.append((child, iter(sorted(adj[child]))))
                        advanced = True
                        break
                if not advanced:
                    colour[node] = 2
                    stack.pop()
                    path.pop()
        return found

    def ancestors(self, node_id: str, kinds: tuple[EdgeKind, ...] = ("proof",)) -> set[str]:
        """Everything ``node_id`` rests on, transitively. Cycle-safe."""
        adj = self.adjacency(kinds)
        seen: set[str] = set()
        stack = list(adj.get(node_id, ()))
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(adj.get(cur, ()))
        return seen

    def descendants(self, node_id: str, kinds: tuple[EdgeKind, ...] = ("proof",)) -> set[str]:
        """Everything that rests on ``node_id``, transitively."""
        radj: dict[str, set[str]] = {n: set() for n in self.nodes}
        for e in self.edges():
            if e.kind in kinds and e.dst in radj:
                radj[e.dst].add(e.src)
        seen: set[str] = set()
        stack = list(radj.get(node_id, ()))
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(radj.get(cur, ()))
        return seen

    def depth(self, node_id: str, kinds: tuple[EdgeKind, ...] = ("proof",)) -> int:
        """Longest chain of proof steps back to something unproved.

        Returns -1 if the node sits on a cycle, since depth is then meaningless.
        """
        adj = self.adjacency(kinds)
        memo: dict[str, int] = {}
        on_stack: set[str] = set()

        def go(n: str) -> int:
            if n in memo:
                return memo[n]
            if n in on_stack:
                return -1
            deps = [d for d in adj.get(n, ()) if d in self.nodes]
            if not deps:
                memo[n] = 0
                return 0
            on_stack.add(n)
            sub = [go(d) for d in deps]
            on_stack.discard(n)
            memo[n] = -1 if -1 in sub else 1 + max(sub)
            return memo[n]

        return go(node_id)

    def layers(self, kinds: tuple[EdgeKind, ...] = ("proof",)) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for n in self.nodes:
            out.setdefault(self.depth(n, kinds), []).append(n)
        for v in out.values():
            v.sort()
        return dict(sorted(out.items()))

    def roots(self) -> list[str]:
        """Nodes nothing else depends on — the current frontier."""
        depended_on = {e.dst for e in self.edges()}
        return sorted(n for n in self.nodes if n not in depended_on)

    def leaves(self) -> list[str]:
        """Nodes that depend on nothing — axioms, definitions, background."""
        return sorted(n for n in self.nodes if not self.nodes[n].edges())
