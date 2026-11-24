# Copyright (C) 2026 Raj shekhar
#
# This file is part of N3MO.
# N3MO is licensed under the PolyForm Noncommercial License 1.0.0.
# You may obtain a copy of the License at
# https://polyformproject.org/licenses/noncommercial/1.0.0

import sys
import logging
import os
from typing import List, Any
from typing import List, Any, Optional

from psycopg2 import OperationalError

# Setup simple logger
logger = logging.getLogger("n3mo.mcp")

Server: Any = None
stdio_server: Any = None
types: Any = None
server: Any = None

DATABASE_UNREACHABLE_MESSAGE = (
    "N3MO database is unreachable. Please ensure you have run "
    "`docker compose up -d` in the N3MO directory."
)


def _get_db_connection():
    """Return a database connection, retrying once after starting services."""
    from n3mo.core.database import get_connection

    try:
        return get_connection()
    except OperationalError:
        try:
            from n3mo.core.run_indexer import (
                start_docker_services,
                wait_for_postgres_and_schema,
            )

            start_docker_services()
            if wait_for_postgres_and_schema(timeout=15):
                return get_connection()
        except Exception:
            logger.debug("Unable to start or reach the N3MO database", exc_info=True)

        raise OperationalError(DATABASE_UNREACHABLE_MESSAGE) from None


def _generate_single_symbol_mermaid(target_name: str, target_file: str, callers: list) -> str:
    """Generate a Mermaid flowchart for blast radius of a single target symbol."""
    if not callers:
        return ""

    def sanitize(s: str) -> str:
        return (
            s.replace('"', "'")
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('[', '(')
            .replace(']', ')')
        )

    lines = [
        "```mermaid",
        "graph LR",
        "    classDef target fill:#ef4444,stroke:#dc2626,color:#ffffff,stroke-width:2px,rx:6px,ry:6px;",
        "    classDef direct fill:#f59e0b,stroke:#d97706,color:#ffffff,stroke-width:2px,rx:6px,ry:6px;",
        "    classDef downstream fill:#3b82f6,stroke:#2563eb,color:#ffffff,stroke-width:2px,rx:6px,ry:6px;",
        '    subgraph Target ["Target Symbol"]',
        f'        t["{sanitize(target_name)}<br/><small>{sanitize(target_file)}</small>"]:::target',
        '    end'
    ]

    direct_nodes = []
    downstream_nodes = []
    edges = []

    node_id_map = {(target_file, target_name): "t"}
    node_counter = 0

    for c in callers:
        c_name = c["source"]
        c_file = c["file_path"]
        c_depth = c["depth"]
        c_key = (c_file, c_name)
        if c_key not in node_id_map:
            c_id = f"c_{node_counter}"
            node_counter += 1
            node_id_map[c_key] = c_id
        else:
            c_id = node_id_map[c_key]

        label = f'{c_id}["{sanitize(c_name)}<br/><small>{sanitize(c_file)}</small>"]'
        if c_depth == 1:
            direct_nodes.append(f"        {label}:::direct")
            edges.append(f"    t --> {c_id}")
        else:
            downstream_nodes.append(f"        {label}:::downstream")
            tgt_name = c.get("target")
            tgt_id = None
            for k, nid in node_id_map.items():
                if k[1] == tgt_name:
                    tgt_id = nid
                    break
            if tgt_id:
                edges.append(f"    {tgt_id} --> {c_id}")
            else:
                edges.append(f"    t --> {c_id}")

    if direct_nodes:
        lines.append('    subgraph Direct_Callers ["Direct Callers"]')
        lines.extend(direct_nodes)
        lines.append('    end')

    if downstream_nodes:
        lines.append('    subgraph Downstream ["Downstream Impact"]')
        lines.extend(downstream_nodes)
        lines.append('    end')

    lines.extend(sorted(set(edges)))
    lines.append("```")
    return "\n".join(lines)


try:
    from mcp.server import Server as MCPServer # type: ignore
    from mcp.server.stdio import stdio_server as MCPStdioServer # type: ignore
    import mcp.types as MCPTypes # type: ignore
    Server = MCPServer
    stdio_server = MCPStdioServer
    types = MCPTypes
except ImportError:
    logger.error("The 'mcp' SDK is not installed. Run 'pip install mcp' to use the MCP Server.")


# Define the N3MO MCP Server if library is installed
if Server is not None:
    server = Server("n3mo-server")

    @server.list_tools()
    async def handle_list_tools() -> List[types.Tool]:
        """
        List N3MO analysis tools available to the LLM agent.
        """
        return [
            types.Tool(
                name="n3mo_index",
                description="Trigger N3MO to crawl and index the active workspace folder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to workspace directory."
                        }
                    },
                    "required": ["project_path"]
                }
            ),
            types.Tool(
                name="n3mo_get_blast_radius",
                description="Query the impact analysis / blast radius of a code symbol (class or function).",
                description="Query the impact analysis / blast radius of a code symbol (class or function), returning callers and a visual dependency diagram.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol_name": {
                            "type": "string",
                            "description": "Name of the function or class to trace."
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Optional file path to disambiguate if multiple symbols have the same name."
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Traversal depth limit (default: 3).",
                            "default": 3
                        },
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to workspace directory (default: current directory)."
                        }
                    },
                    "required": ["symbol_name"]
                }
            ),
            types.Tool(
                name="n3mo_diff_impact",
                description="Analyze git diff changes against a base branch/commit to compute the blast radius and impacted callers of modified code.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "base_ref": {
                            "type": "string",
                            "description": "Base git ref to diff against (e.g. 'main', 'origin/main', 'HEAD~1'). Defaults to 'main'.",
                            "default": "main"
                        },
                        "head_ref": {
                            "type": "string",
                            "description": "Head git ref or commit (defaults to 'HEAD').",
                            "default": "HEAD"
                        },
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to workspace directory (default: current directory)."
                        }
                    }
                }
            ),
            types.Tool(
                name="n3mo_search_symbol",
                description="Search the indexed codebase for the exact location and definition of a symbol (class or function).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol_name": {
                            "type": "string",
                            "description": "Name of the function or class to search for."
                        },
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to workspace directory (default: current directory)."
                        }
                    },
                    "required": ["symbol_name"]
                }
            ),
            types.Tool(
                name="n3mo_get_dependencies",
                description="Find all external symbols that a given symbol calls (the forward-dependency graph).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol_name": {
                            "type": "string",
                            "description": "Name of the function or class to inspect."
                        },
                        "file_path": {
                            "type": "string",
                            "description": "Optional file path to disambiguate if multiple symbols have the same name."
                        },
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to workspace directory (default: current directory)."
                        }
                    },
                    "required": ["symbol_name"]
                }
            ),
            types.Tool(
                name="n3mo_get_file_symbols",
                description="List all symbols (classes/functions) defined inside a specific file.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute path to the file to inspect (or a substring match)."
                        },
                        "project_path": {
                            "type": "string",
                            "description": "Absolute path to workspace directory (default: current directory)."
                        }
                    },
                    "required": ["file_path"]
                }
            )
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> List[types.TextContent]:
        """
        Execute tool calls requested by the LLM agent.
        """

        def get_project_id(cur, project_path):
            cur.execute("SELECT id FROM projects WHERE repo_url = %s", (project_path,))
            proj = cur.fetchone()
            if not proj:
                project_name = os.path.basename(project_path)
                cur.execute("SELECT id FROM projects WHERE name = %s", (project_name,))
                proj = cur.fetchone()
            return proj[0] if proj else None

        if name == "n3mo_index":
            project_path = arguments.get("project_path") or os.getenv("TARGET_CODE_DIR") or os.getcwd()
            if not project_path:
                return [types.TextContent(type="text", text="Error: project_path is required.")]
            

            try:
                from n3mo.core.run_indexer import run_indexer_for_path
                success, message = run_indexer_for_path(project_path)
                return [types.TextContent(type="text", text=message)]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Error indexing workspace: {e}")]

        elif name == "n3mo_get_blast_radius":
            symbol_name = arguments.get("symbol_name")
            file_path = arguments.get("file_path")
            depth = arguments.get("depth", 3)
            project_path = arguments.get("project_path") or os.getenv("TARGET_CODE_DIR") or os.getcwd()

            from n3mo.core.database import release_connection
            conn = None
            try:
                conn = _get_db_connection()
            except OperationalError:
                return [types.TextContent(type="text", text=DATABASE_UNREACHABLE_MESSAGE)]
            except Exception as ex:
                return [types.TextContent(type="text", text=f"Error: {ex}")]

            try:
                with conn.cursor() as cur:
                    project_id = get_project_id(cur, project_path)
                    if not project_id:
                        return [types.TextContent(type="text", text=f"Error: No index found for '{project_path}'. Run the indexer tool first.")]

                    cur.execute(
                        "SELECT id, name, file_path, start_line FROM symbols WHERE name = %s AND project_id = %s LIMIT 1",
                        (symbol_name, project_id)
                    )
                    target = cur.fetchone()
                    if not target:
                    if file_path:
                        norm_fpath = file_path.replace('\\', '/')
                        cur.execute(
                            """
                            SELECT id, name, file_path, start_line
                            FROM symbols
                            WHERE name = %s AND project_id = %s
                              AND (file_path = %s OR replace(file_path, '\\', '/') LIKE %s)
                            ORDER BY start_line ASC
                            """,
                            (symbol_name, project_id, file_path, f"%{norm_fpath}%")
                        )
                    else:
                        cur.execute(
                            "SELECT id, name, file_path, start_line FROM symbols WHERE name = %s AND project_id = %s ORDER BY file_path, start_line ASC",
                            (symbol_name, project_id)
                        )
                    targets = cur.fetchall()

                    if not targets:
                        return [
                            types.TextContent(
                                type="text",
                                text=f"Symbol '{symbol_name}' not found in the index for this workspace."
                            )
                        ]
                    target_id, real_name, target_file, target_start_line = target

                    if len(targets) > 1 and not file_path:
                        candidates = "\n".join(f"- `{name}` at `{fpath}:{sline}`" for _, name, fpath, sline in targets)
                        return [
                            types.TextContent(
                                type="text",
                                text=f"Found {len(targets)} symbols named '{symbol_name}'. Please specify 'file_path' to choose one:\n{candidates}"
                            )
                        ]

                    target_id, real_name, target_file, target_start_line = targets[0]

                    query = """
                    WITH RECURSIVE impact_chain AS (
                        SELECT s.name AS source, s.file_path, c.line_number, 1 AS depth, target_sym.name AS target, c.source_symbol_id AS source_id,
                               ARRAY[c.source_symbol_id] AS path,
                               FALSE AS cycle
                        -- Direct callers (depth 1)
                        SELECT 
                            c.source_symbol_id AS source_id,
                            s.name AS source_name,
                            s.file_path AS source_file,
                            c.resolved_symbol_id AS target_id,
                            target_sym.name AS target_name,
                            1 AS depth,
                            ARRAY[c.source_symbol_id] AS path,
                            FALSE AS cycle
                        FROM calls c
                        JOIN symbols s ON c.source_symbol_id = s.id
                        JOIN symbols target_sym ON c.resolved_symbol_id = target_sym.id
                        WHERE c.resolved_symbol_id = %s
                          AND c.source_symbol_id != %s
                        GROUP BY c.source_symbol_id, s.name, s.file_path, c.resolved_symbol_id, target_sym.name

                        UNION ALL
                        SELECT s.name, s.file_path, c.line_number, ic.depth + 1, ic.source, c.source_symbol_id,
                               ic.path || c.source_symbol_id,
                               c.source_symbol_id = ANY(ic.path)

                        -- Downstream callers
                        SELECT 
                            c.source_symbol_id AS source_id,
                            s.name AS source_name,
                            s.file_path AS source_file,
                            ic.source_id AS target_id,
                            ic.source_name AS target_name,
                            ic.depth + 1 AS depth,
                            ic.path || c.source_symbol_id,
                            c.source_symbol_id = ANY(ic.path)
                        FROM impact_chain ic
                        JOIN calls c ON c.resolved_symbol_id = ic.source_id
                        JOIN symbols s ON c.source_symbol_id = s.id
                        WHERE ic.depth < %s + 1 AND NOT ic.cycle
                        WHERE ic.depth < %s
                          AND NOT ic.cycle
                          AND c.source_symbol_id != ic.source_id
                          AND NOT (c.source_symbol_id = ANY(ic.path))
                        GROUP BY c.source_symbol_id, s.name, s.file_path, ic.source_id, ic.source_name, ic.depth, ic.path
                    )
                    SELECT DISTINCT source, file_path, line_number, depth, target
                    FROM impact_chain WHERE NOT cycle ORDER BY depth ASC, file_path;
                    SELECT 
                        source_id,
                        source_name,
                        source_file,
                        target_id,
                        target_name,
                        depth
                    FROM impact_chain
                    WHERE NOT cycle
                    ORDER BY depth ASC, source_file, source_name;
                    """
                    cur.execute(query, (target_id, depth))
                    results = cur.fetchall()
                    cur.execute(query, (target_id, target_id, depth))
                    chain_rows = cur.fetchall()

                    if not results:
                    if not chain_rows:
                        return [
                            types.TextContent(
                                type="text",
                                text=f"Impact Analysis for '{real_name}' (located in {target_file}:{target_start_line}):\n"
                                text=f"◈ IMPACT ANALYSIS FOR: {real_name}\n"
                                     f"  Location: {target_file}:{target_start_line}\n"
                                     f"  Depth: <= {depth}\n"
                                     f"{'=' * 60}\n"
                                     f"Safe to change - no callers found in the database."
                            )
                        ]

                    # Format the results
                    sorted_results = sorted(results, key=lambda x: (x[3], x[1]))
                    direct = [r for r in sorted_results if r[3] == 1]
                    ripple = [r for r in sorted_results if r[3] > 1]
                    caller_map = {}
                    for (src_id, src_name, src_file, tgt_id, tgt_name, d) in chain_rows:
                        src_key = (src_file, src_name)
                        if src_key not in caller_map or d < caller_map[src_key]["depth"]:
                            caller_map[src_key] = {
                                "source_id": str(src_id),
                                "source": src_name,
                                "file_path": src_file,
                                "target_id": str(tgt_id),
                                "target": tgt_name,
                                "depth": d,
                                "lines": []
                            }

                    src_ids = list({row[0] for row in chain_rows})
                    tgt_ids = list({row[3] for row in chain_rows})
                    cur.execute(
                        """
                        SELECT source_symbol_id, resolved_symbol_id, line_number
                        FROM calls
                        WHERE source_symbol_id = ANY(%s) AND resolved_symbol_id = ANY(%s)
                        ORDER BY line_number
                        """,
                        (src_ids, tgt_ids)
                    )
                    for (s_id, t_id, line_no) in cur.fetchall():
                        for caller in caller_map.values():
                            if caller["source_id"] == str(s_id) and caller["target_id"] == str(t_id):
                                if line_no and line_no not in caller["lines"]:
                                    caller["lines"].append(line_no)

                    formatted_callers = sorted(caller_map.values(), key=lambda x: (x["depth"], x["file_path"], x["source"]))
                    direct = [c for c in formatted_callers if c["depth"] == 1]
                    ripple = [c for c in formatted_callers if c["depth"] > 1]

                    output_lines = []
                    output_lines.append(f"◈ IMPACT ANALYSIS FOR: {real_name}")
                    output_lines.append(f"  Location: {target_file}:{target_start_line}")
                    output_lines.append(f"  Depth: <= {depth}")
                    output_lines.append("=" * 60)

                    if direct:
                        output_lines.append(f"\n◉ Direct Callers ({len(set(r[0] for r in direct))} symbols):")
                        seen_direct = set()
                        for source, path, line, d, t in direct:
                            if source in seen_direct:
                                continue
                            seen_direct.add(source)
                            output_lines.append(f"  ▸ {source:<28} {path}:{line}")
                        output_lines.append(f"\n◉ Direct Callers ({len(direct)} unique symbols):")
                        for c in direct:
                            lines_preview = ', '.join(str(l) for l in c['lines'][:5])
                            if len(c['lines']) > 5:
                                lines_preview += '...'
                            line_label = f" — {len(c['lines'])} call site{'s' if len(c['lines']) != 1 else ''} (lines: {lines_preview})" if c['lines'] else ""
                            output_lines.append(f"  ▸ {c['source']:<28} {c['file_path']}{line_label}")

                    if ripple:
                        output_lines.append(f"\n◎ Ripple Effects ({len(set(r[0] for r in ripple))} symbols):")
                        seen_ripple = set()
                        for source, path, line, d, t in ripple:
                            key = (source, path, line)
                            if key in seen_ripple:
                                continue
                            seen_ripple.add(key)
                            indent = "    " * (d - 1)
                            output_lines.append(f"  {indent}╰─▸ {source:<26} {path}:{line}")
                        output_lines.append(f"\n◎ Downstream Ripple Effects ({len(ripple)} unique symbols):")
                        for c in ripple:
                            indent = "    " * (c["depth"] - 1)
                            lines_preview = ', '.join(str(l) for l in c['lines'][:5])
                            if len(c['lines']) > 5:
                                lines_preview += '...'
                            line_label = f" — {len(c['lines'])} call site{'s' if len(c['lines']) != 1 else ''} (lines: {lines_preview})" if c['lines'] else ""
                            output_lines.append(f"  {indent}╰─▸ {c['source']:<26} {c['file_path']}{line_label}")

                    output_lines.append("=" * 60)
                    total_refs = len(set((r[0], r[1], r[2]) for r in sorted_results))
                    output_lines.append(f"Total impacted: {total_refs} references")
                    output_lines.append(f"Total impacted unique callers: {len(formatted_callers)}")

                    mermaid_chart = _generate_single_symbol_mermaid(real_name, target_file, formatted_callers)
                    if mermaid_chart:
                        output_lines.append("\n" + mermaid_chart)

                    return [types.TextContent(type="text", text="\n".join(output_lines))]

            except Exception as e:
                return [types.TextContent(type="text", text=f"Error running impact analysis: {e}")]
            finally:
                if conn:
                    release_connection(conn)

        elif name == "n3mo_diff_impact":
            base_ref = arguments.get("base_ref") or "main"
            head_ref = arguments.get("head_ref") or "HEAD"
            project_path = arguments.get("project_path") or os.getenv("TARGET_CODE_DIR") or os.getcwd()

            from n3mo.core.database import release_connection
            from n3mo.core.core_engine import (
                parse_diff_hunks,
                get_impact_for_changed_files,
                merge_impacts,
                format_impact_markdown
            )

            conn = None
            try:
                conn = _get_db_connection()
            except OperationalError:
                return [types.TextContent(type="text", text=DATABASE_UNREACHABLE_MESSAGE)]
            except Exception as ex:
                return [types.TextContent(type="text", text=f"Error: {ex}")]

            try:
                with conn.cursor() as cur:
                    project_id = get_project_id(cur, project_path)
                    if not project_id:
                        return [types.TextContent(type="text", text=f"Error: No index found for '{project_path}'. Run n3mo_index first.")]

                    try:
                        diff_info = parse_diff_hunks(project_path, base_ref, head_ref)
                    except Exception as diff_err:
                        return [types.TextContent(type="text", text=f"Git diff failed between '{base_ref}' and '{head_ref}': {diff_err}")]

                    changed_files = diff_info.get("changed_files", [])
                    if not changed_files:
                        return [types.TextContent(type="text", text=f"✓ No code differences detected between '{base_ref}' and '{head_ref}'.")]

                    base_impacts = get_impact_for_changed_files(
                        project_id,
                        changed_files,
                        file_line_ranges=diff_info.get("base_ranges", {}),
                        added_files=diff_info.get("added_files", set()),
                        deleted_files=diff_info.get("deleted_files", set()),
                        is_head=False
                    )

                    head_impacts = get_impact_for_changed_files(
                        project_id,
                        changed_files,
                        file_line_ranges=diff_info.get("head_ranges", {}),
                        added_files=diff_info.get("added_files", set()),
                        deleted_files=diff_info.get("deleted_files", set()),
                        is_head=True
                    )

                    merged = merge_impacts(base_impacts, head_impacts)
                    report = format_impact_markdown(merged, os.path.basename(project_path), 0, 0)
                    return [types.TextContent(type="text", text=report)]

            except Exception as e:
                return [types.TextContent(type="text", text=f"Error analyzing diff impact: {e}")]
            finally:
                if conn:
                    release_connection(conn)

        elif name == "n3mo_search_symbol":
            symbol_name = arguments.get("symbol_name")
            project_path = arguments.get("project_path") or os.getenv("TARGET_CODE_DIR") or os.getcwd()
            from n3mo.core.database import release_connection
            conn = None
            try:
                conn = _get_db_connection()
            except OperationalError:
                return [types.TextContent(type="text", text=DATABASE_UNREACHABLE_MESSAGE)]
            except Exception as ex:
                return [types.TextContent(type="text", text=f"Error: {ex}")]
            try:
                with conn.cursor() as cur:
                    project_id = get_project_id(cur, project_path)
                    if not project_id:
                        return [types.TextContent(type="text", text=f"Error: No index found for '{project_path}'. Run the indexer tool first.")]
                    

                    cur.execute(
                        "SELECT name, file_path, kind, signature, start_line FROM symbols WHERE name = %s AND project_id = %s",
                        (symbol_name, project_id)
                    )
                    results = cur.fetchall()
                    if not results:
                        return [types.TextContent(type="text", text=f"Symbol '{symbol_name}' not found.")]
                    

                    out = [f"Found {len(results)} definitions for '{symbol_name}':"]
                    for sym_name, file_path, kind, sig, line in results:
                        out.append(f"- {kind} {sym_name} at {file_path}:{line}")
                        if sig:
                            out.append(f"  Signature: {sig}")
                    return [types.TextContent(type="text", text="\n".join(out))]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Error searching symbol: {e}")]
            finally:
                if conn:
                    release_connection(conn)

        elif name == "n3mo_get_dependencies":
            symbol_name = arguments.get("symbol_name")
            file_path = arguments.get("file_path")
            project_path = arguments.get("project_path") or os.getenv("TARGET_CODE_DIR") or os.getcwd()
            from n3mo.core.database import release_connection
            conn = None
            try:
                conn = _get_db_connection()
            except OperationalError:
                return [types.TextContent(type="text", text=DATABASE_UNREACHABLE_MESSAGE)]
            except Exception as ex:
                return [types.TextContent(type="text", text=f"Error: {ex}")]
            try:
                with conn.cursor() as cur:
                    project_id = get_project_id(cur, project_path)
                    if not project_id:
                        return [types.TextContent(type="text", text=f"Error: No index found for '{project_path}'. Run the indexer tool first.")]
                    
                    cur.execute(
                        "SELECT id, file_path, start_line FROM symbols WHERE name = %s AND project_id = %s LIMIT 1",
                        (symbol_name, project_id)
                    )
                    target = cur.fetchone()
                    if not target:

                    if file_path:
                        norm_fpath = file_path.replace('\\', '/')
                        cur.execute(
                            """
                            SELECT id, file_path, start_line, name
                            FROM symbols
                            WHERE name = %s AND project_id = %s
                              AND (file_path = %s OR replace(file_path, '\\', '/') LIKE %s)
                            ORDER BY start_line ASC
                            """,
                            (symbol_name, project_id, file_path, f"%{norm_fpath}%")
                        )
                    else:
                        cur.execute(
                            "SELECT id, file_path, start_line, name FROM symbols WHERE name = %s AND project_id = %s ORDER BY file_path, start_line ASC",
                            (symbol_name, project_id)
                        )
                    targets = cur.fetchall()

                    if not targets:
                        return [types.TextContent(type="text", text=f"Symbol '{symbol_name}' not found.")]
                    target_id, target_file, target_line = target

                    if len(targets) > 1 and not file_path:
                        candidates = "\n".join(f"- `{name}` at `{fpath}:{sline}`" for _, fpath, sline, name in targets)
                        return [
                            types.TextContent(
                                type="text",
                                text=f"Found {len(targets)} symbols named '{symbol_name}'. Please specify 'file_path' to choose one:\n{candidates}"
                            )
                        ]

                    target_id, target_file, target_line, real_name = targets[0]

                    query = '''
                    SELECT c.call_name, c.line_number, s.file_path, s.name, s.kind
                    FROM calls c
                    LEFT JOIN symbols s ON c.resolved_symbol_id = s.id
                    WHERE c.source_symbol_id = %s
                    ORDER BY c.line_number ASC
                    '''
                    cur.execute(query, (target_id,))
                    results = cur.fetchall()

                    if not results:
                        return [types.TextContent(type="text", text=f"'{symbol_name}' makes no external calls (or none were resolved).")]
                    
                    out = [f"Dependencies called by '{symbol_name}' ({target_file}:{target_line}):"]
                        return [types.TextContent(type="text", text=f"'{real_name}' ({target_file}:{target_line}) makes no external calls (or none were resolved).")]

                    out = [f"Dependencies called by '{real_name}' ({target_file}:{target_line}):"]
                    for call_name, line, resolved_file, resolved_name, resolved_kind in results:
                        if resolved_name:
                            out.append(f"- Line {line}: Calls {resolved_kind} '{resolved_name}' (resolved to {resolved_file})")
                        else:
                            out.append(f"- Line {line}: Calls '{call_name}' (unresolved)")
                    return [types.TextContent(type="text", text="\n".join(out))]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Error getting dependencies: {e}")]
            finally:
                if conn:
                    release_connection(conn)

        elif name == "n3mo_get_file_symbols":
            file_path = arguments.get("file_path")
            project_path = arguments.get("project_path") or os.getenv("TARGET_CODE_DIR") or os.getcwd()
            from n3mo.core.database import release_connection
            conn = None
            try:
                conn = _get_db_connection()
            except OperationalError:
                return [types.TextContent(type="text", text=DATABASE_UNREACHABLE_MESSAGE)]
            except Exception as ex:
                return [types.TextContent(type="text", text=f"Error: {ex}")]
            try:
                with conn.cursor() as cur:
                    project_id = get_project_id(cur, project_path)
                    if not project_id:
                        return [types.TextContent(type="text", text=f"Error: No index found for '{project_path}'. Run the indexer tool first.")]
                    

                    cur.execute(
                        "SELECT name, kind, signature, start_line, end_line FROM symbols WHERE file_path LIKE %s AND project_id = %s ORDER BY start_line ASC",
                        ('%' + str(file_path) + '%', project_id)
                    )
                    results = cur.fetchall()
                    

                    if not results:
                        return [types.TextContent(type="text", text=f"No symbols found in file matching '{file_path}'.")]
                    

                    out = [f"Symbols defined in '{file_path}':"]
                    for name, kind, sig, start, end in results:
                        line_info = f"L{start}-L{end}" if end else f"L{start}"
                        out.append(f"- [{line_info}] {kind} {name}")
                        if sig:
                            out.append(f"  {sig}")
                    return [types.TextContent(type="text", text="\n".join(out))]
            except Exception as e:
                return [types.TextContent(type="text", text=f"Error getting file symbols: {e}")]
            finally:
                if conn:
                    release_connection(conn)

        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server over stdio transport."""
    if Server is None or stdio_server is None:
        print("Error: MCP SDK not installed. Please run 'pip install mcp' first.", file=sys.stderr)
        sys.exit(1)

    if sys.stdin.isatty():
        print("\n\033[1;33m⚠️  N3MO MCP Server - Interactive Terminal Warning\033[0m", file=sys.stderr)
        print("----------------------------------------------------------------", file=sys.stderr)
        print("The MCP server runs over STDIO transport, which expects a JSON-RPC", file=sys.stderr)
        print("host (like Cursor or Claude Desktop) and cannot be run interactively.", file=sys.stderr)
        print("\nTo integrate with Cursor:", file=sys.stderr)
        print("  1. Open Cursor settings: Settings -> Models -> MCP", file=sys.stderr)
        print("  2. Add a new MCP server:", file=sys.stderr)
        print("     - Name: n3mo", file=sys.stderr)
        print("     - Type: command", file=sys.stderr)
        print(f"     - Command: {sys.executable} -m n3mo.mcp_server", file=sys.stderr)
        print("\nTo automatically register with Cursor and Claude Desktop, run:", file=sys.stderr)
        print("  \033[1;36mn3mo mcp install\033[0m\n", file=sys.stderr)
        sys.exit(1)

    logger.info("Starting N3MO MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
