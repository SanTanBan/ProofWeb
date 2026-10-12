"""Import an ordinary Lean/Lake project as a module-level graph. No Lean toolchain.

Most formal corpora are not laid out like Prove2Me. OpenAI's `math` repository
(122,000 files in one library), `NavierStokesAndEuler` and `fluid_lean` are
ordinary Lake projects: one file declares many theorems, and a file's imports say
which *files* it may use, not which theorems it does use. So the honest
granularity available from text is the module, and that is all this importer
claims:

- one node per source file, of kind ``module``;
- one ``imports`` step per node listing the project modules it imports — an
  upper bound on logical dependence, labelled as such, never a proof;
- status ``draft`` always, because nothing here runs Lean;
- holes counted from comment-stripped text: ``sorry``/``admit``,
  ``native_decide``, and ``axiom`` declarations.

What makes it more than ``lake`` already shows is the catalogue. Projects
following the community `formalization.yaml` schema list their main results by
declaration and file. Those are located in the graph, so the audit can say which
catalogued results sit downstream of other catalogued results, and which have a
``sorry`` somewhere in their import closure. A Comparator configuration, where
one is referenced, is recorded as *existing* — not as having been run.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .leantext import parse_imports, strip_comments
from .model import Node, Step

_LIB_LEAN = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)*lean_lib\s+«?([A-Za-z_][\w.']*)»?", re.M)
_DECL = re.compile(
    r"^(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial)\s+)*"
    r"(theorem|lemma|def|abbrev|instance|structure|class|inductive|axiom|opaque)\s+"
    r"«?([^\s:({\[«»]+)»?", re.M)
_SORRY = re.compile(r"(?<![\w.'])(?:sorry|admit)(?![\w'])")
_NATIVE = re.compile(r"(?<![\w.'])native_decide(?![\w'])")
_SKIP_DIRS = {".lake", "lake-packages", ".git", "build"}

#: What this importer can and cannot say about who checked anything.
_CHECKED = ("unknown to proofweb: it reads text and runs no Lean; the project's "
            "own build and Comparator results are not recorded in the repository")


@dataclass(frozen=True)
class ModuleFile:
    module: str
    path: str                   # project-relative POSIX path
    sha256: str
    lines: int
    imports: tuple[str, ...]
    decls: dict                 # kind -> count
    names: tuple[str, ...]      # declared names as written (not namespace-qualified)
    sorry: int
    native_decide: int
    axioms: tuple[str, ...]


@dataclass
class LakeProject:
    root_dir: Path
    commit: str
    toolchain: str = ""
    libs: list[str] = field(default_factory=list)
    modules: dict[str, ModuleFile] = field(default_factory=dict)
    main_results: list[dict] = field(default_factory=list)
    challenge_modules: set[str] = field(default_factory=set)
    comparator_configs: int = 0
    path_to_module: dict[str, str] = field(default_factory=dict)
    review_status: str | None = None
    licence: str = "unknown"
    problems: list[tuple[str, str, str]] = field(default_factory=list)

    def note(self, code: str, path: str, message: str) -> None:
        self.problems.append((code, path, message))


# ---------------------------------------------------------------------------
# reading the project
# ---------------------------------------------------------------------------


_BLOCK_END = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)*(?:lean_lib|lean_exe|require|package|target|extern_lib|"
    r"input_file|input_dir)\b", re.M)
_SRCDIR = re.compile(r"srcDir\s*:=\s*\"([^\"]*)\"")
_ROOTS = re.compile(r"roots\s*:=\s*#\[([^\]]*)\]")


def library_specs(root: Path) -> list[tuple[str, str]]:
    """``(root module, source folder)`` for every library the lakefile declares.

    A library's files live under its ``srcDir`` (``.`` unless stated) and its
    module names start from there: fluid_lean vendors ``ChainPlanar`` under
    ``vendor/ChainPlanar`` and imports it as ``ChainPlanar.*``. A library named
    ``OAI.Analysis`` lives under the ``OAI`` root, so only first components are
    kept.
    """
    raw: list[tuple[str, str]] = []
    lean = root / "lakefile.lean"
    toml = root / "lakefile.toml"
    if lean.exists():
        text = lean.read_text(encoding="utf-8", errors="replace")
        pkg = re.search(r"^\s*package\b", text, re.M)
        pkg_src = "."
        if pkg:
            nxt = _BLOCK_END.search(text, pkg.end())
            m = _SRCDIR.search(text[pkg.end():nxt.start() if nxt else len(text)])
            pkg_src = m.group(1) if m else "."
        for lib in _LIB_LEAN.finditer(text):
            nxt = _BLOCK_END.search(text, lib.end())
            block = text[lib.end():nxt.start() if nxt else len(text)]
            m = _SRCDIR.search(block)
            src = m.group(1) if m else pkg_src
            r = _ROOTS.search(block)
            roots = ([x.strip().lstrip("`").strip("«»") for x in r.group(1).split(",") if x.strip()]
                     if r else [lib.group(1)])
            raw.extend((x, src) for x in roots)
    elif toml.exists():
        data = _load_lakefile_toml(toml.read_text(encoding="utf-8", errors="replace"))
        pkg_src = data.get("srcDir", ".")
        for lib in data.get("lean_lib", []) or []:
            if not isinstance(lib, dict) or "name" not in lib:
                continue
            src = lib.get("srcDir", pkg_src)
            raw.extend((x, src) for x in (lib.get("roots") or [lib["name"]]))
    specs: list[tuple[str, str]] = []
    for name, src in raw:
        spec = (name.split(".")[0], pathlib_posix(src))
        if spec not in specs:
            specs.append(spec)
    return specs


_TOML_TABLE = re.compile(r"^\s*(\[\[?)\s*([A-Za-z0-9_.\-]+)\s*\]\]?\s*(?:#.*)?$")
_TOML_KEY = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*=\s*(.+?)\s*(?:#[^\"\]]*)?$")


def _load_lakefile_toml(text: str) -> dict:
    """The lakefile fields this importer needs, parsed with `tomllib` when the
    Python has it (3.11+) and by a small reader otherwise. The reader handles
    what lakefiles use for libraries: tables, arrays of tables, strings, and
    arrays of strings. Anything it cannot read is skipped, never guessed."""
    try:
        import tomllib
    except ImportError:
        tomllib = None
    if tomllib is not None:
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return {}
    data: dict = {}
    current: dict = data
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        t = _TOML_TABLE.match(line)
        if t:
            current = {}
            if t.group(1) == "[[":
                data.setdefault(t.group(2), []).append(current)
            else:
                data[t.group(2)] = current
            continue
        k = _TOML_KEY.match(line)
        if not k:
            continue
        value = k.group(2)
        if value.startswith('"') and value.endswith('"'):
            current[k.group(1)] = value[1:-1]
        elif value.startswith("[") and value.endswith("]"):
            current[k.group(1)] = re.findall(r'"([^"]*)"', value)
    return data


def pathlib_posix(src: str) -> str:
    return Path(src or ".").as_posix()


def library_roots(root: Path) -> list[str]:
    """Top-level module roots declared in the lakefile (`OAI`, `Euler`, ...)."""
    out: list[str] = []
    for name, _ in library_specs(root):
        if name not in out:
            out.append(name)
    return out


def _source_files(root: Path, specs: list[tuple[str, str]]) -> list[tuple[Path, str]]:
    """``(file, module name)`` pairs. Without library specs, every ``.lean`` file."""
    found: dict[Path, str] = {}
    if specs:
        for name, src in specs:
            base = (root / src).resolve()
            top = base / f"{name}.lean"
            if top.exists():
                found.setdefault(top, module_name(top, base))
            if (base / name).is_dir():
                for p in (base / name).rglob("*.lean"):
                    if not _SKIP_DIRS & set(p.relative_to(base).parts):
                        found.setdefault(p, module_name(p, base))
    else:
        for p in root.rglob("*.lean"):
            if p.name != "lakefile.lean" and not _SKIP_DIRS & set(p.relative_to(root).parts):
                found[p] = module_name(p, root)
    return sorted(found.items(), key=lambda kv: kv[1])


def _project_path(path: Path, root: Path) -> str:
    """Project-relative POSIX path; a ``srcDir`` outside the project stays absolute."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def module_name(path: Path, root: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def parse_module(path: Path, root: Path, *, module: str | None = None,
                 keep_names: bool = True) -> ModuleFile:
    """Read one source file. ``keep_names=False`` drops the declared-name list,
    which only catalogued result files need: on a 122,000-file library the
    names are most of the memory."""
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    text = strip_comments(raw)
    kinds: dict[str, int] = {}
    names: list[str] = []
    axioms: list[str] = []
    for m in _DECL.finditer(text):
        kinds[m.group(1)] = kinds.get(m.group(1), 0) + 1
        names.append(m.group(2))
        if m.group(1) == "axiom":
            axioms.append(m.group(2))
    return ModuleFile(
        module=module or module_name(path, root),
        path=_project_path(path, root),
        sha256=hashlib.sha256(raw.replace("\r\n", "\n").encode("utf-8")).hexdigest(),
        lines=raw.count("\n") + 1,
        imports=tuple(parse_imports(raw)),
        decls=kinds,
        names=tuple(names) if keep_names else (),
        sorry=len(_SORRY.findall(text)) if ("sorry" in text or "admit" in text) else 0,
        native_decide=len(_NATIVE.findall(text)) if "native_decide" in text else 0,
        axioms=tuple(axioms),
    )


def _find_key(obj, key):
    """First value stored under ``key`` anywhere in a parsed YAML document."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_key(v, key)
            if found is not None:
                return found
    return None


def catalogue_paths(root: Path) -> set[str]:
    """Project-relative paths of the files a `formalization.yaml` points at."""
    path = root / "formalization.yaml"
    if not path.exists():
        return set()
    import yaml
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return set()
    return {Path(str(e["file"])).as_posix()
            for e in (_find_key(doc, "main_results") or [])
            if isinstance(e, dict) and e.get("file")}


def read_comparator_configs(project: LakeProject) -> None:
    """Every Comparator configuration in the project, catalogued or not.

    openai/math has 416 challenge configurations but catalogues only 200 main
    results; the rest check supporting results. Each challenge module ends in
    a deliberate sorry, so all of them must be known before holes are counted.
    """
    root = project.root_dir
    for path in sorted([*root.glob("*.json"), *root.glob("*/*.json")]):
        if path.name == "lake-manifest.json" or _SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(cfg, dict) and cfg.get("challenge_module"):
            project.challenge_modules.add(str(cfg["challenge_module"]))
            project.comparator_configs += 1


def read_catalogue(project: LakeProject) -> None:
    """Main results from a `formalization.yaml`, located in the module graph."""
    path = project.root_dir / "formalization.yaml"
    if not path.exists():
        return
    import yaml
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        project.note("catalogue.unreadable", "formalization.yaml", str(exc)[:200])
        return
    review = _find_key(doc, "review")
    if isinstance(review, dict):
        project.review_status = review.get("status")
    for entry in _find_key(doc, "main_results") or []:
        if not isinstance(entry, dict):
            continue
        decl = str(entry.get("declaration") or "")
        file = str(entry.get("file") or "")
        module = (project.path_to_module.get(Path(file).as_posix())
                  or (".".join(Path(file).with_suffix("").parts) if file else ""))
        mod = project.modules.get(module)
        short = decl.rsplit(".", 1)[-1]
        record = {
            "declaration": decl,
            "file": file,
            "module": module,
            "module_found": mod is not None,
            "declaration_found": bool(mod and any(
                n == short or n.endswith("." + short) for n in mod.names)),
            # Until a Comparator configuration says otherwise, the proof is
            # taken to live in the catalogued file.
            "proof_module": module,
        }
        # What the catalogue asserts about itself is kept, and kept apart from
        # anything measured here.
        claimed = {k: entry[k] for k in ("sorry_count", "axioms") if k in entry}
        if claimed:
            record["claimed"] = claimed
        cfg = entry.get("comparator_config")
        if cfg:
            record["comparator_config"] = cfg
            cpath = project.root_dir / cfg
            try:
                c = json.loads(cpath.read_text(encoding="utf-8"))
                record["challenge_module"] = c.get("challenge_module")
                record["solution_module"] = c.get("solution_module")
                record["permitted_axioms"] = list(c.get("permitted_axioms") or [])
                record["nanoda"] = bool(c.get("enable_nanoda"))
                if c.get("challenge_module"):
                    project.challenge_modules.add(c["challenge_module"])
                # The catalogue may point at the challenge (the statement, ending
                # in a deliberate sorry); the proof is the solution module.
                if c.get("solution_module") in project.modules:
                    record["proof_module"] = c["solution_module"]
            except (OSError, ValueError) as exc:
                project.note("comparator.unreadable", cfg, str(exc)[:200])
        if mod is None:
            project.note("catalogue.missing-module", file, f"no source file for {decl}")
        elif not record["declaration_found"]:
            project.note("catalogue.missing-declaration", file,
                         f"{short} is not declared in this file as text")
        project.main_results.append(record)


def load_project(root_dir: str | Path, *, libs: list[str] | None = None,
                 limit: int | None = None) -> LakeProject:
    from .leanp2m import _git_commit

    root = Path(root_dir).resolve()
    project = LakeProject(root_dir=root, commit=_git_commit(root))
    tc = root / "lean-toolchain"
    if tc.exists():
        project.toolchain = tc.read_text(encoding="utf-8").strip()
    specs = library_specs(root)
    if libs:
        known = dict(specs)
        specs = [(lib, known.get(lib, ".")) for lib in libs]
    project.libs = []
    for name, _ in specs:
        if name not in project.libs:
            project.libs.append(name)
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "../LICENSE"):
        lic = root / name
        if lic.exists():
            head = lic.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            project.licence = head[0].strip()[:120] if head else "LICENSE present"
            break
    files = _source_files(root, specs)
    if limit is not None:
        files = files[:limit]
    wanted = catalogue_paths(root)
    for p, mod in files:
        rel = _project_path(p, root)
        try:
            mf = parse_module(p, root, module=mod, keep_names=rel in wanted)
        except OSError as exc:
            project.note("module.unreadable", rel, str(exc))
            continue
        project.modules[mf.module] = mf
        project.path_to_module[rel] = mf.module
    read_comparator_configs(project)
    read_catalogue(project)
    return project


# ---------------------------------------------------------------------------
# nodes
# ---------------------------------------------------------------------------


def build_nodes(project: LakeProject, *, module: str, source: str) -> list[Node]:
    main_by_module: dict[str, list[str]] = {}
    for r in project.main_results:
        main_by_module.setdefault(r["proof_module"], []).append(r["declaration"])

    nodes: list[Node] = []
    for name in sorted(project.modules):
        mf = project.modules[name]
        internal = tuple(sorted({i for i in mf.imports if i in project.modules}))
        external = sorted({i for i in mf.imports if i not in project.modules})
        n_thm = mf.decls.get("theorem", 0) + mf.decls.get("lemma", 0)
        n_def = sum(v for k, v in mf.decls.items() if k not in ("theorem", "lemma"))
        tags = []
        if name in main_by_module:
            tags.append("main-result")
        if name in project.challenge_modules:
            tags.append("challenge")
        if mf.sorry:
            tags.append("sorry")
        if mf.axioms:
            tags.append("axiom")
        if mf.native_decide:
            tags.append("native_decide")
        steps = ()
        if internal:
            steps = (Step(
                n=1, sid="imports",
                claim=("imports these modules (file-level: an upper bound on logical "
                       "dependence, not a record of use)"),
                by=internal),)
        nodes.append(Node(
            id=name,
            kind="module",
            title=name,
            statement_natural=(f"Lean module: {n_thm} theorems/lemmas, "
                               f"{n_def} other declarations, {mf.lines} lines"
                               + (f"; catalogued main result: {', '.join(main_by_module[name])}"
                                  if name in main_by_module else "")),
            steps=steps,
            status="draft",
            formalization={"lean": name},
            provenance={
                "source": f"{source}@{project.commit[:12]}",
                "contributed_by": "proofweb.leanlake importer (mechanical, text-only)",
                "derivation": "imports",
                "step_attribution": "none",
                "granularity": "module",
                "checked_by": _CHECKED,
                "note": ("module-level import graph; says nothing about which theorem "
                         "uses which, and nothing was checked"),
                "lean": {"file": mf.path, "sha256": mf.sha256, "lines": mf.lines,
                         "declarations": mf.decls, "sorry": mf.sorry,
                         "native_decide": mf.native_decide, "axioms": list(mf.axioms),
                         "external_imports": external,
                         "main_results": main_by_module.get(name, [])},
            },
            tags=tuple(tags),
            module=module,
            source_path=mf.path,
            raw={},
        ))
    return nodes


def project_meta(project: LakeProject, *, source: str) -> dict:
    return {
        "corpus": source,
        "commit": project.commit,
        "style": "lake",
        "toolchain": project.toolchain,
        "libraries": project.libs,
        "derivation": "imports",
        "step_attribution": "none",
        "granularity": "module",
        "checked_by": _CHECKED,
        "licence": project.licence,
        "counts": {"modules": len(project.modules),
                   "main_results": len(project.main_results)},
        "main_results": project.main_results,
        "challenge_modules": sorted(project.challenge_modules),
        "comparator_configs": project.comparator_configs,
        "review_status": project.review_status,
        "problems": [{"code": c, "path": p, "message": m}
                     for c, p, m in project.problems[:500]],
        "problem_count": len(project.problems),
    }


def extract_dir(root_dir: str | Path, *, libs: list[str] | None = None,
                limit: int | None = None, module: str | None = None,
                ) -> tuple[LakeProject, list[Node], dict]:
    path = Path(root_dir)
    project = load_project(path, libs=libs, limit=limit)
    source = path.resolve().name
    if source == "lean" and path.resolve().parent.name:   # e.g. openai-math/lean
        source = f"{path.resolve().parent.name}/lean"
    nodes = build_nodes(project, module=module or f"lean-lake-{source.replace('/', '-')}",
                        source=source)
    return project, nodes, project_meta(project, source=source)
