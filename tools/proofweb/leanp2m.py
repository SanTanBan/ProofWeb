"""Import a Prove2Me-structured Lean corpus as a ProofWeb graph.

Prove2Me (Peng et al., Columbia) coordinates swarms of proving agents around a
DAG of theorem statements, and lays a corpus out so that the DAG is recoverable
from the filesystem alone:

    Theorems/Thm_<stem>.lean   one immutable statement, whose proof body defers
                               to the solution module via `p2m_exact_reverting`
    P2M/Sol/S_<stem>.lean      the proof, importing *exactly* the theorems it
                               cites (`Theorems.Thm_<X>`)
    Definitions/Def_<stem>.lean  shared vocabulary

Anthropic's Fermat's Last Theorem corpus is the first large one in public:
29,511 theorems, 13 million lines, written by Claude agents in eleven days and
checked by the Lean kernel, `comparator` and `nanoda`.

**What this module claims, exactly.** Citation edges come from the import
discipline, which is a platform convention — Lean imports are transitive, so a
proof *could* use something it does not directly import. The upstream kernel
check is real but ran upstream; nothing here replays it. Line attribution is
textual: a name occurring in a proof script usually means what it looks like and
sometimes does not. Every node records which of these applies in
`provenance.derivation` and `provenance.step_attribution`, and `proofweb audit`
measures the parts that can be measured. The alternative — presenting import
edges as kernel-derived — would be exactly the overclaim this project exists to
avoid.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

from .leantext import (
    HitMode,
    NON_PROOF_LINE,
    NamespaceTracker,
    binders,
    canonical_signature,
    classify_import,
    hit_form,
    iter_decl_heads,
    normalise_signature,
    parse_imports,
    split_signature,
    strip_comments,
    usage_regex,
)
from .model import Node, Step

#: The tail every Prove2Me statement file ends with. It is mandatory, unique in
#: the file, and names the solution module — which makes it a far more reliable
#: anchor than the declaration head, since 97% of these signatures span several
#: lines and are preceded by up to 1,850 lines of `attribute` directives.
TAIL = re.compile(
    r":=\s*by\s+p2m_exact_reverting\s+@?_root_\.P2MW\.(?P<sol>S_[^\s.]+)\.solution")

SOLUTION_HEAD = re.compile(
    r"^\s*(?:theorem|lemma)\s+(?:_root_\.P2MW\.S_[^\s.]+\.)?solution\b", re.M)

_SORRY = re.compile(r"(?<![A-Za-z0-9_.])(sorry|admit)(?![A-Za-z0-9_])")
_NATIVE = re.compile(r"(?<![A-Za-z0-9_.])native_decide(?![A-Za-z0-9_])")
# The keyword can be the whole line, with the name on the next one — which is
# how the corpus formats its longest declarations.
_DECL_LINE = re.compile(r'^[ 	]*(?:theorem|lemma)(?=[ 	]|$)', re.M)


class P2MError(Exception):
    """The corpus is not laid out the way this importer understands."""


@dataclass(frozen=True)
class ThmFile:
    """One statement file."""

    stem: str
    path: str
    qualified: str
    signature: str
    decl_line: int
    imports: tuple[str, ...]
    sol_ref: str | None
    attrs: tuple[str, ...]
    is_dup: bool
    n_lines: int
    sha256: str


@dataclass(frozen=True)
class SolFile:
    """One proof file, with the proof-script lines isolated."""

    stem: str
    path: str
    imports: tuple[str, ...]
    namespace_stem: str | None
    solution_line: int | None
    body: tuple[tuple[int, str], ...]
    current_ns: tuple[str, ...]
    opened: frozenset[str]
    aux_decls: int
    has_print_axioms: bool
    sorry: int
    native_decide: int
    n_lines: int
    sha256: str


@dataclass(frozen=True)
class DefFile:
    """One definition module. May contain proved lemmas of its own."""

    stem: str
    path: str
    imports: tuple[str, ...]
    decls: tuple[tuple[str, str], ...]
    short_names: tuple[str, ...]
    sorry: int
    n_lines: int
    sha256: str


@dataclass
class Corpus:
    root_dir: Path
    commit: str
    thms: dict[str, ThmFile] = field(default_factory=dict)
    sols: dict[str, SolFile] = field(default_factory=dict)
    defs: dict[str, DefFile] = field(default_factory=dict)
    attributed: dict[str, str] = field(default_factory=dict)
    landmarks: list[str] = field(default_factory=list)
    problems: list[tuple[str, str, str]] = field(default_factory=list)

    def note(self, code: str, path: str, message: str) -> None:
        self.problems.append((code, path, message))


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _rel(path: Path, root: Path) -> str:
    """Corpus-relative POSIX path: stable regardless of where the clone lives.

    Deliberately string-based. `Path.resolve()` costs a syscall, and calling it
    once per file over 60,000 files is several seconds of the import budget.
    """
    p, r = path.as_posix(), root.as_posix().rstrip("/")
    if p.startswith(r + "/"):
        return p[len(r) + 1:]
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return p


def _sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:16]


def _count(pattern: re.Pattern, text: str, *needles: str) -> int:
    """Run ``pattern`` only when a cheap substring test says it could match."""
    if not any(n in text for n in needles):
        return 0
    return len(pattern.findall(text))


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def parse_thm(path: Path, corpus: Corpus | None = None, root: Path | None = None) -> ThmFile | None:
    """Read a statement file, anchored on its mandatory solution tail."""
    raw = _read(path)
    text = strip_comments(raw)
    stem = path.stem[len("Thm_"):] if path.stem.startswith("Thm_") else path.stem
    rel = _rel(path, root) if root else path.as_posix()

    m = TAIL.search(text)
    if m is None:
        if corpus is not None:
            corpus.note("thm.no-tail", rel, "no p2m_exact_reverting tail found")
        return None

    # Walk back to the declaration head that owns this tail.
    head_start = None
    for hm in _DECL_LINE.finditer(text, 0, m.start()):
        head_start = hm
    if head_start is None:
        if corpus is not None:
            corpus.note("thm.no-head", rel, "tail present but no theorem/lemma head before it")
        return None

    tracker = NamespaceTracker()
    for line in text[:head_start.start()].splitlines():
        tracker.feed(line)

    after = text[head_start.end():]
    name_m = re.match(rf"\s*(«[^»]*»|[^\s{{(\[:]+)", after)
    declared = name_m.group(1) if name_m else stem
    qualified = tracker.qualify(declared)

    sig_start = head_start.end() + (name_m.end() if name_m else 0)
    signature = normalise_signature(text[sig_start:m.start()])

    attrs = tuple(
        a.strip()
        for chunk in re.findall(r"@\[([^\]]*)\]", text[max(0, head_start.start() - 200):head_start.start()])
        for a in chunk.split(",") if a.strip()
    )

    return ThmFile(
        stem=stem, path=rel, qualified=qualified, signature=signature,
        decl_line=_line_of(text, head_start.start()),
        imports=tuple(parse_imports(text)),
        sol_ref=m.group("sol"),
        attrs=attrs,
        is_dup=qualified.startswith("P2M.Dup."),
        n_lines=raw.count("\n") + 1,
        sha256=_sha(raw),
    )


def parse_sol(path: Path, corpus: Corpus | None = None, root: Path | None = None) -> SolFile | None:
    """Read a proof file and isolate its proof-script lines."""
    raw = _read(path)
    text = strip_comments(raw)
    stem = path.stem[len("S_"):] if path.stem.startswith("S_") else path.stem
    rel = _rel(path, root) if root else path.as_posix()

    lines = text.splitlines()
    ns_line = None
    ns_stem = None
    tracker = NamespaceTracker()
    for i, line in enumerate(lines, start=1):
        tracker.feed(line)
        if ns_line is None:
            nm = re.match(r"^\s*namespace\s+P2MW\.(S_\S+)", line)
            if nm:
                ns_line = i
                ns_stem = nm.group(1)[len("S_"):]
    if ns_stem is not None and ns_stem != stem and corpus is not None:
        corpus.note("sol.namespace-mismatch", rel,
                    f"namespace names {ns_stem}, file names {stem}")

    head = SOLUTION_HEAD.search(text)
    solution_line = _line_of(text, head.start()) if head else None
    if head is None and corpus is not None:
        corpus.note("sol.no-solution", rel, "no `theorem solution` head found")

    # The proof-script region: everything after the P2MW namespace opens (or,
    # failing that, after the imports), minus the lines that are declarations
    # about the proof rather than part of it.
    start_line = ns_line or 0
    body: list[tuple[int, str]] = []
    aux = 0
    for i, line in enumerate(lines, start=1):
        if i <= start_line:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if NON_PROOF_LINE.match(line):
            continue
        if _DECL_LINE.match(line) and "solution" not in line:
            aux += 1
        body.append((i, stripped))

    ns, opened = tracker.snapshot()
    return SolFile(
        stem=stem, path=rel,
        imports=tuple(parse_imports(text)),
        namespace_stem=ns_stem,
        solution_line=solution_line,
        body=tuple(body),
        current_ns=ns,
        opened=opened,
        aux_decls=aux,
        has_print_axioms="#print axioms solution" in text,
        sorry=_count(_SORRY, text, "sorry", "admit"),
        native_decide=_count(_NATIVE, text, "native_decide"),
        n_lines=raw.count("\n") + 1,
        sha256=_sha(raw),
    )


def parse_def(path: Path, corpus: Corpus | None = None, root: Path | None = None) -> DefFile:
    """Read a definition module: its declarations become searchable vocabulary."""
    raw = _read(path)
    text = strip_comments(raw)
    stem = path.stem[len("Def_"):] if path.stem.startswith("Def_") else path.stem
    decls = tuple((kind, name) for _, kind, name, _ in iter_decl_heads(text))
    shorts = tuple(sorted({n.rsplit(".", 1)[-1] for _, n in decls}))
    return DefFile(
        stem=stem, path=_rel(path, root) if root else path.as_posix(),
        imports=tuple(parse_imports(text)),
        decls=decls,
        short_names=shorts[:300],          # the regex alternation has to stay sane
        sorry=_count(_SORRY, text, "sorry", "admit"),
        n_lines=raw.count("\n") + 1,
        sha256=_sha(raw),
    )


_LANDMARK_TICK = re.compile(r"`([A-Za-z_][A-Za-z0-9_.'₀-ₜ]*)`")
_LANDMARK_DEF = re.compile(r"Def_([A-Za-z0-9_]+)\.lean")
_ATTRIB_ROW = re.compile(r"^\|\s*`?([A-Za-z0-9_/.\-]+\.lean)`?\s*\|\s*([^|]+?)\s*\|", re.M)


def _git_commit(root: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    head = root / ".git" / "HEAD"
    if head.exists():
        try:
            return head.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return "unknown"


def load_corpus(root_dir: str | Path, *, limit: int | None = None) -> Corpus:
    """Read every statement, proof and definition file under ``root_dir``."""
    root = Path(root_dir)
    thm_dir, sol_dir, def_dir = root / "Theorems", root / "P2M" / "Sol", root / "Definitions"
    if not thm_dir.is_dir() or not sol_dir.is_dir():
        raise P2MError(
            f"{root} does not look like a Prove2Me corpus "
            f"(expected Theorems/ and P2M/Sol/)")

    corpus = Corpus(root_dir=root, commit=_git_commit(root))

    thm_files = sorted(thm_dir.glob("Thm_*.lean"))
    if limit is not None:
        thm_files = thm_files[:limit]
    wanted = {p.stem[len("Thm_"):] for p in thm_files}

    for p in thm_files:
        t = parse_thm(p, corpus, root)
        if t is not None:
            corpus.thms[t.stem] = t

    for p in sorted(sol_dir.glob("S_*.lean")):
        stem = p.stem[len("S_"):]
        if limit is not None and stem not in wanted:
            continue
        s = parse_sol(p, corpus, root)
        if s is not None:
            corpus.sols[s.stem] = s

    if def_dir.is_dir():
        for p in sorted(def_dir.glob("Def_*.lean")):
            d = parse_def(p, corpus, root)
            corpus.defs[d.stem] = d

    proof_path = root / "PROOF-PATH.md"
    if proof_path.exists():
        text = _read(proof_path)
        seen: list[str] = []
        for name in _LANDMARK_TICK.findall(text) + [f"Def_{d}" for d in _LANDMARK_DEF.findall(text)]:
            if name not in seen:
                seen.append(name)
        corpus.landmarks = seen

    attribution = root / "ATTRIBUTION.md"
    if attribution.exists():
        for path_str, project in _ATTRIB_ROW.findall(_read(attribution)):
            corpus.attributed[path_str.strip()] = project.strip()

    for stem in corpus.thms:
        if stem not in corpus.sols:
            corpus.note("thm.no-sol", corpus.thms[stem].path, "no matching P2M/Sol file")
    return corpus


# ---------------------------------------------------------------------------
# citations and usage
# ---------------------------------------------------------------------------


def cite_targets(sol: SolFile) -> tuple[list[str], list[str], list[str]]:
    """``(theorem stems, definition stems, external modules)`` cited by a proof."""
    thms: list[str] = []
    defs: list[str] = []
    external: list[str] = []
    for mod in sol.imports:
        kind, payload = classify_import(mod)
        if kind == "thm":
            thms.append(payload)
        elif kind == "def":
            defs.append(payload)
        elif kind in ("mathlib", "lean", "util"):
            external.append(payload)
    return thms, defs, external


def scan_usages(sol: SolFile, corpus: Corpus, cited_thms: Iterable[str],
                *, mode: HitMode = "strict",
                ) -> tuple[dict[int, dict[str, str]], dict[str, str]]:
    """Where each cited name appears in the proof script.

    Only *theorem* citations are attributed to lines. A definition module
    exports hundreds of names, so matching any of them would fire on nearly
    every line and say nothing; definition citations stay on the ``imports``
    step, where they are still edges and still exact.

    Returns ``(by_line, forms)``: ``by_line[lineno]`` maps a cited node id to the
    :func:`~proofweb.leantext.hit_form` of its strongest occurrence on that line,
    and ``forms`` maps each cited node id to its strongest form anywhere (absent
    if the name never occurs).
    """
    short_to_ids: dict[str, list[tuple[str, str]]] = {}
    for stem in cited_thms:
        thm = corpus.thms.get(stem)
        qualified = thm.qualified if thm else stem
        short = qualified.rsplit(".", 1)[-1]
        short_to_ids.setdefault(short, []).append((stem, qualified))
    pattern = usage_regex(short_to_ids.keys(), mode)
    if pattern is None:
        return {}, {}

    rank = {"qualified": 3, "bare-open": 2, "dot": 1, "bare-unopened": 0}
    by_line: dict[int, dict[str, str]] = {}
    best: dict[str, str] = {}
    for lineno, text in sol.body:
        for m in pattern.finditer(text):
            for node_id, qualified in short_to_ids.get(m.group("name"), ()):
                form = hit_form(m.group("prefix"), qualified, sol.current_ns, sol.opened)
                slot = by_line.setdefault(lineno, {})
                if rank[form] > rank.get(slot.get(node_id, "bare-unopened"), -1) or node_id not in slot:
                    slot[node_id] = form
                if rank[form] > rank.get(best.get(node_id, "bare-unopened"), -1) or node_id not in best:
                    best[node_id] = form
    return by_line, best


# ---------------------------------------------------------------------------
# node construction
# ---------------------------------------------------------------------------

Trust = Literal["upstream", "none"]

_UPSTREAM_CHECK = ("lean-kernel (upstream build; comparator; nanoda) "
                   "— not replayed by proofweb")


def build_nodes(corpus: Corpus, *, module: str, source: str,
                usage_lines: bool = True, hit_mode: HitMode = "strict",
                trust: Trust = "upstream") -> list[Node]:
    """Turn a parsed corpus into ProofWeb nodes.

    One theorem node per statement file; one definition node per definition
    module. A theorem's proof steps are the proof-script lines on which a cited
    theorem is named, plus a leading ``imports`` step carrying every citation
    that is never named — so that ``node.proof_deps()`` is always exactly the
    import citation set, whatever the text does.
    """
    landmarks = set(corpus.landmarks)
    qualified_index = {t.qualified: stem for stem, t in corpus.thms.items()}
    nodes: list[Node] = []

    for stem, thm in corpus.thms.items():
        sol = corpus.sols.get(stem)
        cited_thms: list[str] = []
        cited_defs: list[str] = []
        external: list[str] = []
        by_line: dict[int, dict[str, str]] = {}
        forms: dict[str, str] = {}

        if sol is not None:
            cited_thms, cited_defs, external = cite_targets(sol)
            cited_thms = [c for c in cited_thms if c in corpus.thms]
            cited_defs = [c for c in cited_defs if c in corpus.defs]
            by_line, forms = scan_usages(sol, corpus, cited_thms, mode=hit_mode)

        def_ids = [f"Def_{d}" for d in cited_defs]
        all_cited = [*cited_thms, *def_ids]
        # Two different things, deliberately not conflated: a theorem whose name
        # never occurs in the proof script (worth auditing), and a definition
        # module, which is never line-attributed at all (by design, see
        # scan_usages).
        unhit = [c for c in cited_thms if c not in forms]
        on_imports = sorted(set(all_cited if not usage_lines else unhit + def_ids))

        steps: list[Step] = []
        if on_imports:
            steps.append(Step(
                n=1, sid="imports",
                claim=("cited by import: " if not usage_lines else
                       "cited by import, not attributed to a proof line: ")
                      + ", ".join(on_imports),
                by=tuple(on_imports),
                note=("statement-level citations only" if not usage_lines else
                      "definition modules are vocabulary; any theorem here is "
                      "imported but never named in the proof script"),
            ))
        if usage_lines and by_line:
            # A dict, not a scan: one Sol in the FLT corpus is 7,300 lines, and
            # a linear lookup per hit line makes the import quadratic in it.
            line_text = dict(sol.body) if sol else {}
            for lineno in sorted(by_line):
                hits = by_line[lineno]
                text = line_text.get(lineno, "")
                steps.append(Step(
                    n=len(steps) + 1, sid=f"l{lineno}",
                    claim=text[:240],
                    by=tuple(sorted(hits)),
                    note=None,
                ))

        # Vocabulary: what the *statement* needs in order to be stated at all.
        context: list[str] = []
        for mod in thm.imports:
            kind, payload = classify_import(mod)
            if kind == "def" and payload in corpus.defs:
                context.append(f"Def_{payload}")
            elif kind == "thm" and payload in corpus.thms:
                context.append(payload)

        blocking: list[str] = []
        if thm.sol_ref is None:
            blocking.append("statement has no solution tail")
        if sol is None:
            blocking.append("no proof file")
        else:
            if sol.solution_line is None:
                blocking.append("proof file has no `theorem solution`")
            if sol.sorry:
                blocking.append(f"{sol.sorry} sorry/admit in the proof")
        status = "verified" if (trust == "upstream" and not blocking) else "draft"

        note = ("statement identity is kernel-enforced by p2m_exact_reverting; "
                "the proof was checked upstream, not here")
        if blocking:
            note = "not verified: " + "; ".join(blocking)
        elif trust == "none":
            note = "upstream kernel check not trusted (--trust none)"

        provenance: dict[str, object] = {
            "source": f"{source}@{corpus.commit[:12]} (Apache-2.0)",
            "contributed_by": "proofweb.leanp2m importer (mechanical, text-only; "
                              "no AI, no Lean toolchain)",
            "assisted_by": corpus.attributed.get(
                sol.path.split("/")[-3] + "/" + "/".join(sol.path.split("/")[-2:])
                if sol else "",
                "upstream proof machine-generated (agents on Prove2Me, per upstream README)"),
            "derivation": "imports",
            "step_attribution": "textual" if usage_lines else "none",
            "checked_by": _UPSTREAM_CHECK,
            "note": note,
            "lean": {
                "thm": f"{thm.path}:{thm.decl_line}",
                "sol": f"{sol.path}:{sol.solution_line}" if sol else None,
                "sha256_thm": thm.sha256,
                "sha256_sol": sol.sha256 if sol else None,
                "body_lines": len(sol.body) if sol else 0,
                "aux_decls": sol.aux_decls if sol else 0,
                "has_print_axioms": sol.has_print_axioms if sol else False,
                "sorry": sol.sorry if sol else 0,
                "native_decide": sol.native_decide if sol else 0,
                "external_imports": len(external),
                "unused_imports": sorted(unhit),
                "hit_forms": {k: sum(1 for v in forms.values() if v == k)
                              for k in ("qualified", "dot", "bare-open", "bare-unopened")
                              if any(v == k for v in forms.values())},
            },
        }

        tags: list[str] = []
        if thm.qualified in landmarks or stem in landmarks:
            tags.append("landmark")
        if thm.is_dup:
            tags.append("dup")
        if not all_cited:
            tags.append("leaf")
        if any(a.startswith("simp") for a in thm.attrs):
            tags.append("simp")

        nodes.append(Node(
            id=stem,
            kind="theorem",
            title=thm.qualified.replace("P2M.Dup.", ""),
            statement_natural=thm.signature,
            statement_latex=None,
            context=tuple(sorted(set(context))),
            strategy=None,
            hypotheses=tuple(f"{n}: {t}" for n, t in binders(thm.signature)),
            steps=tuple(steps),
            status=status,
            formalization={"lean": thm.qualified},
            provenance=provenance,
            tags=tuple(tags),
            module=module,
            source_path=sol.path if sol else thm.path,
            raw={},
        ))

    for stem, d in corpus.defs.items():
        kinds = ", ".join(f"{k} {n}" for k, n in d.decls[:20])
        nodes.append(Node(
            id=f"Def_{stem}",
            kind="definition",
            title=stem,
            statement_natural=(f"Lean definition module ({len(d.decls)} declarations)"
                               + (f": {kinds}" if kinds else "")),
            context=tuple(sorted({
                f"Def_{p}" for m in d.imports
                for k, p in [classify_import(m)] if k == "def" and p in corpus.defs
            })),
            steps=(),
            status="draft",
            formalization={},
            provenance={
                "source": f"{source}@{corpus.commit[:12]} (Apache-2.0)",
                "contributed_by": "proofweb.leanp2m importer (mechanical, text-only)",
                "derivation": "imports",
                "step_attribution": "none",
                "note": "definition module; the lemmas it proves are not yet nodes",
                "lean": {"file": d.path, "sha256": d.sha256,
                         "declarations": len(d.decls), "sorry": d.sorry},
            },
            tags=("landmark",) if f"Def_{stem}" in landmarks else (),
            module=module,
            source_path=d.path,
            raw={},
        ))

    return nodes


def corpus_meta(corpus: Corpus, *, source: str, root: str | None,
                usage_lines: bool, hit_mode: str, trust: str) -> dict:
    return {
        "corpus": source,
        "commit": corpus.commit,
        "style": "p2m",
        "root": root,
        "derivation": "imports",
        "step_attribution": "textual" if usage_lines else "none",
        "hit_mode": hit_mode,
        "trust": trust,
        "checked_by": _UPSTREAM_CHECK,
        "counts": {
            "theorem_files": len(corpus.thms),
            "solution_files": len(corpus.sols),
            "definition_files": len(corpus.defs),
        },
        "landmarks": corpus.landmarks,
        "problems": [{"code": c, "path": p, "message": m} for c, p, m in corpus.problems[:500]],
        "problem_count": len(corpus.problems),
        "licence": "upstream corpus Apache-2.0; see its NOTICE and ATTRIBUTION.md",
    }


def extract_dir(root_dir: str | Path, *, limit: int | None = None,
                usage_lines: bool = True, hit_mode: HitMode = "strict",
                trust: Trust = "upstream", module: str | None = None,
                root: str | None = None) -> tuple[Corpus, list[Node], dict]:
    """Parse a corpus directory and build nodes. Mirrors ``metamath.extract_file``."""
    path = Path(root_dir)
    corpus = load_corpus(path, limit=limit)
    source = path.name
    mod = module or f"lean-p2m-{source}"
    nodes = build_nodes(corpus, module=mod, source=source,
                        usage_lines=usage_lines, hit_mode=hit_mode, trust=trust)
    meta = corpus_meta(corpus, source=source, root=root,
                       usage_lines=usage_lines, hit_mode=hit_mode, trust=trust)
    return corpus, nodes, meta
