"""Reading Lean as text: the places where a naive regex is wrong.

Each case here is a way the FLT corpus would have broken a simpler parser.
"""

from __future__ import annotations

from proofweb.leantext import (
    binders,
    canonical_signature,
    classify_import,
    hit_form,
    iter_decl_heads,
    normalise_signature,
    parse_imports,
    split_signature,
    strip_comments,
    tokens,
    usage_regex,
)


def test_strip_comments_preserves_line_numbers_and_nesting():
    src = (
        "line one -- trailing comment\n"        # 1
        "/- a block\n"                          # 2
        "   /- nested -/\n"                     # 3
        "   still inside -/\n"                  # 4
        "real code\n"                           # 5
    )
    out = strip_comments(src)
    assert out.count("\n") == src.count("\n")
    assert out.splitlines()[0].startswith("line one")
    assert "trailing" not in out
    assert "nested" not in out and "still inside" not in out
    # Line 5 is still line 5 — the addresses this project hands out depend on it.
    assert out.splitlines()[4].strip() == "real code"


def test_strip_comments_leaves_strings_alone():
    src = 'def s := "not -- a comment"\n'
    assert "not -- a comment" in strip_comments(src)


def test_identifier_boundaries_handle_primes_unicode_and_subscripts():
    body = "exact foo' h₀ (Nat.add_zero n) bar_foo'"
    pattern = usage_regex(["foo'", "add_zero", "foo"])
    found = {(m.group("prefix"), m.group("name")) for m in pattern.finditer(body)}
    assert ("", "foo'") in found
    assert ("Nat.", "add_zero") in found
    # `bar_foo'` must not match `foo'`, and `foo'` must not be read as bare `foo`.
    assert ("", "foo") not in found


def test_classify_import_separates_citations_from_context():
    assert classify_import("Theorems.Thm_A_left") == ("thm", "A_left")
    assert classify_import("Definitions.Def_Foo") == ("def", "Foo")
    assert classify_import("P2M.Sol.S_A_left") == ("sol", "A_left")
    assert classify_import("P2M.Util") == ("util", "P2M.Util")
    assert classify_import("Mathlib.Algebra.Group")[0] == "mathlib"
    assert classify_import("Std.Data.List")[0] == "lean"


def test_parse_imports_stops_at_the_first_real_declaration():
    src = "import A\nimport B\n\nnamespace X\nimport NotAnImport\n"
    assert parse_imports(src) == ["A", "B"]


def test_split_signature_ignores_autoparam_assignment():
    """`(h : p := by simp)` contains a `:=` that does not start the proof."""
    text = "theorem t (n : ℕ) (h : 0 < n := by simp) : n = n := by rfl"
    start = text.index("(n :")
    sig, end = split_signature(text, start)
    assert sig == "(n : ℕ) (h : 0 < n := by simp) : n = n"
    assert text[end:].startswith(":= by rfl")


def test_normalise_and_canonical_signature():
    a = "(m : ℕ)\n    (hm : 0 < m) :\n    m + 0 = m"
    b = "(n : ℕ) (h : 0 < n) : n + 0 = n"
    assert normalise_signature(a) == "(m : ℕ) (hm : 0 < m) : m + 0 = m"
    # The same theorem written twice with different binder names.
    assert canonical_signature(a) == canonical_signature(b)


def test_binders_recovers_named_hypotheses():
    assert binders("(n : ℕ) (h : 0 < n) : n + 0 = n") == [("n", "ℕ"), ("h", "0 < n")]
    assert binders("(a b : ℕ) : a = a") == [("a", "ℕ"), ("b", "ℕ")]


def test_tokens_are_identifiers_only():
    assert "Nat.add_zero" in tokens("(n : ℕ) : Nat.add_zero n = n")


def test_iter_decl_heads_tracks_namespaces_and_root():
    src = (
        "namespace A\n"
        "namespace B\n"
        "theorem inner : True := trivial\n"
        "end B\n"
        "theorem outer : True := trivial\n"
        "theorem _root_.escaped : True := trivial\n"
        "end A\n"
    )
    got = {name: (line, kind) for line, kind, name, _ in iter_decl_heads(src)}
    assert got["A.B.inner"][0] == 3
    assert got["A.outer"][0] == 5
    assert "escaped" in got and "A.escaped" not in got


def test_iter_decl_heads_reads_attributes():
    src = "@[simp, norm_cast]\ntheorem t : True := trivial\n"
    (_, _, name, attrs), = list(iter_decl_heads(src))
    assert name == "t" and "simp" in attrs and "norm_cast" in attrs


def test_hit_forms_grade_confidence():
    # Qualified by the theorem's own namespace: near-certain.
    assert hit_form("A.", "A.left") == "qualified"
    assert hit_form("_root_.A.", "A.left") == "qualified"
    # Some other prefix: field notation on a term, unverifiable from text.
    assert hit_form("h.", "A.left") == "dot"
    # Bare, with the namespace opened here.
    assert hit_form("", "A.left", (), frozenset({"A"})) == "bare-open"
    # Bare, with no reason to resolve.
    assert hit_form("", "A.left", (), frozenset()) == "bare-unopened"
    # A name with no namespace at all is always plausible bare.
    assert hit_form("", "toplevel") == "bare-open"


def test_usage_regex_modes_differ_on_unicode():
    body = "exact h₀.foo"
    assert usage_regex(["foo"], "strict").search(body).group("prefix") == "h₀."
    # The upstream ASCII pattern cannot see the subscript, so it reports a
    # different prefix. Reproducing that is the point of `--hit-mode anthropic`.
    assert usage_regex(["foo"], "anthropic").search(body) is not None
