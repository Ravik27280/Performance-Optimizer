import os
import re
import json
from pathlib import Path
from typing import List, Tuple
from core.issue import Issue, Severity, Layer

class NodeAnalyzer:
    def __init__(self, path: str):
        self.path = Path(path)
        self.issues: List[Issue] = []

    def analyze(self) -> List[Issue]:
        for f in self.path.rglob('*.js'):
            if any(x in str(f) for x in ['node_modules', 'dist/', '.min.js', 'test/', 'spec/', '.git']):
                continue
            try:
                src = f.read_text(encoding='utf-8', errors='ignore')
                rel = str(f.relative_to(self.path)).replace('\\', '/')
                lines = src.splitlines()

                self._check_async_patterns(src, lines, rel)
                self._check_seneca(src, lines, rel)
                self._check_db_patterns(src, lines, rel)
                self._check_api_responses(src, lines, rel)
                self._check_memory_and_events(src, lines, rel)
                self._check_network(src, lines, rel)
            except Exception:
                pass

        for f in self.path.rglob('*.json'):
            if any(x in str(f) for x in ['node_modules', 'dist/', '.git']):
                continue
            name = f.name.lower()
            if 'config' in name or 'database' in name or 'db' in name:
                try:
                    src = f.read_text(encoding='utf-8', errors='ignore')
                    rel = str(f.relative_to(self.path)).replace('\\', '/')
                    lines = src.splitlines()
                    self._check_db_config(src, lines, rel)
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
            if isinstance(regex_or_str, str) and regex_or_str in line:
                return idx, line.strip()
            elif hasattr(regex_or_str, 'search') and regex_or_str.search(line):
                return idx, line.strip()
        return 1, (lines[0].strip() if lines else '')

    def _check_async_patterns(self, src: str, lines: List[str], rel: str):
        # NODE001: Sync fs calls inside request handlers or functions
        # Distinguish top-level boot calls vs inside functions
        in_fn = False
        for idx, line in enumerate(lines, 1):
            if any(k in line for k in ['function', '=>', 'async', 'class']):
                in_fn = True
            if in_fn and any(sync_call in line for sync_call in ['fs.readFileSync', 'fs.writeFileSync', 'fs.readdirSync']):
                if not self._is_suppressed(lines, idx - 1, 'NODE001'):
                    self.issues.append(Issue(
                        id='NODE001',
                        title='Synchronous fs Call in Runtime Execution Path',
                        description='Calling synchronous filesystem methods (readFileSync / writeFileSync) inside functions blocks the Node.js event loop. All concurrent requests wait until disk I/O completes.',
                        fix='Switch to non-blocking `fs.promises.readFile` with `await` or use streams.',
                        code_before='const raw = fs.readFileSync(filePath, "utf8"); // Blocks event loop',
                        code_after='const raw = await fs.promises.readFile(filePath, "utf8"); // Non-blocking',
                        file=rel,
                        line_number=idx,
                        code_snippet=line.strip(),
                        category='Event Loop & Concurrency',
                        severity=Severity.HIGH,
                        layer=Layer.BACKEND,
                        impact=8,
                        effort=2,
                        occurrences=1,
                        perf_gain='Unblocks Node.js event loop for concurrent traffic'
                    ))
                    break

        # NODE002: Sequential await for independent promises
        for i in range(len(lines) - 1):
            line_a = lines[i]
            line_b = lines[i + 1]
            if re.search(r'const\s+(\w+)\s*=\s*await\s+\w+', line_a) and re.search(r'const\s+(\w+)\s*=\s*await\s+\w+', line_b):
                var_a = re.search(r'const\s+(\w+)', line_a).group(1)
                # If line_b does not reference var_a, they are likely independent
                if var_a not in line_b:
                    if not self._is_suppressed(lines, i, 'NODE002'):
                        self.issues.append(Issue(
                            id='NODE002',
                            title='Sequential await on Independent Operations',
                            description='Consecutive awaits run sequentially, accumulating latency (e.g. 200ms + 150ms = 350ms). Running them concurrently reduces total latency to the slowest operation.',
                            fix='Parallelize using `Promise.all([op1(), op2()])`.',
                            code_before='const user = await getUser(userId);\nconst config = await getAppConfig(); // Waits for user!',
                            code_after='const [user, config] = await Promise.all([\n  getUser(userId),\n  getAppConfig()\n]); // Runs in parallel',
                            file=rel,
                            line_number=i + 1,
                            code_snippet=f"{line_a.strip()} \\n {line_b.strip()}",
                            category='Latency & Parallelism',
                            severity=Severity.HIGH,
                            layer=Layer.BACKEND,
                            impact=7,
                            effort=2,
                            occurrences=1,
                            perf_gain='Reduces aggregate async operation latency by up to 50%'
                        ))
                        break

    def _check_seneca(self, src: str, lines: List[str], rel: str):
        if 'seneca' not in src.lower() and 'seneca' not in rel.lower():
            return

        # SEN001: seneca.act inside loop
        for idx, line in enumerate(lines, 1):
            if ('.act(' in line or 'seneca.act' in line):
                prev_block = '\n'.join(lines[max(0, idx - 8):idx])
                if any(loop_k in prev_block for loop_k in ['for (', 'for(', 'forEach(', 'for await']):
                    if not self._is_suppressed(lines, idx - 1, 'SEN001'):
                        self.issues.append(Issue(
                            id='SEN001',
                            title='Seneca .act() Called Inside Loop (Sequential RPC)',
                            description='Firing microservice .act() calls inside a loop sequentially serializes network RPCs. 50 items at 20ms each = 1,000ms latency.',
                            fix='Batch commands into a single message (`cmd:batchUpdate`) or parallelize via `Promise.all`.',
                            code_before='for (const item of items) {\n  await seneca.act({ role: "store", cmd: "update", item });\n}',
                            code_after='await seneca.act({ role: "store", cmd: "batchUpdate", items });',
                            file=rel,
                            line_number=idx,
                            code_snippet=line.strip(),
                            category='Microservice RPC',
                            severity=Severity.CRITICAL,
                            layer=Layer.BACKEND,
                            impact=9,
                            effort=4,
                            occurrences=1,
                            perf_gain='Reduces N×latency to max(latency) for batch operations'
                        ))
                        break

    def _check_db_patterns(self, src: str, lines: List[str], rel: str):
        # NODE004: N+1 Database queries inside loop
        for idx, line in enumerate(lines, 1):
            if any(q in line for q in ['.query(', '.execute(', '.find(', '.findOne(', 'db.']):
                prev_chunk = '\n'.join(lines[max(0, idx - 8):idx])
                if any(loop_kw in prev_chunk for loop_kw in ['for (', 'for(', 'forEach(', '.map(', 'for await']):
                    if not self._is_suppressed(lines, idx - 1, 'NODE004'):
                        self.issues.append(Issue(
                            id='NODE004',
                            title='N+1 Database Query Pattern in Loop',
                            description='Database query executed inside iteration loop. Triggers 1 + N network roundtrips to the database, exhausting connection pools and causing massive latency spikes under load.',
                            fix='Use a single SQL `JOIN` query or `WHERE id IN (...)` to retrieve all related records at once.',
                            code_before='for (const order of orders) {\n  order.user = await db.query("SELECT * FROM users WHERE id = ?", [order.userId]);\n}',
                            code_after='// Single JOIN query\nconst orders = await db.query(`\n  SELECT o.*, u.name, u.email FROM orders o\n  JOIN users u ON u.id = o.user_id\n`);',
                            file=rel,
                            line_number=idx,
                            code_snippet=line.strip(),
                            category='Database I/O',
                            severity=Severity.CRITICAL,
                            layer=Layer.BACKEND,
                            impact=10,
                            effort=3,
                            occurrences=1,
                            perf_gain='Replaces O(N) database queries with O(1)'
                        ))
                        break

        # NODE005: Unpaginated DB query
        if ('SELECT *' in src or 'find({})' in src or 'findAll()' in src) and 'LIMIT' not in src and 'limit' not in src:
            line_no, snippet = self._find_line(lines, re.compile(r'(?:SELECT\s+\*|find\(\{\}\)|findAll\(\))'))
            if not self._is_suppressed(lines, line_no - 1, 'NODE005'):
                self.issues.append(Issue(
                    id='NODE005',
                    title='Database Query Returns All Rows (No LIMIT / Pagination)',
                    description='Query lacks a LIMIT clause. On production datasets with tens of thousands of rows, this exhausts memory, locks DB cursors, and transmits massive payloads.',
                    fix='Add LIMIT and OFFSET or cursor-based pagination to the query.',
                    code_before='const users = await db.query("SELECT * FROM users");',
                    code_after='const users = await db.query("SELECT * FROM users LIMIT ? OFFSET ?", [limit, offset]);',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Database I/O',
                    severity=Severity.CRITICAL,
                    layer=Layer.BACKEND,
                    impact=10,
                    effort=2,
                    occurrences=1,
                    perf_gain='Caps query memory and network transfer to predictable bounds'
                ))

    def _check_api_responses(self, src: str, lines: List[str], rel: str):
        # NODE008: Missing compression middleware in Express
        if 'express' in src and 'compression' not in src and ('listen(' in src or 'app.use' in src):
            line_no, snippet = self._find_line(lines, re.compile(r'express\(\)'))
            if not self._is_suppressed(lines, line_no - 1, 'NODE008'):
                self.issues.append(Issue(
                    id='NODE008',
                    title='Express Server Missing Gzip/Brotli Response Compression',
                    description='HTTP JSON responses are sent uncompressed. Modern gzip or brotli compression reduces JSON payload sizes by 70% to 90%, speeding up API response times on mobile and slow networks.',
                    fix='Add `app.use(compression());` with the `compression` middleware.',
                    code_before='const app = express();\napp.use(routes);',
                    code_after='const compression = require("compression");\nconst app = express();\napp.use(compression());\napp.use(routes);',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Network Optimization',
                    severity=Severity.MEDIUM,
                    layer=Layer.BACKEND,
                    impact=6,
                    effort=1,
                    occurrences=1,
                    perf_gain='Reduces network payload sizes by 70-90%'
                ))

    def _check_memory_and_events(self, src: str, lines: List[str], rel: str):
        # NODE011: EventEmitter leak (on without removeListener/off)
        on_count = len(re.findall(r'\.on\(', src))
        off_count = len(re.findall(r'\.(?:off|removeListener|removeAllListeners)\(', src))
        if on_count >= 3 and off_count == 0 and ('emitter' in src.lower() or 'event' in src.lower()):
            line_no, snippet = self._find_line(lines, '.on(')
            if not self._is_suppressed(lines, line_no - 1, 'NODE011'):
                self.issues.append(Issue(
                    id='NODE011',
                    title='Potential EventEmitter Memory Leak (Missing Listener Teardown)',
                    description=f'Found {on_count} `.on(...)` listener registrations with no corresponding `.off()` or `.removeListener()`. Retains closures and objects in memory across request lifecycles.',
                    fix='Ensure event listeners are cleaned up or use `events.once()` for one-time events.',
                    code_before='emitter.on("data", handler); // Listener never removed',
                    code_after='emitter.once("data", handler); // Or emitter.off("data", handler) in cleanup',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Memory Leak',
                    severity=Severity.HIGH,
                    layer=Layer.BACKEND,
                    impact=7,
                    effort=2,
                    occurrences=on_count,
                    perf_gain='Eliminates progressive heap memory growth in long-running processes'
                ))

    def _check_network(self, src: str, lines: List[str], rel: str):
        # NODE012: Missing HTTP keep-alive for microservice/API clients
        if ('axios' in src or 'fetch(' in src or 'http.request' in src) and 'keepAlive' not in src and 'Agent' not in src:
            line_no, snippet = self._find_line(lines, re.compile(r'(?:axios|http\.request)'))
            if line_no > 0 and not self._is_suppressed(lines, line_no - 1, 'NODE012'):
                self.issues.append(Issue(
                    id='NODE012',
                    title='HTTP Requests Without Connection Reuse (Missing keepAlive: true)',
                    description='Outgoing HTTP requests create a new TCP + TLS handshake for every call. Enabling HTTP keep-alive reuses existing TCP sockets, eliminating 50-100ms connection overhead per RPC.',
                    fix='Configure `http.Agent({ keepAlive: true })` or pass `{ keepAlive: true }` to your HTTP client.',
                    code_before='const agent = new http.Agent(); // Default keepAlive: false',
                    code_after='const agent = new http.Agent({ keepAlive: true, maxSockets: 50 });',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Latency & Network',
                    severity=Severity.MEDIUM,
                    layer=Layer.BACKEND,
                    impact=6,
                    effort=2,
                    occurrences=1,
                    perf_gain='Saves 50ms-100ms TLS handshake latency on repeated service calls'
                ))

    def _check_db_config(self, src: str, lines: List[str], rel: str):
        # NODE010: Pool max too small
        try:
            cfg = json.loads(src)
            pool = cfg.get('pool', cfg.get('database', {}).get('pool', {}))
            if isinstance(pool, dict):
                max_conn = pool.get('max', pool.get('maximum', None))
                if max_conn is not None and int(max_conn) < 5:
                    line_no, snippet = self._find_line(lines, '"max"')
                    if not self._is_suppressed(lines, line_no - 1, 'NODE010'):
                        self.issues.append(Issue(
                            id='NODE010',
                            title=f'Database Connection Pool Too Small (max = {max_conn})',
                            description=f'Database pool max size configured to only {max_conn}. Under concurrent requests, operations queue waiting for an available DB connection, artificially inflating request latency.',
                            fix='Increase pool max to 10-20 connections based on CPU cores and RDS tier.',
                            code_before=f'"pool": {{ "max": {max_conn}, "min": 0 }}',
                            code_after='"pool": { "max": 15, "min": 2, "acquire": 30000, "idle": 10000 }',
                            file=rel,
                            line_number=line_no,
                            code_snippet=snippet,
                            category='Database Configuration',
                            severity=Severity.HIGH,
                            layer=Layer.BACKEND,
                            impact=8,
                            effort=1,
                            occurrences=1,
                            perf_gain='Eliminates connection queue wait delays under concurrent load'
                        ))
        except Exception:
            pass
