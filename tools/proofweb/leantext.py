"""Reading Lean 4 source as text, carefully.

No Lean toolchain is involved anywhere in this module. That is a deliberate
constraint, not a shortcut: the whole point of the formal track is a pipeline a
contributor can run and audit with nothing but Python, in the same posture as
the Metamath verifier. It also has a limit that must be stated wherever its
output is used — text is not elaboration. A name that occurs in a proof script
might resolve to something else entirely, and a name that does not occur might
still be used through a tactic. :func:`hit_form` exists to grade that
uncertainty rather than hide it.

Everything here is tuned to one corpus shape (Prove2Me; see :mod:`leanp2m`) but
none of it is specific to Fermat's Last Theorem.
"""

from __future__ import annotations

import re
from typing import Iterable, Iterator, Literal

#: Characters Lean allows inside an identifier. ``\w`` is Unicode-aware in
#: Python, which covers ``ℕ`` and Greek, but subscripts (``h₀``) and the prime
#: and bang/question suffixes (``foo'``, ``simp!``) need spelling out.
IDENT_CHARS = r"\w'!?₀-ₜ′"

#: A Lean identifier, possibly dotted, possibly «guillemet-quoted».
IDENT = re.compile(rf"«[^»]*»|[{IDENT_CHARS}]+(?:\.[{IDENT_CHARS}]+)*")

#: Lines that are declarations *about* a proof rather than part of one. The
#: root theorem carries ~1,850 `attribute [-simp] ...` lines naming thousands of
#: theorems; counting those as citations would swamp every real signal.
NON_PROOF_LINE = re.compile(
    r"^\s*(?:attribute\b|p2m_export\b|p2m_open\b|open\b|namespace\b|end\b|"
    r"set_option\b|import\b|universe\b|variable\b|section\b|"
    r"#print\b|#guard_msgs\b|#align\b|@\[)"
)

_COMMENT_SCAN = re.compile(r'--[^\n]*|/-|-/|"(?:\\.|[^"\\\n])*"')

_BRACKETS = {"(": ")", "[": "]", "{": "}", "⦃": "⦄", "⟨": "⟩", "«": "»"}
_CLOSERS = {v: k for k, v in _BRACKETS.items()}

_DECL_KINDS = (
    "theorem", "lemma", "def", "abbrev", "instance", "structure", "class",
    "inductive", "opaque", "axiom", "example",
)
DECL_HEAD = re.compile(
    r"^(?:@\[[^\]]*\]\s*)*"
    r"(?:(?:protected|private|noncomputable|nonrec|unsafe|partial|scoped)\s+)*"
    rf"(?P<kind>{'|'.join(_DECL_KINDS)})\s+"
    rf"(?P<name>«[^»]*»|[{IDENT_CHARS}]+(?:\.[{IDENT_CHARS}]+)*)",
    re.M,
)

_ATTRS = re.compile(r"@\[([^\]]*)\]")


_NOT_NEWLINE = re.compile("[^\n]")


def strip_comments(text: str) -> str:
    """Blank out comments, preserving every newline and every offset.

    Line numbers are the addresses this project hands out (``S_X#l42``), so a
    comment stripper that shifted them would break the one thing the format
    promises. Comment characters become spaces; newlines survive untouched.

    Handles ``--`` to end of line, *nested* ``/- ... -/``, and skips over string
    literals so a ``"--"`` inside a string is not mistaken for a comment.

    Written on slices rather than a character list: the largest proof file in
    the Fermat corpus is 1.6 MB, and a per-character Python loop over 13 million
    lines is the difference between a five-minute import and an abandoned one.
    """
    pieces: list[str] = []
    cursor = 0          # everything before this is already emitted
    pos = 0
    depth = 0
    block_start = 0
    n = len(text)

    def blank(segment: str) -> str:
        return _NOT_NEWLINE.sub(" ", segment)

    while pos < n:
        m = _COMMENT_SCAN.search(text, pos)
        if m is None:
            break
        token = m.group(0)
        lo, hi = m.span()
        if depth:
            # Inside a block comment: only the delimiters move the depth, and
            # everything between them is comment, not just the matched spans.
            if token == "/-":
                depth += 1
            elif token == "-/":
                depth -= 1
                if depth == 0:
                    pieces.append(text[cursor:block_start])
                    pieces.append(blank(text[block_start:hi]))
                    cursor = hi
            pos = hi
            continue
        if token.startswith('"'):
            pos = hi                       # a string literal: leave it alone
            continue
        if token == "/-":
            depth = 1
            block_start = lo
            pos = hi
            continue
        if token == "-/":
            pos = hi                       # stray closer outside a block; ignore
            continue
        pieces.append(text[cursor:lo])     # a line comment
        pieces.append(blank(token))
        cursor = hi
        pos = hi

    if depth:                              # unterminated block comment
        pieces.append(text[cursor:block_start])
        pieces.append(blank(text[block_start:]))
        cursor = n
    pieces.append(text[cursor:])
    return "".join(pieces)


def parse_imports(text: str) -> list[str]:
    """Module names from the leading ``import`` block."""
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("import "):
            out.append(s[len("import "):].strip())
            continue
        if s.startswith("--") or s.startswith("/-"):
            continue
        break                              # imports must precede everything else
    return out


ImportKind = Literal["thm", "def", "sol", "util", "mathlib", "lean", "other"]

_EXTERNAL_ROOTS = ("Mathlib", "Std", "Batteries", "Aesop", "Init", "Lean", "Qq", "Plausible")


def classify_import(module: str) -> tuple[ImportKind, str]:
    """Split an import into (kind, payload).

    ``Theorems.Thm_X`` is a *citation*: under the Prove2Me discipline a proof
    imports exactly the theorems it uses. Everything else is context.
    """
    if module.startswith("Theorems.Thm_"):
        return "thm", module[len("Theorems.Thm_"):]
    if module.startswith("Definitions.Def_"):
        return "def", module[len("Definitions.Def_"):]
    if module.startswith("P2M.Sol.S_"):
        return "sol", module[len("P2M.Sol.S_"):]
    if module.startswith("P2M."):
        return "util", module
    head = module.split(".", 1)[0]
    if head in _EXTERNAL_ROOTS:
        return ("mathlib" if head == "Mathlib" else "lean"), module
    return "other", module


class NamespaceTracker:
    """Follows ``namespace`` / ``end`` / ``open`` so a declared name can be qualified.

    Deliberately forgiving: Lean's real scoping rules are richer than anything a
    regex should claim to implement, and a wrong qualification is worse than an
    approximate one that is labelled. Anything it cannot resolve surfaces as a
    parse problem rather than as a silent guess.
    """

    _NAMESPACE = re.compile(r"^\s*namespace\s+(\S+)")
    _END = re.compile(r"^\s*end\b\s*(\S*)")
    _SECTION = re.compile(r"^\s*section\b\s*(\S*)")
    _OPEN = re.compile(r"^\s*open\s+(.+?)(?:\s+in)?\s*$")
    _P2M_OPEN = re.compile(r'^\s*p2m_open\s+"([^"]*)"')
    _P2M_EXPORT = re.compile(r'^\s*p2m_export\s+"([^"]*)"\s+"([^"]*)"')

    def __init__(self) -> None:
        self.current: list[str] = []
        self.opened: set[str] = set()
        self._stack: list[str | None] = []     # namespace name, or None for a section

    #: The only line starts that can change scope. Checking membership before
    #: running five regexes matters: the FLT import feeds this 700,000 times per
    #: 1,500 files, and the overwhelming majority of lines are proof script.
    _KEYWORDS = frozenset({"namespace", "end", "section", "open",
                           "p2m_open", "p2m_export"})

    def feed(self, line: str) -> None:
        stripped = line.lstrip()
        if not stripped:
            return
        head = stripped.split(" ", 1)[0].rstrip("\t\r\n")
        if head not in self._KEYWORDS:
            return
        m = self._NAMESPACE.match(line)
        if m:
            parts = m.group(1).split(".")
            self.current.extend(parts)
            self._stack.append(m.group(1))
            return
        m = self._SECTION.match(line)
        if m:
            self._stack.append(None)
            return
        m = self._END.match(line)
        if m:
            if self._stack:
                name = self._stack.pop()
                if name is not None:
                    for _ in name.split("."):
                        if self.current:
                            self.current.pop()
            return
        m = self._P2M_OPEN.match(line)
        if m:
            # `p2m_open "A~hidden B"` — namespace then optional hidden names.
            for chunk in m.group(1).split():
                self.opened.add(chunk.split("~", 1)[0])
            return
        m = self._P2M_EXPORT.match(line)
        if m:
            self.opened.add(m.group(1))
            return
        m = self._OPEN.match(line)
        if m:
            for chunk in m.group(1).split():
                if chunk in ("in", "renaming", "hiding"):
                    break
                self.opened.add(chunk)
            return

    def qualify(self, declared: str) -> str:
        if declared.startswith("_root_."):
            return declared[len("_root_."):]
        if self.current:
            return ".".join(self.current + [declared])
        return declared

    def snapshot(self) -> tuple[tuple[str, ...], frozenset[str]]:
        return tuple(self.current), frozenset(self.opened)


def iter_decl_heads(text: str) -> Iterator[tuple[int, str, str, tuple[str, ...]]]:
    """Yield ``(line_number, kind, qualified_name, attributes)`` for each declaration.

    ``text`` should already be comment-stripped. Line numbers are 1-based.
    """
    tracker = NamespaceTracker()
    lines = text.splitlines()
    line_starts: list[int] = []
    pos = 0
    for line in lines:
        line_starts.append(pos)
        pos += len(line) + 1

    heads = {m.start(): m for m in DECL_HEAD.finditer(text)}
    for i, line in enumerate(lines):
        start = line_starts[i]
        m = heads.get(start)
        if m is None:
            tracker.feed(line)
            continue
        attrs = tuple(
            a.strip() for chunk in _ATTRS.findall(m.group(0)) for a in chunk.split(",")
            if a.strip()
        )
        yield i + 1, m.group("kind"), tracker.qualify(m.group("name")), attrs


def split_signature(text: str, start: int) -> tuple[str, int]:
    """From ``start`` to the ``:=`` that opens the proof, at bracket depth zero.

    The depth check is what makes this safe against auto-param binders such as
    ``(h : p := by simp)``, whose ``:=`` must not be mistaken for the start of
    the proof.
    """
    depth = 0
    i = start
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in _BRACKETS:
            depth += 1
        elif ch in _CLOSERS:
            depth = max(0, depth - 1)
        elif depth == 0 and ch == ":" and text.startswith(":=", i):
            return text[start:i].strip(), i
        i += 1
    return text[start:].strip(), n


_WS = re.compile(r"\s+")
_UNIV = re.compile(r"\.\{[^}]*\}")


def normalise_signature(sig: str) -> str:
    """Collapse whitespace and drop universe annotations."""
    return _WS.sub(" ", _UNIV.sub("", sig)).strip()


_BINDER = re.compile(rf"\(\s*(?P<names>[{IDENT_CHARS}][{IDENT_CHARS}\s]*?)\s*:\s*(?P<type>[^()]*)\)")


def binders(sig: str) -> list[tuple[str, str]]:
    """Best-effort ``(name, type)`` for simple explicit binders.

    Only flat parenthesised binders are recovered; anything nested is skipped.
    This feeds a human-readable ``hypotheses`` list, never an edge, so an
    incomplete answer costs nothing.
    """
    out: list[tuple[str, str]] = []
    for m in _BINDER.finditer(sig):
        typ = normalise_signature(m.group("type"))
        if not typ:
            continue
        for name in m.group("names").split():
            out.append((name, typ))
    return out


def canonical_signature(sig: str) -> str:
    """A signature with binder names alpha-renamed, for duplicate detection.

    ``(m : ℕ) (hm : 0 < m) : m + 0 = m`` and ``(n : ℕ) (h : 0 < n) : n + 0 = n``
    are the same theorem written twice. Renaming binders in order of appearance
    makes them compare equal; anything the renamer cannot see stays as it is,
    which can only cause a duplicate to be missed, never invented.
    """
    sig = normalise_signature(sig)
    mapping: dict[str, str] = {}
    for name, _ in binders(sig):
        if name not in mapping:
            mapping[name] = f"v{len(mapping)}"
    if not mapping:
        return sig
    pattern = re.compile(
        rf"(?<![{IDENT_CHARS}.])(?:{'|'.join(re.escape(k) for k in sorted(mapping, key=len, reverse=True))})"
        rf"(?![{IDENT_CHARS}])"
    )
    return pattern.sub(lambda m: mapping[m.group(0)], sig)


def tokens(sig: str) -> set[str]:
    """Identifier tokens, for Jaccard similarity between statements."""
    return {m.group(0) for m in IDENT.finditer(normalise_signature(sig))}


HitMode = Literal["strict", "anthropic"]
HitForm = Literal["qualified", "dot", "bare-open", "bare-unopened"]


def usage_regex(short_names: Iterable[str], mode: HitMode = "strict") -> re.Pattern | None:
    """One alternation matching any of ``short_names``, with its qualifier.

    ``anthropic`` reproduces the pattern used by the upstream docs generator, so
    that our counts can be compared with the numbers they published about their
    own corpus. ``strict`` is Unicode-aware, which theirs is not.
    """
    names = sorted({n for n in short_names if n}, key=len, reverse=True)
    if not names:
        return None
    alt = "|".join(re.escape(n) for n in names)
    if mode == "anthropic":
        return re.compile(
            r"(?<![A-Za-z0-9_.'])(?P<prefix>(?:[A-Za-z0-9_.']*\.)?)"
            rf"(?P<name>{alt})(?![A-Za-z0-9_'])"
        )
    return re.compile(
        rf"(?<![{IDENT_CHARS}.])(?P<prefix>(?:[{IDENT_CHARS}]+\.)*)"
        rf"(?P<name>{alt})(?![{IDENT_CHARS}])"
    )


def hit_form(prefix: str, qualified: str,
             current: tuple[str, ...] = (), opened: frozenset[str] = frozenset()) -> HitForm:
    """How much confidence a textual occurrence deserves.

    ``qualified``
        The prefix matches the theorem's own namespace path. Near-certain.
    ``dot``
        Some *other* prefix — most often field notation (``h.symm``), where the
        prefix is a term, not a namespace. Unverifiable without elaboration.
    ``bare-open``
        No prefix, and the namespace is open here, so the name plausibly
        resolves to the cited theorem.
    ``bare-unopened``
        No prefix and no reason for the name to resolve here. Weakest.
    """
    pre = prefix[:-1] if prefix.endswith(".") else prefix
    if pre.startswith("_root_"):
        pre = pre[len("_root_"):].lstrip(".")
    ns = qualified.rsplit(".", 1)[0] if "." in qualified else ""
    if pre:
        if ns and (ns == pre or ns.endswith("." + pre) or pre.endswith(ns)):
            return "qualified"
        return "dot"
    if not ns or ns in opened or ns in {".".join(current[:i]) for i in range(1, len(current) + 1)}:
        return "bare-open"
    return "bare-unopened"
