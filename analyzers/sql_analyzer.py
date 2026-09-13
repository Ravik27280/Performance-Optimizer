import os
import re
from pathlib import Path
from typing import List, Tuple
from core.issue import Issue, Severity, Layer

class SqlAnalyzer:
    def __init__(self, path: str):
        self.path = Path(path)
        self.issues: List[Issue] = []

    def analyze(self) -> List[Issue]:
        # Scan dedicated .sql files
        for f in self.path.rglob('*.sql'):
            if any(x in str(f) for x in ['node_modules', 'dist/', '.git']):
                continue
            try:
                src = f.read_text(encoding='utf-8', errors='ignore')
                rel = str(f.relative_to(self.path)).replace('\\', '/')
                lines = src.splitlines()
                self._check_sql_file(src, lines, rel)
            except Exception:
                pass

        # Scan .js and .ts files for inline SQL strings
        for f in list(self.path.rglob('*.js')) + list(self.path.rglob('*.ts')):
            if any(x in str(f) for x in ['node_modules', 'dist/', '.spec.', '.d.ts', '.git']):
                continue
            try:
                src = f.read_text(encoding='utf-8', errors='ignore')
                rel = str(f.relative_to(self.path)).replace('\\', '/')
                lines = src.splitlines()
                self._check_inline_sql(src, lines, rel)
            except Exception:
                pass

        return self.issues

    def _is_suppressed(self, lines: List[str], line_idx: int, rule_id: str) -> bool:
        check_lines = []
        if 0 <= line_idx < len(lines):
            check_lines.append(lines[line_idx])
        if 0 <= line_idx - 1 < len(lines):
            check_lines.append(lines[line_idx - 1])
        for cl in check_lines:
            if f'perf-ignore {rule_id}' in cl or 'perf-ignore-all' in cl:
                return True
        return False

    def _find_line(self, lines: List[str], regex_or_str) -> Tuple[int, str]:
        for idx, line in enumerate(lines, 1):
            if isinstance(regex_or_str, str) and regex_or_str.lower() in line.lower():
                return idx, line.strip()
            elif hasattr(regex_or_str, 'search') and regex_or_str.search(line):
                return idx, line.strip()
        return 1, (lines[0].strip() if lines else '')

    def _check_sql_file(self, src: str, lines: List[str], rel: str):
        # SQL001: SELECT * Usage
        select_star_count = len(re.findall(r'SELECT\s+\*\s+FROM', src, re.IGNORECASE))
        if select_star_count > 0:
            line_no, snippet = self._find_line(lines, re.compile(r'SELECT\s+\*\s+FROM', re.IGNORECASE))
            if not self._is_suppressed(lines, line_no - 1, 'SQL001'):
                self.issues.append(Issue(
                    id='SQL001',
                    title=f'SELECT * Over-fetching ({select_star_count} occurrences)',
                    description='Fetching all table columns with SELECT * wastes database memory, network bandwidth, and prevents index-only query execution plans.',
                    fix='Explicitly enumerate the necessary columns: `SELECT id, name, status FROM table`.',
                    code_before='SELECT * FROM orders WHERE user_id = ?;',
                    code_after='SELECT id, total_amount, status, created_at FROM orders WHERE user_id = ?;',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Database I/O',
                    severity=Severity.HIGH,
                    layer=Layer.DATABASE,
                    impact=7,
                    effort=2,
                    occurrences=select_star_count,
                    perf_gain='Reduces row serialization size and network transfer'
                ))

        # SQL004: Missing indexes on foreign keys
        table_defs = re.finditer(r'CREATE\s+TABLE\s+(\w+)\s*\(([^;]+)\)', src, re.IGNORECASE | re.DOTALL)
        for tbl in table_defs:
            tname = tbl.group(1)
            tbody = tbl.group(2)
            has_fk = re.search(r'(\w+_id|\w+_fk)\s+INT', tbody, re.IGNORECASE) or 'FOREIGN KEY' in tbody.upper()
            has_idx = any(idx_kw in tbody.upper() for idx_kw in ['INDEX', 'KEY ', 'UNIQUE'])
            if has_fk and not has_idx:
                line_no, snippet = self._find_line(lines, re.compile(rf'CREATE\s+TABLE\s+{tname}', re.IGNORECASE))
                if not self._is_suppressed(lines, line_no - 1, 'SQL004'):
                    self.issues.append(Issue(
                        id='SQL004',
                        title=f'Missing Foreign Key Index on Table `{tname}`',
                        description=f'Table `{tname}` defines relationship foreign keys without explicit B-Tree indexes. Queries using JOIN or WHERE on foreign keys will execute full table scans.',
                        fix=f'Add B-Tree indexes to foreign key columns: `INDEX idx_{tname.lower()}_fk (user_id)`.',
                        code_before=f'CREATE TABLE {tname} (\n  id INT PRIMARY KEY,\n  user_id INT -- No index: causes O(N) table scans\n);',
                        code_after=f'CREATE TABLE {tname} (\n  id INT PRIMARY KEY,\n  user_id INT,\n  INDEX idx_{tname.lower()}_user (user_id)\n);',
                        file=rel,
                        line_number=line_no,
                        code_snippet=snippet,
                        category='Indexing & Optimization',
                        severity=Severity.CRITICAL,
                        layer=Layer.DATABASE,
                        impact=9,
                        effort=2,
                        occurrences=1,
                        perf_gain='Converts O(N) table scans into O(log N) B-Tree seeks'
                    ))

        # SQL007: Deep OFFSET pagination antipattern
        if re.search(r'OFFSET\s+[1-9]\d{3,}', src, re.IGNORECASE):
            line_no, snippet = self._find_line(lines, re.compile(r'OFFSET\s+[1-9]\d{3,}', re.IGNORECASE))
            if not self._is_suppressed(lines, line_no - 1, 'SQL007'):
                self.issues.append(Issue(
                    id='SQL007',
                    title='Deep OFFSET Pagination Antipattern (O(N) Discard Waste)',
                    description='High OFFSET values force the database engine to fetch and discard thousands of rows before returning the requested slice. Response latency degrades proportionally with page depth.',
                    fix='Use keyset / cursor-based pagination: `WHERE id > :last_id ORDER BY id LIMIT 50`.',
                    code_before='SELECT id, name FROM orders ORDER BY id LIMIT 50 OFFSET 10000;',
                    code_after='SELECT id, name FROM orders WHERE id > :cursor ORDER BY id LIMIT 50;',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Query Performance',
                    severity=Severity.HIGH,
                    layer=Layer.DATABASE,
                    impact=8,
                    effort=3,
                    occurrences=1,
                    perf_gain='Constant O(1) query time regardless of pagination depth'
                ))

    def _check_inline_sql(self, src: str, lines: List[str], rel: str):
        # SQL005: String concatenation in SQL queries
        concat_matches = re.finditer(r'[`\'"](SELECT[^`\'"]+)[`\'"]\s*\+', src, re.IGNORECASE)
        for m in concat_matches:
            matched_text = m.group(0)
            line_no, snippet = self._find_line(lines, matched_text[:20])
            if not self._is_suppressed(lines, line_no - 1, 'SQL005'):
                self.issues.append(Issue(
                    id='SQL005',
                    title='SQL Built via String Concatenation (Disables Execution Plan Cache)',
                    description='Dynamic string concatenation generates a unique SQL text for every argument, preventing the database from reusing compiled execution plans. Also opens SQL injection risk.',
                    fix='Use parameterized queries with `?` or `$1` placeholders so execution plans are cached.',
                    code_before='const sql = "SELECT * FROM users WHERE status = \'" + status + "\'";',
                    code_after='const sql = "SELECT id, name, status FROM users WHERE status = ?";\nawait db.query(sql, [status]);',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Execution Plan Cache',
                    severity=Severity.HIGH,
                    layer=Layer.DATABASE,
                    impact=8,
                    effort=2,
                    occurrences=1,
                    perf_gain='Enables query plan caching and eliminates SQL injection'
                ))
                break

        # SQL006: LIKE with leading wildcard
        leading_like = re.search(r"LIKE\s+['\"]%[^'\"]+['\"]", src, re.IGNORECASE)
        if leading_like:
            line_no, snippet = self._find_line(lines, re.compile(r"LIKE\s+['\"]%", re.IGNORECASE))
            if not self._is_suppressed(lines, line_no - 1, 'SQL006'):
                self.issues.append(Issue(
                    id='SQL006',
                    title='SQL LIKE Query with Leading Wildcard (%query)',
                    description='A leading wildcard pattern like `LIKE "%keyword"` prevents the database engine from using B-Tree indexes, triggering a full table scan across all rows.',
                    fix='Use trailing wildcard `LIKE "keyword%"` or implement Full-Text Search (FTS) / trigram indexing.',
                    code_before='SELECT id, title FROM articles WHERE title LIKE "%performance%";',
                    code_after='-- Use Full-Text index:\nSELECT id, title FROM articles WHERE MATCH(title) AGAINST(? IN NATURAL LANGUAGE MODE);',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Indexing & Search',
                    severity=Severity.MEDIUM,
                    layer=Layer.DATABASE,
                    impact=7,
                    effort=3,
                    occurrences=1,
                    perf_gain='Avoids full table scan on text searches'
                ))
