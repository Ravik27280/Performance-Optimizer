import re
from pathlib import Path
from core.issue import Issue, Severity, Layer

class SqlAnalyzer:
    def __init__(self, path):
        self.path = Path(path)
        self.issues = []

    def analyze(self):
        # Scan .sql files
        for f in self.path.rglob('*.sql'):
            if 'node_modules' in str(f): continue
            try:
                src = f.read_text(errors='ignore').upper()
                rel = str(f.relative_to(self.path))
                self._check_sql_file(src, rel, f)
            except: pass
        # Scan JS/TS files for inline SQL strings
        for f in list(self.path.rglob('*.js')) + list(self.path.rglob('*.ts')):
            if any(x in str(f) for x in ['node_modules', 'dist/', '.spec.']): continue
            try:
                src = f.read_text(errors='ignore')
                rel = str(f.relative_to(self.path))
                self._check_inline_sql(src, rel)
            except: pass
        return self.issues

    def _check_sql_file(self, src, rel, f):
        # SELECT * usage
        select_star = len(re.findall(r'SELECT\s+\*\s+FROM', src))
        if select_star > 0:
            self.issues.append(Issue(
                id='SQL001', title=f'SELECT * Usage ({select_star} queries)',
                description=f'{select_star} queries use SELECT *. This fetches ALL columns including large TEXT/BLOB fields you may not need. Increases I/O, memory, and network transfer. Breaks app when columns are added/removed.',
                fix='Specify exact columns needed: SELECT id, name, status FROM table',
                code_before='SELECT * FROM orders WHERE user_id = ?\n-- Fetches 30 columns, including large JSON/BLOB fields',
                code_after='SELECT id, status, total, created_at FROM orders WHERE user_id = ?\n-- Only 4 columns needed by the API',
                file=rel, severity=Severity.HIGH, layer=Layer.DATABASE,
                impact=7, effort=3, occurrences=select_star,
                perf_gain='Reduces row transfer size, faster query execution'
            ))
        # Missing WHERE clause on UPDATE/DELETE
        dangerous = re.findall(r'(?:UPDATE|DELETE FROM)\s+\w+\s*(?:SET[^;]+)?(?:;|$)', src)
        no_where = [q for q in dangerous if 'WHERE' not in q]
        if no_where:
            self.issues.append(Issue(
                id='SQL002', title=f'UPDATE/DELETE Without WHERE Clause',
                description=f'Found {len(no_where)} UPDATE or DELETE statements with no WHERE clause. These affect ALL rows in the table. One accidental call corrupts the entire dataset.',
                fix='Always add a WHERE clause. Use transactions for multi-step operations.',
                code_before='UPDATE users SET status = \'inactive\';\n-- Updates ALL users!',
                code_after='UPDATE users SET status = \'inactive\'\nWHERE last_login < NOW() - INTERVAL 90 DAY;',
                file=rel, severity=Severity.CRITICAL, layer=Layer.DATABASE,
                impact=10, effort=2, occurrences=len(no_where),
                perf_gain='Data integrity protection; prevents full-table locks'
            ))
        # No LIMIT on SELECT
        selects = re.findall(r'SELECT\b.+?FROM\b.+?(?:WHERE.+?)?(?:;|$)', src, re.DOTALL)
        no_limit = [s for s in selects if 'LIMIT' not in s and 'TOP' not in s and len(s) < 500]
        if len(no_limit) > 2:
            self.issues.append(Issue(
                id='SQL003', title=f'{len(no_limit)} SELECT Queries Without LIMIT',
                description=f'{len(no_limit)} SELECT queries have no LIMIT clause. These will return ALL matching rows. On a 1M-row table this returns 1M rows to the application layer.',
                fix='Add LIMIT to all queries used in lists/grids. Use cursor-based pagination for large datasets.',
                code_before='SELECT id, name FROM products WHERE active = 1;\n-- Returns all active products (maybe 500,000)',
                code_after='SELECT id, name FROM products WHERE active = 1\nLIMIT 50 OFFSET ?; -- paginated',
                file=rel, severity=Severity.HIGH, layer=Layer.DATABASE,
                impact=9, effort=2, occurrences=len(no_limit),
                perf_gain='Limits result set to manageable size regardless of table growth'
            ))
        # Missing indexes detection (look for CREATE TABLE without indexes)
        tables = re.findall(r'CREATE\s+TABLE\s+(\w+)\s*\(([^;]+)\)', src, re.DOTALL)
        for tname, tdef in tables:
            fk_cols = re.findall(r'(\w+_ID|\w+_FK|FOREIGN\s+KEY\s*\((\w+)\))', tdef)
            index_defs = re.findall(r'INDEX|KEY\s+\w|UNIQUE', tdef)
            if fk_cols and not index_defs:
                self.issues.append(Issue(
                    id='SQL004', title=f'Missing Index on Table: {tname}',
                    description=f'Table {tname} has foreign key / relationship columns but no indexes defined. JOINs and WHERE clauses on these columns perform full table scans O(N) instead of O(log N).',
                    fix=f'Add indexes: CREATE INDEX idx_{tname.lower()}_fk ON {tname}(user_id);',
                    code_before=f'CREATE TABLE {tname} (\n  id INT PRIMARY KEY,\n  user_id INT,  -- no index!\n  order_id INT  -- no index!\n);\n-- JOIN on user_id = full table scan',
                    code_after=f'CREATE TABLE {tname} (\n  id INT PRIMARY KEY,\n  user_id INT,\n  order_id INT,\n  INDEX idx_user (user_id),\n  INDEX idx_order (order_id)\n);',
                    file=rel, severity=Severity.CRITICAL, layer=Layer.DATABASE,
                    impact=9, effort=2, occurrences=len(fk_cols),
                    perf_gain='Turns O(N) table scans into O(log N) index lookups'
                ))

    def _check_inline_sql(self, src, rel):
        # Find SQL strings in JS/TS
        sql_strings = re.findall(r'[`\'"](SELECT[^`\'"]{10,})[`\'"]', src, re.IGNORECASE)
        if not sql_strings: return
        # String concatenation in SQL (SQL injection + perf)
        concat_sql = re.findall(r'[`\'"](SELECT[^`\'"]+)[`\'"]\s*\+', src, re.IGNORECASE)
        if concat_sql:
            self.issues.append(Issue(
                id='SQL005', title='SQL Built by String Concatenation',
                description='SQL query built by string concatenation prevents the DB from caching query execution plans. Each unique string = new plan compilation. Also creates SQL injection vulnerability.',
                fix='Use parameterized queries with ? placeholders. DB caches the plan and reuses it.',
                code_before="const sql = 'SELECT * FROM users WHERE id = ' + userId;\n// New plan on every unique userId value",
                code_after="const sql = 'SELECT * FROM users WHERE id = ?';\nawait db.query(sql, [userId]);\n// Plan cached and reused",
                file=rel, severity=Severity.HIGH, layer=Layer.DATABASE,
                impact=7, effort=3, occurrences=len(concat_sql),
                perf_gain='Enables query plan caching, reduces DB CPU load'
            ))
        # LIKE with leading wildcard (can't use index)
        leading_wildcard = re.findall(r"LIKE\s+['\"`]%", ''.join(sql_strings), re.IGNORECASE)
        if leading_wildcard:
            self.issues.append(Issue(
                id='SQL006', title='LIKE With Leading Wildcard (Index Bypass)',
                description=f'Found {len(leading_wildcard)} LIKE \'%value\' patterns. A leading % means the DB CANNOT use any index on that column — forces a full table scan every time.',
                fix='For full-text search, use MySQL FULLTEXT index with MATCH() AGAINST(). Avoid leading % in LIKE.',
                code_before="WHERE name LIKE '%smith%'\n-- Full table scan every time, ignores any index on 'name'",
                code_after='-- Add fulltext index:\nALTER TABLE users ADD FULLTEXT(name);\n-- Query:\nWHERE MATCH(name) AGAINST(\'smith\' IN BOOLEAN MODE)',
                file=rel, severity=Severity.HIGH, layer=Layer.DATABASE,
                impact=8, effort=4, occurrences=len(leading_wildcard),
                perf_gain='Turns full table scan into indexed lookup for search queries'
            ))
