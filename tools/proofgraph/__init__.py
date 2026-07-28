"""ProofGraph — a knowledge graph of mathematics whose edges are derived from proofs.

The package is deliberately small. Three ideas carry the whole design:

1. :mod:`proofgraph.model` — a node declares a *proof*, not a dependency list.
   Each proof step carries its own justifications, and edges are derived from
   them. You cannot claim a dependency you did not use, and you cannot use a
   result without the edge appearing.

2. :mod:`proofgraph.loader` — nodes live in YAML on disk, one file per node,
   grouped into modules. Plain text, reviewable in a pull request.

3. :mod:`proofgraph.validate` — the graph is only worth something if it is
   checked. Every invariant that can be machine-checked is checked in CI.

Anything that cannot be machine-checked (does step 7 *really* follow?) is the
job of human review and, eventually, of a link to a proof assistant.
"""

from __future__ import annotations

from .loader import load_graph, load_manifests
from .model import Edge, Graph, Node, Step

__version__ = "0.1.0"

__all__ = ["Edge", "Graph", "Node", "Step", "load_graph", "load_manifests", "__version__"]
