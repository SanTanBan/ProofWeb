"""The commands as a user runs them, end to end.

These are the first CLI tests in the project. They exist because the import and
audit path has several places where a wiring mistake would produce a plausible
file rather than an error.
"""

from __future__ import annotations

import gzip
import json
import re

from proofweb.cli import main


def test_cli_import_lean_then_audit_end_to_end(p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json"
    assert main(["import-lean", str(p2m_repo), "--root", "C_root", "-o", str(out)]) == 0
    err = capsys.readouterr().err
    assert "imported 6 nodes (5 theorems, 1 definition modules)" in err
    assert "8 distinct citation pairs" in err
    assert "not replayed here" in err

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == "proofweb/extracted"
    assert payload["meta"]["derivation"] == "imports"
    assert payload["meta"]["root"] == "C_root"

    assert main(["audit", "--json", str(out), "--root", "C_root",
                 "--proof-path", str(p2m_repo / "PROOF-PATH.md")]) == 0
    report = capsys.readouterr().out
    assert "# Corpus audit" in report
    assert "theorem nodes" in report and "Landmark route" in report
    assert "derived by `imports`" in report


def test_cli_audit_writes_markdown_and_json(p2m_repo, tmp_path, capsys):
    graph_json = tmp_path / "mini.json"
    main(["import-lean", str(p2m_repo), "--root", "C_root", "-o", str(graph_json)])
    capsys.readouterr()

    md, js = tmp_path / "audit.md", tmp_path / "audit.json"
    assert main(["audit", "--json", str(graph_json), "--root", "C_root",
                 "--report", str(md), "--out", str(js)]) == 0
    assert md.read_text(encoding="utf-8").startswith("# Corpus audit")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["Counts"]["theorems"] == 5


def test_cli_import_lean_gzips_when_asked(p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json.gz"
    assert main(["import-lean", str(p2m_repo), "-o", str(out)]) == 0
    capsys.readouterr()
    with gzip.open(out, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    assert payload["meta"]["style"] == "p2m"
    # and it reads back through the normal path
    assert main(["stats", "--json", str(out)]) == 0
    assert "nodes            6" in capsys.readouterr().out


def test_cli_stats_says_who_did_the_checking(p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json"
    main(["import-lean", str(p2m_repo), "-o", str(out)])
    capsys.readouterr()
    assert main(["stats", "--json", str(out)]) == 0
    text = capsys.readouterr().out
    assert "verified  5/6" in text
    # `verified` must never read as "proofweb checked this".
    assert "0 replayed here" in text and "edges derived by `imports`" in text


def test_cli_uses_is_a_reverse_line_level_index(p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json"
    main(["import-lean", str(p2m_repo), "-o", str(out)])
    capsys.readouterr()

    assert main(["uses", "A_left", "--json", str(out)]) == 0
    text = capsys.readouterr().out
    assert "B_useLeft" in text and "exact A.left" in text
    assert "#l" in text                                   # addressed by line
    assert "invoked at 3 step(s)" in text


def test_cli_why_limits_the_transitive_lists(p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json"
    main(["import-lean", str(p2m_repo), "-o", str(out)])
    capsys.readouterr()
    assert main(["why", "C_root", "--json", str(out), "--limit", "1"]) == 0
    text = capsys.readouterr().out
    assert "Rests on 4 node(s)" in text
    assert "and 3 more" in text


def test_cli_render_html_focus_is_self_contained_and_marks_external_cites(
        p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json"
    main(["import-lean", str(p2m_repo), "-o", str(out)])
    capsys.readouterr()

    page = tmp_path / "focus.html"
    assert main(["render", "html", "--json", str(out), "--focus", "B_useLeft",
                 "--radius", "1", "-o", str(page)]) == 0
    html = page.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    for forbidden in ("<script src=", "<link ", "fetch(", "XMLHttpRequest"):
        assert forbidden not in html
    assert "within 1 hop(s) of B_useLeft" in html
    # A citation leaving the view is neither local nor navigable, and says so.
    assert "cite ext" in html and "outside this view" in html

    payload = json.loads(re.search(r"const DATA = (\{.*?\});\nconst COLOURS",
                                   html, re.S).group(1))
    ids = {n["id"] for n in payload["nodes"]}
    assert ids == {"B_useLeft", "A_left", "C_root", "Def_Foo"}


def test_cli_render_path_to_root(p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json"
    main(["import-lean", str(p2m_repo), "--root", "C_root", "-o", str(out)])
    capsys.readouterr()

    page = tmp_path / "route.html"
    assert main(["render", "html", "--json", str(out),
                 "--path-to-root", "A_left", "-o", str(page)]) == 0
    html = page.read_text(encoding="utf-8")
    assert "shortest dependency route from C_root down to A_left" in html
    payload = json.loads(re.search(r"const DATA = (\{.*?\});\nconst COLOURS",
                                   html, re.S).group(1))
    assert {n["id"] for n in payload["nodes"]} == {"A_left", "C_root"}


def test_cli_render_path_to_root_needs_a_real_dependency(p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json"
    main(["import-lean", str(p2m_repo), "--root", "C_root", "-o", str(out)])
    capsys.readouterr()
    main(["render", "json", "--json", str(out), "--path-to-root", "E_outside",
          "-o", str(tmp_path / "x.json")])
    assert "C_root does not depend on E_outside" in capsys.readouterr().err


def test_cli_render_focus_rejects_an_unknown_node(p2m_repo, tmp_path, capsys):
    out = tmp_path / "mini.json"
    main(["import-lean", str(p2m_repo), "-o", str(out)])
    capsys.readouterr()
    main(["render", "json", "--json", str(out), "--focus", "nope",
          "-o", str(tmp_path / "x.json")])
    assert "no such node: nope" in capsys.readouterr().err
