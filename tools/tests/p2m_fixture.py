"""A miniature Prove2Me corpus, written to follow the upstream conventions exactly.

Every convention encoded here was read off Anthropic's Fermat's Last Theorem
repository: the mandatory `p2m_exact_reverting` tail, the statement file
importing its own solution module, `namespace P2MW.S_<stem>`, multi-line
signatures (97% of the real ones are), `attribute` lines that must not be
mistaken for proof, and citations expressed purely as `Theorems.Thm_<X>` imports.

These files have **not** been compiled — no Lean toolchain is involved anywhere
in this pipeline. They are fixtures for the *reader*, and their mathematics is
deliberately trivial so that a reviewer can check by eye what the parser claims.
"""

from __future__ import annotations

from pathlib import Path

THM = """import Mathlib
{extra_imports}import P2M.Sol.S_{stem}
import P2M.Util
namespace {namespace}

{attrs}theorem {name}
{signature} := by p2m_exact_reverting @_root_.P2MW.S_{stem}.solution

end {namespace}
"""

THM_ROOT_NS = """import Mathlib
{extra_imports}import P2M.Sol.S_{stem}
import P2M.Util

{attrs}theorem {name}
{signature} := by p2m_exact_reverting @_root_.P2MW.S_{stem}.solution
"""

SOL = """import Mathlib
{imports}import P2M.Util
namespace P2MW.S_{stem}
set_option autoImplicit false
{opens}
theorem solution
{signature} := by
{body}
"""


def write_corpus(root: Path) -> Path:
    """Write the mini corpus under ``root`` and return it."""
    thm_dir = root / "Theorems"
    sol_dir = root / "P2M" / "Sol"
    def_dir = root / "Definitions"
    for d in (thm_dir, sol_dir, def_dir):
        d.mkdir(parents=True, exist_ok=True)

    def thm(stem: str, name: str, signature: str, *, namespace: str | None = None,
            extra: list[str] = (), attrs: str = "") -> None:
        extra_imports = "".join(f"import {m}\n" for m in extra)
        template = THM if namespace else THM_ROOT_NS
        thm_dir.joinpath(f"Thm_{stem}.lean").write_text(
            template.format(stem=stem, name=name, signature=signature,
                            namespace=namespace or "", extra_imports=extra_imports,
                            attrs=attrs),
            encoding="utf-8")

    def sol(stem: str, signature: str, body: str, *, cites: list[str] = (),
            defs: list[str] = (), opens: str = "") -> None:
        imports = "".join(f"import Theorems.Thm_{c}\n" for c in cites)
        imports += "".join(f"import Definitions.Def_{d}\n" for d in defs)
        sol_dir.joinpath(f"S_{stem}.lean").write_text(
            SOL.format(stem=stem, imports=imports, signature=signature,
                       body=body, opens=opens),
            encoding="utf-8")

    # -- Def_Foo: shared vocabulary, with a proved lemma of its own -----------
    def_dir.joinpath("Def_Foo.lean").write_text(
        "import Mathlib\n"
        "namespace Foo\n\n"
        "structure Box where\n"
        "  x : ℕ\n\n"
        "def Box.double (b : Box) : ℕ := 2 * b.x\n\n"
        "lemma Box.double_eq (b : Box) : b.double = b.x + b.x := by ring\n\n"
        "end Foo\n",
        encoding="utf-8")

    # -- A.left: a leaf, declared inside a namespace, multi-line signature ----
    thm("A_left", "left", "    (n : ℕ)\n    (h : 0 < n) :\n    n + 0 = n",
        namespace="A")
    sol("A_left", "    (n : ℕ)\n    (h : 0 < n) :\n    n + 0 = n",
        "  simpa using Nat.add_zero n")

    # -- B.useLeft: cites A qualified; mentions A.left in a comment and in an
    #    `attribute` line, neither of which may count as a use.
    thm("B_useLeft", "useLeft", "    (f : Foo.Box) :\n    f.x + 0 = f.x",
        namespace="B", extra=["Definitions.Def_Foo"])
    sol("B_useLeft", "    (f : Foo.Box) :\n    f.x + 0 = f.x",
        "  -- A.left would also work here\n"
        "  attribute [-simp] A.left\n"
        "  have hx : 0 < f.x + 1 := Nat.succ_pos _\n"
        "  exact A.left (f.x) hx",
        cites=["A_left"], defs=["Foo"])

    # -- C.root: the goal. Cites B and A (bare, under `open A`) and imports
    #    D_dup without ever naming it.
    thm("C_root", "root", "    (f g : Foo.Box) :\n    f.x + g.x + 0 = f.x + g.x",
        namespace="C", extra=["Definitions.Def_Foo"])
    sol("C_root", "    (f g : Foo.Box) :\n    f.x + g.x + 0 = f.x + g.x",
        "  have h1 : 0 < f.x + g.x + 1 := Nat.succ_pos _\n"
        "  have h2 := B.useLeft f\n"
        "  exact left (f.x + g.x) h1",
        cites=["B_useLeft", "A_left", "D_dup"], defs=["Foo"], opens="open A")

    # -- D.dup: A.left again with the binders renamed. An exact duplicate.
    thm("D_dup", "dup", "    (m : ℕ)\n    (hm : 0 < m) :\n    m + 0 = m", namespace="D")
    sol("D_dup", "    (m : ℕ)\n    (hm : 0 < m) :\n    m + 0 = m",
        "  simpa using Nat.add_zero m")

    # -- E.outside: C's statement with the sum reordered. Nobody cites it.
    thm("E_outside", "outside", "    (f g : Foo.Box) :\n    g.x + f.x + 0 = g.x + f.x",
        namespace="E", extra=["Definitions.Def_Foo"])
    sol("E_outside", "    (f g : Foo.Box) :\n    g.x + f.x + 0 = g.x + f.x",
        "  exact A.left (g.x + f.x) (Nat.succ_pos _)",
        cites=["A_left"], defs=["Foo"])

    root.joinpath("PROOF-PATH.md").write_text(
        "# Route\n\n"
        "The argument runs `A.left`, then `B.useLeft`, then `C.root`.\n"
        "Vocabulary lives in Definitions/Def_Foo.lean.\n"
        "It also uses `Nat.add_zero` from Mathlib, and mentions `Nope.missing`.\n",
        encoding="utf-8")

    root.joinpath("ATTRIBUTION.md").write_text(
        "| File | Project |\n|---|---|\n"
        "| `P2M/Sol/S_A_left.lean` | ImperialCollegeLondon/FLT |\n",
        encoding="utf-8")
    return root


def add_sorry(root: Path) -> None:
    """Break one proof, to exercise the `verified` gate."""
    p = root / "P2M" / "Sol" / "S_D_dup.lean"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "  simpa using Nat.add_zero m", "  sorry"), encoding="utf-8")
