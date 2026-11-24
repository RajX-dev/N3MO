import sys
import pytest
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import patch, MagicMock

import pytest
from psycopg2 import OperationalError

from n3mo.mcp.mcp_server import DATABASE_UNREACHABLE_MESSAGE, _get_db_connection
from n3mo.mcp.mcp_server import (
    DATABASE_UNREACHABLE_MESSAGE,
    _get_db_connection,
    _generate_single_symbol_mermaid,
    handle_list_tools,
    handle_call_tool,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_get_db_connection_returns_friendly_error_when_database_is_unreachable():
    run_indexer = SimpleNamespace(
        start_docker_services=lambda: None,
        wait_for_postgres_and_schema=lambda timeout: False,
    )

    with (
        patch(
            "n3mo.core.database.get_connection",
            side_effect=OperationalError("connection refused"),
        ),
        patch.dict(sys.modules, {"n3mo.core.run_indexer": run_indexer}),
    ):
        with pytest.raises(OperationalError, match="N3MO database is unreachable") as exc_info:
            _get_db_connection()

    assert str(exc_info.value) == DATABASE_UNREACHABLE_MESSAGE


def test_generate_single_symbol_mermaid_syntax():
    callers = [
        {"source": "extract_generic", "file_path": "symbol_extractor.py", "depth": 1, "target": "_visit_generic"},
        {"source": "extract_symbols", "file_path": "symbol_extractor.py", "depth": 2, "target": "extract_generic"},
    ]
    chart = _generate_single_symbol_mermaid("_visit_generic", "symbol_extractor.py", callers)

    assert "```mermaid" in chart
    assert "graph LR" in chart
    assert "t[\"_visit_generic" in chart
    assert "subgraph Direct_Callers" in chart
    assert "subgraph Downstream" in chart
    assert "```" in chart


@pytest.mark.anyio
async def test_handle_list_tools_contains_all_tools_and_diff_impact():
    tools = await handle_list_tools()
    tool_names = [t.name for t in tools]

    assert "n3mo_index" in tool_names
    assert "n3mo_get_blast_radius" in tool_names
    assert "n3mo_diff_impact" in tool_names
    assert "n3mo_search_symbol" in tool_names
    assert "n3mo_get_dependencies" in tool_names
    assert "n3mo_get_file_symbols" in tool_names

    # Check that file_path is present in n3mo_get_blast_radius schema
    blast_tool = next(t for t in tools if t.name == "n3mo_get_blast_radius")
    assert "file_path" in blast_tool.inputSchema["properties"]


@pytest.mark.anyio
async def test_blast_radius_prompts_for_file_path_on_ambiguity():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_cur.fetchone.side_effect = [("proj-1",)]
    mock_cur.fetchall.side_effect = [
        [
            ("id-1", "execute", "commands/run.py", 10),
            ("id-2", "execute", "commands/build.py", 25),
        ]
    ]

    with patch("n3mo.mcp.mcp_server._get_db_connection", return_value=mock_conn), \
         patch("n3mo.core.database.release_connection"):
        result = await handle_call_tool(
            "n3mo_get_blast_radius",
            {"symbol_name": "execute", "project_path": "."}
        )

    text = result[0].text
    assert "Found 2 symbols named 'execute'" in text
    assert "Please specify 'file_path'" in text
    assert "commands/run.py:10" in text
    assert "commands/build.py:25" in text


@pytest.mark.anyio
async def test_blast_radius_disambiguates_with_file_path_and_deduplicates():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_cur.fetchone.side_effect = [("proj-1",)]
    mock_cur.fetchall.side_effect = [
        # Target lookup
        [("id-1", "execute", "commands/run.py", 10)],
        # CTE chain rows (depth 1 direct caller, depth 2 downstream)
        [
            ("src-1", "caller_one", "main.py", "id-1", "execute", 1),
            ("src-2", "caller_two", "cli.py", "src-1", "caller_one", 2),
        ],
        # Call lines for (src-1, src-2)
        [
            ("src-1", "id-1", 42),
            ("src-1", "id-1", 45),  # 2 call sites for src-1
            ("src-2", "src-1", 100),
        ]
    ]

    with patch("n3mo.mcp.mcp_server._get_db_connection", return_value=mock_conn), \
         patch("n3mo.core.database.release_connection"):
        result = await handle_call_tool(
            "n3mo_get_blast_radius",
            {"symbol_name": "execute", "file_path": "commands/run.py", "project_path": "."}
        )

    text = result[0].text
    assert "◈ IMPACT ANALYSIS FOR: execute" in text
    assert "Direct Callers (1 unique symbols):" in text
    assert "2 call sites (lines: 42, 45)" in text
    assert "Downstream Ripple Effects (1 unique symbols):" in text
    assert "```mermaid" in text


@pytest.mark.anyio
async def test_diff_impact_tool_execution():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.side_effect = [("proj-1",)]

    diff_info = {
        "changed_files": ["core.py"],
        "head_ranges": {"core.py": [(10, 20)]},
        "base_ranges": {"core.py": [(10, 20)]},
        "added_files": set(),
        "deleted_files": set(),
    }

    base_impacts = {
        "core.py::my_func": {
            "name": "my_func",
            "file_path": "core.py",
            "line": 10,
            "callers": [],
        }
    }
    head_impacts = {
        "core.py::my_func": {
            "name": "my_func",
            "file_path": "core.py",
            "line": 10,
            "callers": [
                {
                    "source": "api_handler",
                    "file_path": "api.py",
                    "depth": 1,
                    "target": "my_func",
                    "line": 50,
                    "lines": [50],
                }
            ],
        }
    }

    with patch("n3mo.mcp.mcp_server._get_db_connection", return_value=mock_conn), \
         patch("n3mo.core.database.release_connection"), \
         patch("n3mo.core.core_engine.parse_diff_hunks", return_value=diff_info), \
         patch("n3mo.core.core_engine.get_impact_for_changed_files", side_effect=[base_impacts, head_impacts]):

        result = await handle_call_tool(
            "n3mo_diff_impact",
            {"base_ref": "main", "project_path": "."}
        )

    text = result[0].text
    assert "◈ N3MO Pull Request Impact Analysis" in text
    assert "my_func" in text
    assert "Modified" in text
    assert "```mermaid" in text
