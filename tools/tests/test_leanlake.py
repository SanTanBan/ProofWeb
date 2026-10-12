"""Module-level import of an ordinary Lake project, and what it refuses to claim."""

from __future__ import annotations

import json

import pytest
from lake_fixture import write_project
from proofweb.audit import audit
from proofweb.cli import main
from proofweb.leanlake import extract_dir, library_roots
from proofweb.model import Graph
from proofweb.validate import Report, check_kind_obligations


@pytest.fixture
def lake_repo(tmp_path):
    return write_project(tmp_path / "demo")


def graph_for(root) -> Graph:
    _, nodes, meta = extract_dir(root)
    return Graph(nodes, meta=meta)


def sect(report, title):
    return next(s for s in report.sections if s.title == title)


def test_library_roots_come_from_the_lakefile(lake_repo):
    assert library_roots(lake_repo) == ["Demo", "Challenges"]


def test_library_roots_from_a_toml_lakefile(tmp_path):
    (tmp_path / "lakefile.toml").write_text(
        'name = "x"\n\n[[lean_lib]]\nname = "Euler"\n\n[[lean_lib]]\nname = "NavierStokes"\n',
        encoding="utf-8")
    assert library_roots(tmp_path) == ["Euler", "NavierStokes"]


def test_one_node_per_file_in_the_declared_libraries_only(lake_repo):
    g = graph_for(lake_repo)
    assert {n.id for n in g} == {
        "Demo", "Demo.A.Lemmas", "Demo.A.Main", "Demo.B.Extra", "Demo.B.Main",
        "Challenges.B"}
    assert "Unlisted.Stray" not in g


def test_edges_are_project_imports_and_external_imports_are_recorded(lake_repo):
    g = graph_for(lake_repo)
    assert g.get("Demo.B.Main").proof_deps() == {"Demo.A.Main", "Demo.B.Extra"}
    assert g.get("Demo.A.Main").proof_deps() == {"Demo.A.Lemmas"}
    lean = g.get("Demo.A.Main").provenance["lean"]
    assert lean["external_imports"] == ["Mathlib.Data.Nat.Basic"]
    assert g.get("Demo.B.Extra").steps == ()       # imports nothing in the project


def test_sorry_in_comments_does_not_count_but_real_sorry_does(lake_repo):
    g = graph_for(lake_repo)
    assert g.get("Demo.A.Lemmas").provenance["lean"]["sorry"] == 1
    assert "sorry" in g.get("Demo.A.Lemmas").tags
    assert g.get("Demo.A.Main").provenance["lean"]["sorry"] == 0


def test_axioms_and_declarations_are_counted(lake_repo):
    g = graph_for(lake_repo)
    extra = g.get("Demo.B.Extra").provenance["lean"]
    assert extra["axioms"] == ["convenient"]
    assert extra["declarations"] == {"axiom": 1, "def": 1}
    assert g.get("Demo.A.Lemmas").provenance["lean"]["declarations"] == {
        "theorem": 1, "lemma": 1}


def test_every_node_is_draft_and_says_why(lake_repo):
    """Nothing here ran Lean, so nothing may be called verified."""
    g = graph_for(lake_repo)
    for n in g:
        assert n.kind == "module" and n.status == "draft"
        p = n.provenance
        assert p["derivation"] == "imports" and p["granularity"] == "module"
        assert p["step_attribution"] == "none"
        assert "runs no Lean" in p["checked_by"]
        for step in n.steps:
            assert step.sid == "imports" and "upper bound" in step.claim


def test_catalogue_results_are_located_and_comparator_configs_read(lake_repo):
    _, _, meta = extract_dir(lake_repo)
    by_decl = {r["declaration"]: r for r in meta["main_results"]}
    b = by_decl["Demo.B.main"]
    assert b["module"] == "Demo.B.Main" and b["module_found"] and b["declaration_found"]
    assert b["challenge_module"] == "Challenges.B" and b["nanoda"] is False
    assert by_decl["Demo.A.main"]["declaration_found"]
    assert not by_decl["Demo.C.missing"]["module_found"]
    assert meta["review_status"] == "unchecked"
    assert any(p["code"] == "catalogue.missing-module" for p in meta["problems"])


def test_module_nodes_pass_the_kind_checks(lake_repo):
    report = Report()
    check_kind_obligations(graph_for(lake_repo), report)
    assert not [f for f in report.findings if f.severity == "error"]


def test_audit_finds_results_resting_on_results_and_holes_below_them(lake_repo):
    report = audit(graph_for(lake_repo))
    rests = sect(report, "Results resting on other results").data
    assert rests["rests_on_other_results"] == {"Demo.B.Main": ["Demo.A.Main"]}
    assert rests["sorry_in_closure"] == {"Demo.A.Main": 1, "Demo.B.Main": 1}
    holes = sect(report, "Holes").data
    assert holes["sorry_modules"] == ["Demo.A.Lemmas"]
    assert holes["challenge_sorry"] == ["Challenges.B"]     # deliberate, by design
    assert holes["axioms"] == ["Demo.B.Extra: convenient"]
    results = sect(report, "Catalogued results").data
    assert (results["main_results"], results["resolved"], results["declared"],
            results["comparator"]) == (3, 2, 2, 1)
    assert results["review_status"] == "unchecked"


def test_audit_markdown_never_says_verified(lake_repo):
    text = audit(graph_for(lake_repo)).to_markdown()
    assert "runs no Lean" in text
    assert '"Imports" is the honest verb' in text
    assert "Whether that check was run, and passed, is not recorded here" in text
    assert "verified" not in text.lower()


def test_cli_import_lake_then_audit_and_query(lake_repo, tmp_path, capsys):
    out = tmp_path / "demo.json"
    assert main(["import-lean", str(lake_repo), "--style", "lake", "-o", str(out)]) == 0
    err = capsys.readouterr().err
    assert "imported 6 modules" in err and "nothing checked by proofweb" in err
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["meta"]["style"] == "lake"

    assert main(["audit", "--json", str(out)]) == 0
    assert "Results resting on other results" in capsys.readouterr().out

    assert main(["uses", "Demo.A.Main", "--json", str(out)]) == 0
    assert "Demo.B.Main" in capsys.readouterr().out


def test_a_catalogue_pointing_at_the_challenge_resolves_to_the_proof(lake_repo):
    """fluid_lean's catalogue names Challenge.lean, the statement; the proof is
    the solution module in the Comparator configuration. Auditing the challenge
    would report its deliberate sorry as a hole under the result."""
    cat = lake_repo / "formalization.yaml"
    cat.write_text(cat.read_text(encoding="utf-8").replace(
        "file: Demo/B/Main.lean", "file: Challenges/B.lean\n      sorry_count: 0"),
        encoding="utf-8")
    g = graph_for(lake_repo)
    b = next(r for r in g.meta["main_results"] if r["declaration"] == "Demo.B.main")
    assert b["module"] == "Challenges.B" and b["proof_module"] == "Demo.B.Main"
    assert b["claimed"] == {"sorry_count": 0}
    assert "challenge" in g.get("Challenges.B").tags
    assert "main-result" in g.get("Demo.B.Main").tags
    rests = sect(audit(g), "Results resting on other results").data
    assert "Challenges.B" not in rests["sorry_in_closure"]


def test_libraries_with_a_source_folder_get_module_names_from_it(tmp_path):
    """fluid_lean vendors ChainPlanar under vendor/ChainPlanar and imports it as
    ChainPlanar.*: the module name starts at srcDir, not at the project root."""
    (tmp_path / "lakefile.toml").write_text(
        'name = "P"\n\n[[lean_lib]]\nname = "Vend"\nsrcDir = "vendor/v"\n\n'
        '[[lean_lib]]\nname = "Main"\n\n[[lean_lib]]\nname = "Solution"\nroots = ["Solution"]\n',
        encoding="utf-8")
    for rel, text in {"vendor/v/Vend/Basic.lean": "theorem v : True := trivial\n",
                      "Main/Use.lean": "import Vend.Basic\n",
                      "Main.lean": "import Main.Use\n",
                      "Solution.lean": "import Main\n"}.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    g = graph_for(tmp_path)
    assert {n.id for n in g} == {"Vend.Basic", "Main", "Main.Use", "Solution"}
    assert g.get("Main.Use").proof_deps() == {"Vend.Basic"}
    assert g.get("Main.Use").provenance["lean"]["external_imports"] == []
    assert g.get("Vend.Basic").source_path == "vendor/v/Vend/Basic.lean"


def test_uncatalogued_challenges_are_still_recognised(lake_repo):
    """openai/math catalogues 200 results but ships 416 Comparator challenges;
    a challenge checking a supporting result still ends in a deliberate sorry."""
    (lake_repo / "Challenges" / "Support.lean").write_text(
        "import Mathlib.Data.Nat.Basic\n\ntheorem Demo.support : True := sorry\n",
        encoding="utf-8")
    (lake_repo / "Challenges" / "Support.json").write_text(
        '{"challenge_module": "Challenges.Support", "solution_module": "Demo.A.Main",'
        ' "theorem_names": ["Demo.support"], "permitted_axioms": []}', encoding="utf-8")
    g = graph_for(lake_repo)
    assert g.meta["comparator_configs"] == 2
    holes = sect(audit(g), "Holes").data
    assert holes["challenge_sorry"] == ["Challenges.B", "Challenges.Support"]
    assert holes["sorry_modules"] == ["Demo.A.Lemmas"]
