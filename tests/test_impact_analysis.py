import os
import pytest
from unittest.mock import patch, MagicMock

from n3mo.core.core_engine import (
    parse_diff_hunks,
    get_changed_files_with_hunks,
    get_impact_for_changed_files,
    merge_impacts,
    generate_mermaid_graph,
    format_impact_markdown
)
from n3mo.core.symbol_extractor import extract_symbols


def test_parse_diff_hunks_with_simulated_git_diff():
    fake_diff = """diff --git a/n3mo/core/symbol_extractor.py b/n3mo/core/symbol_extractor.py
index 9416b6f..fcc1ff4 100644
--- a/n3mo/core/symbol_extractor.py
+++ b/n3mo/core/symbol_extractor.py
@@ -272,0 +273,5 @@ def _visit_generic(node, current_scope_id, symbols, calls, imports, file_path, l
+            if func_node is None:
+                func_node = next(
+                    (c for c in node.children if c.type in ("identifier", "simple_identifier")),
+                    None,
+                )
diff --git a/tests/test_ruby_kotlin_support.py b/tests/test_ruby_kotlin_support.py
new file mode 100644
index 0000000..fe23f5a
--- /dev/null
+++ b/tests/test_ruby_kotlin_support.py
@@ -0,0 +1,142 @@
+from pathlib import Path
+"""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=fake_diff, returncode=0)
        diff_info = parse_diff_hunks(".", "base_sha", "head_sha")

    assert "n3mo/core/symbol_extractor.py" in diff_info["changed_files"]
    assert "tests/test_ruby_kotlin_support.py" in diff_info["changed_files"]

    # Head ranges
    assert diff_info["head_ranges"]["n3mo/core/symbol_extractor.py"] == [(273, 277)]
    assert diff_info["head_ranges"]["tests/test_ruby_kotlin_support.py"] == [(1, 142)]

    # Base ranges (old file had pure insertion at line 272)
    assert diff_info["base_ranges"]["n3mo/core/symbol_extractor.py"] == [(272, 272)]

    # Added files
    assert "tests/test_ruby_kotlin_support.py" in diff_info["added_files"]
    assert "n3mo/core/symbol_extractor.py" not in diff_info["added_files"]


def test_pr39_symbol_line_overlap_filters_out_untouched_functions():
    """
    Simulates PR #39 on symbol_extractor.py:
    Only _visit_generic (lines 237..496) intersects the hunk at lines 273..277.
    All other 11 functions in symbol_extractor.py must be filtered out.
    """
    mock_symbols = [
        ("id-1", "load_lang", "n3mo/core/symbol_extractor.py", 15, 21),
        ("id-2", "get_parser", "n3mo/core/symbol_extractor.py", 53, 59),
        ("id-3", "extract_symbols", "n3mo/core/symbol_extractor.py", 67, 196),
        ("id-4", "extract_generic", "n3mo/core/symbol_extractor.py", 198, 212),
        ("id-5", "_find_function_declarator", "n3mo/core/symbol_extractor.py", 215, 222),
        ("id-6", "_get_cpp_declarator_name", "n3mo/core/symbol_extractor.py", 224, 234),
        ("id-7", "_visit_generic", "n3mo/core/symbol_extractor.py", 237, 496),
        ("id-8", "extract_symbols_imports_calls", "n3mo/core/symbol_extractor.py", 500, 524),
        ("id-9", "_visit_definitions_and_calls", "n3mo/core/symbol_extractor.py", 526, 570),
        ("id-10", "_visit_imports", "n3mo/core/symbol_extractor.py", 572, 618),
        ("id-11", "_extract_strings_as_imports", "n3mo/core/symbol_extractor.py", 620, 626),
        ("id-12", "_add_import", "n3mo/core/symbol_extractor.py", 628, 635),
    ]

    hunk_ranges = {"n3mo/core/symbol_extractor.py": [(273, 277)]}

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.side_effect = [
        mock_symbols,   # Symbols query
        [],             # Callers query for _visit_generic
    ]

    with patch("n3mo.core.core_engine.get_connection", return_value=mock_conn), \
         patch("n3mo.core.core_engine.release_connection"):
        impacts = get_impact_for_changed_files(
            "proj-123",
            ["n3mo/core/symbol_extractor.py"],
            file_line_ranges=hunk_ranges,
            is_head=True
        )

    # ONLY _visit_generic must be present!
    assert len(impacts) == 1
    assert "n3mo/core/symbol_extractor.py::_visit_generic" in impacts
    assert impacts["n3mo/core/symbol_extractor.py::_visit_generic"]["name"] == "_visit_generic"
    assert "load_lang" not in str(impacts.keys())
    assert "get_parser" not in str(impacts.keys())
    assert "extract_symbols" not in str(impacts.keys())


def test_real_git_diff_hunks_on_pr39_commit():
    """
    Directly tests git diff parsing and symbol intersection on commit cd78352 in the repo.
    """
    diff_info = parse_diff_hunks(".", "cd78352~1", "cd78352")
    assert "n3mo/core/symbol_extractor.py" in diff_info["changed_files"]
    ranges = diff_info["head_ranges"]["n3mo/core/symbol_extractor.py"]
    assert ranges == [(273, 277)]

    syms, _, _ = extract_symbols("n3mo/core/symbol_extractor.py")
    modified_syms = []
    for s in syms:
        s_start = s.get("start_line", 0)
        s_end = s.get("end_line") or s_start
        if any(s_start <= h_end and s_end >= h_start for h_start, h_end in ranges):
            modified_syms.append(s["name"])

    # Verified: exactly 1 function modified, 0 false positives
    assert modified_syms == ["_visit_generic"]


def test_merge_impacts_scoping_and_statuses():
    base_impacts = {
        "file_a.py::func_mod": {"name": "func_mod", "file_path": "file_a.py", "line": 10, "callers": []},
        "file_a.py::func_del": {"name": "func_del", "file_path": "file_a.py", "line": 50, "callers": []},
        "file_b.py::same_name": {"name": "same_name", "file_path": "file_b.py", "line": 5, "callers": []},
    }
    head_impacts = {
        "file_a.py::func_mod": {"name": "func_mod", "file_path": "file_a.py", "line": 10, "callers": []},
        "file_a.py::func_add": {"name": "func_add", "file_path": "file_a.py", "line": 80, "callers": []},
        "file_c.py::same_name": {"name": "same_name", "file_path": "file_c.py", "line": 15, "callers": []},
    }

    merged = merge_impacts(base_impacts, head_impacts)

    assert merged["file_a.py::func_mod"]["status"] == "Modified"
    assert merged["file_a.py::func_add"]["status"] == "Added"
    assert merged["file_a.py::func_del"]["status"] == "Deleted"

    # Verify no collision between file_b.py::same_name and file_c.py::same_name
    assert "file_b.py::same_name" in merged
    assert merged["file_b.py::same_name"]["status"] == "Deleted"
    assert "file_c.py::same_name" in merged
    assert merged["file_c.py::same_name"]["status"] == "Added"


def test_generate_mermaid_graph_structure():
    merged_impacts = {
        "n3mo/core/symbol_extractor.py::_visit_generic": {
            "name": "_visit_generic",
            "file_path": "n3mo/core/symbol_extractor.py",
            "line": 237,
            "status": "Modified",
            "callers": [
                {
                    "source": "extract_generic",
                    "file_path": "n3mo/core/symbol_extractor.py",
                    "depth": 1,
                    "target": "_visit_generic",
                    "lines": [210]
                },
                {
                    "source": "extract_symbols",
                    "file_path": "n3mo/core/symbol_extractor.py",
                    "depth": 2,
                    "target": "extract_generic",
                    "lines": [86, 90, 92]
                }
            ]
        }
    }

    mermaid = generate_mermaid_graph(merged_impacts)
    assert "```mermaid" in mermaid
    assert "graph LR" in mermaid
    assert 'subgraph PR_Changes ["Modified in PR"]' in mermaid
    assert "_visit_generic" in mermaid
    assert "extract_generic" in mermaid
    assert "extract_symbols" in mermaid
    assert "-->" in mermaid
    assert "```" in mermaid


def test_format_impact_markdown_deduplicates_call_sites():
    merged_impacts = {
        "n3mo/core/symbol_extractor.py::_visit_generic": {
            "name": "_visit_generic",
            "file_path": "n3mo/core/symbol_extractor.py",
            "line": 237,
            "status": "Modified",
            "callers": [
                {
                    "source": "extract_generic",
                    "file_path": "n3mo/core/symbol_extractor.py",
                    "depth": 1,
                    "target": "_visit_generic",
                    "line": 210,
                    "lines": [210]
                },
                {
                    "source": "extract_symbols",
                    "file_path": "n3mo/core/symbol_extractor.py",
                    "depth": 2,
                    "target": "extract_generic",
                    "line": 86,
                    "lines": [86, 90, 92, 96, 100, 104, 108] # 7 call sites
                }
            ]
        }
    }

    report = format_impact_markdown(merged_impacts, "RajX-dev/N3MO", 39, 6649)

    # Direct callers count must be 1, total impacted 2
    assert "| `n3mo/core/symbol_extractor.py` | `_visit_generic` |  🟠 `Modified` | 1 | 2 |" in report

    # Check caller call sites label
    assert "extract_symbols" in report
    assert "7 call sites" in report
    assert "```mermaid" in report


def test_format_impact_markdown_empty_is_safe():
    empty_report = format_impact_markdown({}, "RajX-dev/N3MO", 39, 6649)
    assert "Safe to change" in empty_report
