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

#: ``module`` is a source file of a formal library imported at file granularity.
#: Its single ``imports`` step is an upper bound on dependence, never a proof.
NodeKind = Literal["axiom", "definition", "background", "theorem", "module"]
EdgeKind = Literal["proof", "vocabulary"]

#: Justification tokens that refer to something local to the proof and therefore
#: create no edge: the theorem's own hypotheses, and earlier steps.
_LOCAL_HYP = re.compile(r"^hyp(?::(?P<name>[A-Za-z0-9_.-]+))?$")
_LOCAL_STEP = re.compile(r"^s(?P<n>\d+)$")
_LOCAL_STEP_ID = re.compile(r"^s:(?P<sid>[a-z0-9][a-z0-9-]*)$")
_LOCAL_OTHER = frozenset({"assumption"})


def classify_token(token: str) -> tuple[str, str | None]:
    """Classify a `by:` entry.

    Returns ``(kind, payload)`` where kind is one of ``"hyp"``, ``"step"``,
    ``"stepid"``, ``"assumption"``, or ``"node"``. Only ``"node"`` tokens become
    edges.

    ``s3`` and ``s:collapse-inner`` both name an earlier step of the same proof.
    The difference is what survives an edit: see :class:`Step`.
    """
    m = _LOCAL_HYP.match(token)
    if m:
        return "hyp", m.group("name")
    m = _LOCAL_STEP_ID.match(token)
    if m:
        return "stepid", m.group("sid")
    m = _LOCAL_STEP.match(token)
    if m:
        return "step", m.group("n")
    if token in _LOCAL_OTHER:
        return "assumption", None
    return "node", token


@dataclass(frozen=True)
class Step:
    """One line of a proof.

    Two names, doing different jobs:

    ``n``
        The presentation ordinal, contiguous from 1. It says where the step sits
        in the reading order and **it is not stable** — inserting a step renumbers
        everything after it.

    ``sid``
        An immutable identifier, assigned once and never reused, even if the step
        is deleted. This is what an edge from outside the proof must point at.

    The distinction is the whole reason the project can claim to address stable
    sub-proof identity rather than merely naming it as an open problem. An edge
    addressed as "step 12 of T6" breaks the first time somebody inserts a step at
    position 3; an edge addressed as ``T6#collapse-outer`` does not.
    """

    n: int
    claim: str
    by: tuple[str, ...]
    note: str | None = None
    sid: str | None = None

    @property
    def ref(self) -> str:
        """How to address this step from outside: stable if it can be, else ordinal."""
        return f"#{self.sid}" if self.sid else f"step {self.n}"

    def node_refs(self) -> list[str]:
        return [t for t in self.by if classify_token(t)[0] == "node"]

    def step_refs(self) -> list[int]:
        return [int(p) for k, p in map(classify_token, self.by) if k == "step"]

    def step_id_refs(self) -> list[str]:
        return [p for k, p in map(classify_token, self.by) if k == "stepid"]

    def hyp_refs(self) -> list[str | None]:
        return [p for k, p in map(classify_token, self.by) if k == "hyp"]


@dataclass(frozen=True)
class Edge:
    """A dependency, always traceable to the line of proof that created it.

    ``step`` is where the reader will find it today; ``step_id`` is what still
    means the same thing after the proof is edited. Anything durable — a citation
    in a paper, a link from another module — must use ``step_id``.
    """

    src: str
    dst: str
    kind: EdgeKind
    step: int | None = None
    step_id: str | None = None

    @property
    def address(self) -> str:
        if self.step_id:
            return f"{self.src}#{self.step_id}"
        return f"{self.src} step {self.step}" if self.step is not None else self.src

    def __str__(self) -> str:
        where = ""
        if self.step is not None:
            where = f" (step {self.step}"
            where += f", #{self.step_id})" if self.step_id else ")"
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
                out.append(Edge(self.id, dep, "proof", step.n, step.sid))
        return out

    def proof_deps(self) -> set[str]:
        return {e.dst for e in self.edges() if e.kind == "proof"}


class Graph:
    """A loaded, in-memory proof graph. Construction does no validation.

    A graph is **immutable after construction** — nothing here mutates ``nodes`` —
    so every derived structure is computed once and cached. That is not a
    micro-optimisation. The previous version rebuilt the entire adjacency map
    inside :meth:`depth`, which :meth:`layers`, ``render.summarise`` and the HTML
    exporter each call once per node. At the 14-node pilot that is invisible; at
    the 30,000-node scale of an imported Lean corpus it is quadratic and turns a
    one-second report into an overnight job.
    """

    def __init__(self, nodes: Iterable[Node], meta: dict | None = None) -> None:
        self.nodes: dict[str, Node] = {}
        self.duplicate_ids: list[tuple[str, str, str]] = []
        #: Corpus-level facts about where this graph came from (extractors set it;
        #: the YAML loader leaves it empty). Never load-bearing for any query.
        self.meta: dict = dict(meta or {})
        for node in nodes:
            if node.id in self.nodes:
                self.duplicate_ids.append(
                    (node.id, self.nodes[node.id].source_path, node.source_path)
                )
                continue
            self.nodes[node.id] = node

        self._edges_cache: list[Edge] | None = None
        self._adj_cache: dict[tuple[EdgeKind, ...], dict[str, set[str]]] = {}
        self._radj_cache: dict[tuple[EdgeKind, ...], dict[str, set[str]]] = {}
        self._depths_cache: dict[tuple[EdgeKind, ...], dict[str, int]] = {}
        self._topo_cache: dict[tuple[EdgeKind, ...], list[str]] = {}

    def __len__(self) -> int:
        return len(self.nodes)

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes.values())

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.nodes

    def get(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def edges(self, kind: EdgeKind | None = None) -> list[Edge]:
        if self._edges_cache is None:
            self._edges_cache = [e for n in self for e in n.edges()]
        if kind is None:
            return list(self._edges_cache)
        return [e for e in self._edges_cache if e.kind == kind]

    # -- cached structures -------------------------------------------------

    def _adj(self, kinds: tuple[EdgeKind, ...]) -> dict[str, set[str]]:
        """Forward adjacency (node -> what it depends on), targets in-graph only.

        Private and shared: callers must not mutate it. :meth:`adjacency` hands
        out a copy for anyone who wants one.
        """
        key = tuple(kinds)
        cached = self._adj_cache.get(key)
        if cached is None:
            cached = {n: set() for n in self.nodes}
            for e in self.edges():
                if e.kind in key and e.src in cached and e.dst in self.nodes:
                    cached[e.src].add(e.dst)
            self._adj_cache[key] = cached
        return cached

    def _radj(self, kinds: tuple[EdgeKind, ...]) -> dict[str, set[str]]:
        """Reverse adjacency: node -> who depends on it."""
        key = tuple(kinds)
        cached = self._radj_cache.get(key)
        if cached is None:
            cached = {n: set() for n in self.nodes}
            for e in self.edges():
                if e.kind in key and e.dst in cached and e.src in self.nodes:
                    cached[e.dst].add(e.src)
            self._radj_cache[key] = cached
        return cached

    # -- graph queries -----------------------------------------------------

    def adjacency(self, kinds: tuple[EdgeKind, ...] = ("proof", "vocabulary")) -> dict[str, set[str]]:
        """A fresh, caller-owned copy of the forward adjacency."""
        return {k: set(v) for k, v in self._adj(kinds).items()}

    def cycles(self, kinds: tuple[EdgeKind, ...] = ("proof", "vocabulary")) -> list[list[str]]:
        """All elementary cycles reachable by DFS, as node-id paths.

        A proof graph must be acyclic: a cycle means some result is, transitively,
        used in its own proof. Iterative DFS with an explicit stack so that deep
        graphs cannot blow the recursion limit.
        """
        adj = self._adj(kinds)
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
        adj = self._adj(kinds)
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
        radj = self._radj(kinds)
        seen: set[str] = set()
        stack = list(radj.get(node_id, ()))
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(radj.get(cur, ()))
        return seen

    def depths(self, kinds: tuple[EdgeKind, ...] = ("proof",)) -> dict[str, int]:
        """Longest chain back to an assumption, for every node, in one pass.

        Kahn's algorithm rather than recursion. A 3,000-deep dependency chain is
        ordinary in a machine-generated corpus and would exceed Python's recursion
        limit; a node is finalised only once every dependency is, so its depth is
        the true longest path. Nodes never dequeued sit on (or behind) a cycle and
        get ``-1`` — the same answer the recursive version gave.
        """
        key = tuple(kinds)
        cached = self._depths_cache.get(key)
        if cached is not None:
            return cached

        adj = self._adj(key)            # node -> what it depends on
        radj = self._radj(key)          # node -> who depends on it
        remaining = {n: len(adj[n]) for n in adj}
        depth: dict[str, int] = {}
        order: list[str] = []
        queue = [n for n, c in remaining.items() if c == 0]
        for n in queue:
            depth[n] = 0

        head = 0
        while head < len(queue):
            n = queue[head]
            head += 1
            order.append(n)
            for user in radj.get(n, ()):
                remaining[user] -= 1
                if remaining[user] == 0:
                    depth[user] = 1 + max(depth[d] for d in adj[user])
                    queue.append(user)

        out = {n: depth.get(n, -1) for n in self.nodes}
        self._depths_cache[key] = out
        self._topo_cache[key] = order
        return out

    def depth(self, node_id: str, kinds: tuple[EdgeKind, ...] = ("proof",)) -> int:
        """Longest chain of proof steps back to something unproved.

        Returns -1 if the node sits on a cycle, since depth is then meaningless.
        """
        return self.depths(kinds).get(node_id, -1)

    def topological_order(self, kinds: tuple[EdgeKind, ...] = ("proof",)) -> list[str]:
        """Dependencies before dependents. Omits nodes on or behind a cycle."""
        key = tuple(kinds)
        if key not in self._topo_cache:
            self.depths(key)
        return list(self._topo_cache[key])

    def layers(self, kinds: tuple[EdgeKind, ...] = ("proof",)) -> dict[int, list[str]]:
        out: dict[int, list[str]] = {}
        for n, d in self.depths(kinds).items():
            out.setdefault(d, []).append(n)
        for v in out.values():
            v.sort()
        return dict(sorted(out.items()))

    def closure_sizes(self, kinds: tuple[EdgeKind, ...] = ("proof",)) -> dict[str, int]:
        """How many distinct nodes each node rests on, transitively.

        Integer bitsets in topological order: one pass, and ORing a few thousand
        Python ints beats a per-node traversal by orders of magnitude. Nodes on a
        cycle are absent from the topological order and fall back to
        :meth:`ancestors`.
        """
        order = self.topological_order(kinds)
        adj = self._adj(kinds)
        index = {n: i for i, n in enumerate(order)}
        clo: dict[str, int] = {}
        for n in order:
            bits = 0
            for dep in adj[n]:
                if dep in clo:
                    bits |= clo[dep] | (1 << index[dep])
            clo[n] = bits
        out = {n: clo[n].bit_count() for n in order}
        for n in self.nodes:
            if n not in out:
                out[n] = len(self.ancestors(n, kinds))
        return out

    def shortest_path(self, src: str, dst: str,
                      kinds: tuple[EdgeKind, ...] = ("proof",)) -> list[str] | None:
        """A shortest dependency path ``src -> ... -> dst``, or None if unreachable."""
        if src not in self.nodes or dst not in self.nodes:
            return None
        if src == dst:
            return [src]
        adj = self._adj(kinds)
        parent: dict[str, str] = {src: src}
        queue = [src]
        head = 0
        while head < len(queue):
            cur = queue[head]
            head += 1
            for nxt in sorted(adj.get(cur, ())):
                if nxt in parent:
                    continue
                parent[nxt] = cur
                if nxt == dst:
                    path = [dst]
                    while path[-1] != src:
                        path.append(parent[path[-1]])
                    return list(reversed(path))
                queue.append(nxt)
        return None

    def neighbourhood(self, node_id: str, radius: int = 1, *,
                      direction: Literal["both", "up", "down"] = "both",
                      max_nodes: int | None = None,
                      kinds: tuple[EdgeKind, ...] = ("proof", "vocabulary"),
                      ) -> tuple[set[str], bool]:
        """Nodes within ``radius`` hops. Returns ``(ids, truncated)``.

        ``down`` follows dependencies, ``up`` follows dependents. Breadth-first,
        so truncation keeps the nearest neighbours — the ones a reader of a
        30,000-node corpus actually wants.
        """
        if node_id not in self.nodes:
            return set(), False
        adj = self._adj(kinds)
        radj = self._radj(kinds)
        seen = {node_id}
        frontier = [node_id]
        truncated = False
        for _ in range(max(radius, 0)):
            nxt: list[str] = []
            for cur in frontier:
                neighbours: set[str] = set()
                if direction in ("both", "down"):
                    neighbours |= adj.get(cur, set())
                if direction in ("both", "up"):
                    neighbours |= radj.get(cur, set())
                for n in sorted(neighbours):
                    if n in seen:
                        continue
                    if max_nodes is not None and len(seen) >= max_nodes:
                        return seen, True
                    seen.add(n)
                    nxt.append(n)
            if not nxt:
                break
            frontier = nxt
        return seen, truncated

    def subgraph(self, node_ids: Iterable[str], meta: dict | None = None) -> "Graph":
        """A view over a subset of nodes.

        The nodes are reused unchanged, so a step whose citation now points
        outside the view keeps that citation in its ``by`` list. That is
        deliberate: dropping it would misrepresent the proof. Renderers mark such
        citations as external instead.
        """
        ids = [i for i in node_ids if i in self.nodes]
        return Graph((self.nodes[i] for i in ids),
                     meta=meta if meta is not None else self.meta)

    def roots(self) -> list[str]:
        """Nodes nothing else depends on — the current frontier."""
        depended_on = {e.dst for e in self.edges()}
        return sorted(n for n in self.nodes if n not in depended_on)

    def leaves(self) -> list[str]:
        """Nodes that depend on nothing — axioms, definitions, background."""
        return sorted(n for n in self.nodes if not self.nodes[n].edges())
