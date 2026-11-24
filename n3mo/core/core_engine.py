# Copyright (C) 2026 Raj shekhar
#
# This file is part of N3MO.
# N3MO is licensed under the PolyForm Noncommercial License 1.0.0.
# You may obtain a copy of the License at
# https://polyformproject.org/licenses/noncommercial/1.0.0

import os
import re
import logging
import subprocess
import urllib.request
import urllib.error
import json

from n3mo.core.crawler import crawl_directory
from n3mo.core.database import get_connection, release_connection

logger = logging.getLogger("n3mo.core_engine")


def get_workspace_dir(repo_name: str) -> str:
    workspace_root = os.getenv('N3MO_WORKSPACE_DIR', os.path.join(os.getcwd(), 'n3mo_workspaces'))
    return os.path.abspath(os.path.join(workspace_root, repo_name.replace('/', '_')))


def calculate_repo_loc(repo_dir: str) -> int:
    files = crawl_directory(repo_dir)
    total_lines = 0
    for fpath in files:
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                total_lines += sum(1 for _ in f)
        except Exception:
            pass
    return total_lines


def checkout_repo(clone_url: str, repo_name: str, sha: str) -> str:
    repo_dir = get_workspace_dir(repo_name)
    os.makedirs(os.path.dirname(repo_dir), exist_ok=True)
    if not os.path.exists(repo_dir):
        logger.info(f'Cloning {clone_url} to {repo_dir}...')
        subprocess.run(['git', 'clone', clone_url, repo_dir], check=True)
    else:
        logger.info(f'Fetching updates for {repo_name}...')
        subprocess.run(['git', 'fetch', 'origin'], cwd=repo_dir, check=True)
    logger.info(f'Checking out {sha}...')
    subprocess.run(['git', 'checkout', '-f', sha], cwd=repo_dir, check=True)
    return repo_dir


def get_changed_files(repo_dir: str, base_sha: str, head_sha: str) -> list:
    res = subprocess.run(
        ['git', 'diff', '--name-only', base_sha, head_sha],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True
    )
    return [line.strip().replace('\\', '/') for line in res.stdout.splitlines() if line.strip()]


def parse_diff_hunks(repo_dir: str, base_sha: str, head_sha: str) -> dict:
    """
    Parses git diff -U0 to determine modified line ranges per file for base and head commits.
    Returns:
    {
        "changed_files": list[str],
        "head_ranges": dict[str, list[tuple[int, int]]],
        "base_ranges": dict[str, list[tuple[int, int]]],
        "added_files": set[str],
        "deleted_files": set[str]
    }
    """
    try:
        res = subprocess.run(
            ['git', 'diff', '-U0', '--no-color', base_sha, head_sha],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True
        )
    except Exception as e:
        logger.error(f"Failed to execute git diff: {e}")
        changed = get_changed_files(repo_dir, base_sha, head_sha)
        return {
            "changed_files": changed,
            "head_ranges": {},
            "base_ranges": {},
            "added_files": set(),
            "deleted_files": set()
        }

    head_ranges = {}
    base_ranges = {}
    added_files = set()
    deleted_files = set()
    changed_files_set = set()

    curr_base_file = None
    curr_head_file = None

    hunk_regex = re.compile(r'^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@')

    for line in res.stdout.splitlines():
        if line.startswith('--- '):
            raw = line[4:].strip()
            if raw == '/dev/null':
                curr_base_file = None
            elif raw.startswith('a/'):
                curr_base_file = raw[2:].replace('\\', '/')
            else:
                curr_base_file = raw.replace('\\', '/')
            continue

        if line.startswith('+++ '):
            raw = line[4:].strip()
            if raw == '/dev/null':
                curr_head_file = None
                if curr_base_file:
                    deleted_files.add(curr_base_file)
                    changed_files_set.add(curr_base_file)
            elif raw.startswith('b/'):
                curr_head_file = raw[2:].replace('\\', '/')
                if curr_base_file is None:
                    added_files.add(curr_head_file)
                changed_files_set.add(curr_head_file)
            else:
                curr_head_file = raw.replace('\\', '/')
                changed_files_set.add(curr_head_file)
            continue

        m = hunk_regex.match(line)
        if m:
            old_start = int(m.group(1))
            old_count = int(m.group(2)) if m.group(2) is not None else 1
            new_start = int(m.group(3))
            new_count = int(m.group(4)) if m.group(4) is not None else 1

            if curr_base_file:
                if old_count > 0:
                    base_ranges.setdefault(curr_base_file, []).append((old_start, old_start + old_count - 1))
                else:
                    base_ranges.setdefault(curr_base_file, []).append((old_start, old_start))

            if curr_head_file:
                if new_count > 0:
                    head_ranges.setdefault(curr_head_file, []).append((new_start, new_start + new_count - 1))
                else:
                    head_ranges.setdefault(curr_head_file, []).append((new_start, new_start))

    return {
        "changed_files": sorted(list(changed_files_set)),
        "head_ranges": head_ranges,
        "base_ranges": base_ranges,
        "added_files": added_files,
        "deleted_files": deleted_files
    }


def get_changed_files_with_hunks(repo_dir: str, base_sha: str, head_sha: str) -> dict:
    return parse_diff_hunks(repo_dir, base_sha, head_sha)


def get_project_id(repo_dir: str):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM projects WHERE repo_url = %s', (repo_dir,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        release_connection(conn)


def get_impact_for_changed_files(
    project_id,
    changed_files: list,
    file_line_ranges: dict = None,
    added_files: set = None,
    deleted_files: set = None,
    is_head: bool = True
) -> dict:
    if not project_id or not changed_files:
        return {}
    conn = get_connection()
    impacts = {}
    try:
        norm_changed = [f.replace('\\', '/') for f in changed_files]
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, file_path, start_line, end_line
                FROM symbols
                WHERE project_id = %s
                  AND (file_path = ANY(%s) vR replace(file_path, '\\', '/') = ANY(%s))
                """,
                (project_id, changed_files, norm_changed)
            )
            symbols = cur.fetchall()

            symbols_to_analyze = []
            for (sym_id, name, file_path, start_line, end_line) in symbols:
                norm_path = file_path.replace('\\', '/')

                if file_line_ranges is None:
                    # Fallback mode: analyze all symbols in changed files
                    symbols_to_analyze.append((sym_id, name, file_path, start_line))
                    continue

                if is_head and added_files and norm_path in added_files:
                    symbols_to_analyze.append((sym_id, name, file_path, start_line))
                    continue

                if not is_head and deleted_files and norm_path in deleted_files:
                    symbols_to_analyze.append((sym_id, name, file_path, start_line))
                    continue

                ranges = file_line_ranges.get(norm_path, [])
                if not ranges:
                    continue

                s_start = start_line or 0
                s_end = end_line if (end_line is not None and end_line > 0) else s_start

                overlaps = any(s_start <= h_end and s_end >= h_start for h_start, h_end in ranges)
                if overlaps:
                    symbols_to_analyze.append((sym_id, name, file_path, start_line))

            for (sym_id, name, file_path, start_line) in symbols_to_analyze:
                query = """
                WITH RECURSIVE impact_chain AS (
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

                    -- Downstream callers (depth > 1)
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
                    WHERE ic.depth < 3
                      AND NOT ic.cycle
                      AND c.source_symbol_id != ic.source_id
                      AND NOT (c.source_symbol_id = ANY(ic.path))
                    GROUP BY c.source_symbol_id, s.name, s.file_path, ic.source_id, ic.source_name, ic.depth, ic.path
                )
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
                cur.execute(query, (sym_id, sym_id))
                chain_rows = cur.fetchall()

                # Deduplicate callers by (source_file, source_name)
                caller_map = {}
                for (src_id, src_name, src_file, tgt_id, tgt_name, depth) in chain_rows:
                    src_key = (src_file, src_name)
                    if src_key not in caller_map or depth < caller_map[src_key]["depth"]:
                        caller_map[src_key] = {
                            "source_id": str(src_id),
                            "source": src_name,
                            "file_path": src_file,
                            "target_id": str(tgt_id),
                            "target": tgt_name,
                            "depth": depth,
                            "lines": []
                        }

                if caller_map:
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

                formatted_callers = []
                for c in sorted(caller_map.values(), key=lambda x: (x["depth"], x["file_path"], x["source"])):
                    c["line"] = c["lines"][0] if c["lines"] else 0
                    formatted_callers.append(c)

                sym_key = f"{file_path}::{name}"
                impacts[sym_key] = {
                    "name": name,
                    "file_path": file_path,
                    "line": start_line,
                    "callers": formatted_callers
                }
    finally:
        release_connection(conn)
    return impacts


def merge_impacts(base_impacts: dict, head_impacts: dict) -> dict:
    merged = {}
    all_keys = set(base_impacts.keys()) | set(head_impacts.keys())
    for key in all_keys:
        in_base = key in base_impacts
        in_head = key in head_impacts
        if in_base and in_head:
            status = 'Modified'
            data = head_impacts[key]
        elif in_head:
            status = 'Added'
            data = head_impacts[key]
        else:
            status = 'Deleted'
            data = base_impacts[key]

        name = data.get('name') or key.split('::')[-1]
        file_path = data.get('file_path') or (key.split('::')[0] if '::' in key else '')
        merged[key] = {
            'name': name,
            'status': status,
            'file_path': file_path,
            'line': data.get('line', 0),
            'callers': data.get('callers', [])
        }
    return merged


def generate_mermaid_graph(merged_impacts: dict, max_nodes: int = 25) -> str:
    if not merged_impacts:
        return ""

    def sanitize(s: str) -> str:
        return (
            s.replace('"', "'")
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('[', '(')
            .replace(']', ')')
        )

    changed_nodes = []
    direct_nodes = {}
    downstream_nodes = {}
    edges = set()

    node_counter = 0
    node_id_map = {}

    for key, data in merged_impacts.items():
        name = data['name']
        fpath = data['file_path']
        status = data['status']
        node_id = f"m_{node_counter}"
        node_counter += 1
        node_id_map[(fpath, name)] = node_id
        changed_nodes.append((node_id, sanitize(name), sanitize(fpath), status))

        for c in data.get('callers', []):
            c_name = c['source']
            c_fpath = c['file_path']
            c_depth = c['depth']
            c_key = (c_fpath, c_name)

            if c_key not in node_id_map:
                c_id = f"c_{node_counter}"
                node_counter += 1
                node_id_map[c_key] = c_id
            else:
                c_id = node_id_map[c_key]

            if c_depth == 1:
                direct_nodes[c_key] = (c_id, sanitize(c_name), sanitize(c_fpath))
                edges.add((node_id, c_id))
            else:
                downstream_nodes[c_key] = (c_id, sanitize(c_name), sanitize(c_fpath))
                tgt_name = c.get('target')
                tgt_id = None
                for k, nid in node_id_map.items():
                    if k[1] == tgt_name:
                        tgt_id = nid
                        break
                if tgt_id:
                    edges.add((tgt_id, c_id))
                else:
                    edges.add((node_id, c_id))

    total_nodes = len(changed_nodes) + len(direct_nodes) + len(downstream_nodes)
    if total_nodes > max_nodes:
        excess = total_nodes - max_nodes
        downstream_items = list(downstream_nodes.items())
        retained_downstream = dict(downstream_items[:-excess] if excess < len(downstream_items) else [])
        downstream_nodes = retained_downstream
        valid_ids = {nid for nid, _, _, _ in changed_nodes} | {nid for nid, _, _ in direct_nodes.values()} | {nid for nid, _, _ in downstream_nodes.values()}
        edges = {(u, v) for u, v in edges if u in valid_ids and v in valid_ids}

    lines = [
        "```mermaid",
        "graph LR",
        "    classDef modified fill:#ef4444,stroke:#dc2626,color:#ffffff,stroke-width:2px,rx:6px,ry:6px;",
        "    classDef direct fill:#f59e0b,stroke:#d97706,color:#ffffff,stroke-width:2px,rx:6px,ry:6px;",
        "    classDef downstream fill:#3b82f6,stroke:#2563eb,color:#ffffff,stroke-width:2px,rx:6px,ry:6px;"
    ]

    lines.append('    subgraph PR_Changes ["Modified in PR"]')
    for nid, name, fpath, _ in changed_nodes:
        lines.append(f'        {nid}["{name}<br/><small>{fpath}</small>"]:::modified')
    lines.append('    end')

    if direct_nodes:
        lines.append('    subgraph Direct_Callers ["Direct Callers"]')
        for nid, name, fpath in direct_nodes.values():
            lines.append(f'        {nid}["{name}<br/><small>{fpath}</small>"]:::direct')
        lines.append('    end')

    if downstream_nodes:
        lines.append('    subgraph Downstream_Impact ["Downstream Impact"]')
        for nid, name, fpath in downstream_nodes.values():
            lines.append(f'        {nid}["{name}<br/><small>{fpath}</small>"]:::downstream')
        lines.append('    end')

    for u, v in sorted(edges):
        lines.append(f'    {u} --> {v}')

    lines.append("```")
    return "\n".join(lines)


def format_impact_markdown(merged_impacts: dict, repo_name: str, pr_number: int, total_lines: int) -> str:
    if not merged_impacts:
        return '### ◈ N3MO Pull Request Impact Analysis\n\n✓ **Safe to change:** No active symbols were modified/affected in this Pull Request.'

    sorted_symbols = sorted(merged_impacts.values(), key=lambda x: (x['status'], x['file_path'], x['name']))

    markdown = '### ◈ N3MO Pull Request Impact Analysis\n\n'
    markdown += f"Analyzed **{total_lines:,} lines of code**. Below is the blast radius report for changes in PR #{pr_number}.\n\n"

    # 1. Visual Mermaid graph
    mermaid_graph = generate_mermaid_graph(merged_impacts)
    if mermaid_graph:
        markdown += mermaid_graph + "\n\n"

    # 2. Impact Summary Table
    markdown += '| File | Symbol | Status | Direct Callers | Total Impacted | Details |\n'
    markdown += '| :--- | :--- | :--- | :---: | :---: | :--- |\n'

    details_sections = []
    for data in sorted_symbols:
        name = data['name']
        status = data['status']
        file_path = data['file_path']
        line = data['line']
        callers = data['callers']

        direct_callers = [c for c in callers if c['depth'] == 1]
        ripple_callers = [c for c in callers if c['depth'] > 1]
        direct_count = len(direct_callers)
        total_count = len(callers)

        status_badge = f' `{status}`'
        if status == 'Modified':
            status_badge = ' 🟠 `Modified`'
        elif status == 'Added':
            status_badge = ' 🟢 `Added`'
        elif status == 'Deleted':
            status_badge = ' 🔴 `Deleted`'

        anchor = f"{file_path}-{name}".lower().replace('/', '-').replace('.', '-').replace('_', '-')
        markdown += f"| `{file_path}` | `{name}` | {status_badge} | {direct_count} | {total_count} | [View Details](#{anchor}) |\n"

        details = f'<a name="{anchor}"></a>\n'
        details += f"#### ◉ `{name}` ({status})\n"
        details += f"*   **Location:** `{file_path}:{line}`\n"

        if not callers:
            details += "*   **Blast Radius:** 0 callers (safe to change, no dependencies found).\n"
        else:
            if direct_callers:
                details += f"*   **Direct Callers ({len(direct_callers)}):**\n"
                for c in direct_callers:
                    lines_list = c.get('lines', [])
                    if lines_list:
                        lines_preview = ', '.join(str(l) for l in lines_list[:5])
                        if len(lines_list) > 5:
                            lines_preview += '...'
                        call_site_label = f" — {len(lines_list)} call site{'s' if len(lines_list) != 1 else ''} (lines: {lines_preview})"
                    else:
                        call_site_label = f" (`line {c['line']}`)" if c.get('line') else ""
                    details += f"    *   `{c['source']}` (`{c['file_path']}`){call_site_label}\n"

            if ripple_callers:
                details += f"\n<details>\n<summary><b>View {len(ripple_callers)} Downstream Ripple Effects</b></summary>\n\n"
                for c in sorted(ripple_callers, key=lambda x: (x['depth'], x['file_path'])):
                    indent = '  ' * (c['depth'] - 1)
                    lines_list = c.get('lines', [])
                    if lines_list:
                        lines_preview = ', '.join(str(l) for l in lines_list[:5])
                        if len(lines_list) > 5:
                            lines_preview += '...'
                        call_site_label = f" — {len(lines_list)} call site{'s' if len(lines_list) != 1 else ''} (lines: {lines_preview})"
                    else:
                        call_site_label = f" (`line {c['line']}`)" if c.get('line') else ""
                    details += f"{indent}* ─▸ `{c['source']}` (`{c['file_path']}`){call_site_label}\n"
                details += "\n</details>\n"

        details_sections.append(details)

    markdown += '\n---\n\n'
    markdown += '### 🔍 Impact Details\n\n'
    markdown += '\n'.join(details_sections)
    return markdown


def post_github_comment(repo_name: str, pr_number: int, body_markdown: str, installation_id: str | int | None = None) -> dict:
    token = os.getenv('GITHUB_TOKEN') or os.getenv('GITHUB_PAT')
    app_id = os.getenv('GITHUB_APP_ID')
    private_key_env = os.getenv('GITHUB_APP_PRIVATE_KEY')
    private_key_path = os.getenv('GITHUB_APP_PRIVATE_KEY_PATH') or os.getenv('GITHUB_PRIVATE_KEY_PATH')
    if not token and app_id and (private_key_env or private_key_path) and installation_id:
        logger.info('Authenticating as GitHub App...')
        token = get_github_app_installation_token(app_id, private_key_env, private_key_path, installation_id)
    if not token:
        logger.warning('⚠️ No GITHUB_TOKEN or GITHUB_APP credentials found. Printing report to stdout.')
        print('\n--- REPORT COMMENT ---\n')
        print(body_markdown)
        print('\n----------------------\n')
        return {'status': 'printed_locally', 'reason': 'no_credentials'}
    url = f'https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments'
    req = urllib.request.Request(
        url,
        data=json.dumps({'body': body_markdown}).encode('utf-8'),
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'N3MO-Impact-Tracker'
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            logger.info(f'Successfully posted comment to PR #{pr_number}')
            return {'status': 'posted', 'comment_id': data.get('id')}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        logger.error(f'Failed to post comment: {e.code} - {err_msg}')
        raise Exception(f'GitHub API Error: {err_msg}')


def get_github_app_installation_token(app_id, private_key_env, private_key_path, installation_id):
    if not app_id:
        raise Exception("Missing GITHUB_APP_ID")

    try:
        import jwt
        import time
    except ImportError:
        logger.error("jwt package not found.")
        raise Exception("PyJWT required for GitHub App auth")

    private_key = private_key_env
    if not private_key and private_key_path:
        if os.path.exists(private_key_path):
            with open(private_key_path, "r") as f:
                private_key = f.read()

    if not private_key:
        raise Exception("GitHub App private key is empty or not found")

    private_key = private_key.replace("\\n", "\n")

    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": str(app_id)
    }

    token_jwt = jwt.encode(payload, private_key, algorithm="RS256")

    if not installation_id:
        raise Exception("Missing installation ID")

    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token_jwt}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "N3MO-Impact-Tracker"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data.get("token")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        logger.error(f"Failed to get App installation token: {e.code} - {err_msg}")
        raise Exception(f"GitHub App Token Error: {err_msg}")
