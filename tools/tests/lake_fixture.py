"""A miniature Lake project in the shape of openai/math's `lean/` directory.

Written by hand from that repository's conventions (a `lean_lib` per area under
one root, a `formalization.yaml` catalogue in the mathlib-initiative schema, and
Comparator challenge configurations), not compiled: nothing here runs Lean.

    Demo.lean                 imports both results
    Demo/A/Lemmas.lean        a real sorry, and one inside a comment that must not count
    Demo/A/Main.lean          result A; imports Lemmas and Mathlib
    Demo/B/Main.lean          result B; imports A (B rests on A) and Extra
    Demo/B/Extra.lean         declares an axiom
    Challenges/B.lean         Comparator challenge statement for B
    Unlisted/Stray.lean       outside every lean_lib: must not be read
"""

from __future__ import annotations

from pathlib import Path

FILES = {
    "lakefile.lean": """import Lake
open Lake DSL

package Demo where
  version := v!"0.1.0"

require mathlib from git "https://github.com/leanprover-community/mathlib4.git" @ "abc"

@[default_target] lean_lib Demo

lean_lib Demo.A where
  roots := #[`Demo.A]
  globs := #[`Demo.A.+]
lean_lib Challenges where globs := #[`Challenges.+]
""",
    "lean-toolchain": "leanprover/lean4:v4.34.1\n",
    "LICENSE": "Apache License\nVersion 2.0, January 2004\n",
    "Demo.lean": "import Demo.A.Main\nimport Demo.B.Main\n",
    "Demo/A/Lemmas.lean": """import Mathlib.Data.Nat.Basic

/-! Nothing here is finished: `sorry` in a doc comment must not count. -/

namespace Demo.A

-- a sorry in a line comment must not count either
theorem helper (n : ℕ) : n + 0 = n := by
  sorry

lemma helper' (n : ℕ) : 0 + n = n := by simp

end Demo.A
""",
    "Demo/A/Main.lean": """import Demo.A.Lemmas
import Mathlib.Data.Nat.Basic

namespace Demo.A

theorem main (n : ℕ) : n + 0 = n := helper n

end Demo.A
""",
    "Demo/B/Extra.lean": """namespace Demo.B

axiom convenient : ∀ n : Nat, n = n

def twice (n : Nat) : Nat := 2 * n

end Demo.B
""",
    "Demo/B/Main.lean": """import Demo.A.Main
import Demo.B.Extra

namespace Demo.B

theorem main (n : ℕ) : n + 0 = n := Demo.A.main n

end Demo.B
""",
    "Challenges/B.lean": """import Mathlib.Data.Nat.Basic

theorem Demo.B.main (n : ℕ) : n + 0 = n := sorry
""",
    "Challenges/B.json": """{
  "challenge_module": "Challenges.B",
  "solution_module": "Demo.B.Main",
  "theorem_names": ["Demo.B.main"],
  "definition_names": [],
  "permitted_axioms": ["propext", "Quot.sound", "Classical.choice"],
  "enable_nanoda": false
}
""",
    "Unlisted/Stray.lean": "theorem stray : True := trivial\n",
    "formalization.yaml": """version: "v0.4"
project:
  name: "Demo"
status:
  scope: "Partial progress."
  main_results:
    - comparator_config: Challenges/B.json
      declaration: Demo.B.main
      file: Demo/B/Main.lean

    - declaration: Demo.A.main
      file: Demo/A/Main.lean

    - declaration: Demo.C.missing
      file: Demo/C/Main.lean
review:
  status: unchecked
""",
}


def write_project(root: Path) -> Path:
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root
