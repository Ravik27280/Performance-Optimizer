import os, re
from pathlib import Path
from core.issue import Issue, Severity, Layer

class NodeAnalyzer:
    def __init__(self, path):
        self.path = Path(path)
        self.issues = []

    def analyze(self):
        for f in self.path.rglob('*.js'):
            if any(x in str(f) for x in ['node_modules', 'dist/', '.min.js', 'test/', 'spec/']): continue
            try:
                src = f.read_text(errors='ignore')
                rel = str(f.relative_to(self.path))
                self._check_async_patterns(src, f, rel)
                self._check_seneca(src, f, rel)
                self._check_db_patterns(src, f, rel)
                self._check_api_responses(src, f, rel)
                self._check_memory(src, f, rel)
            except: pass
        for f in self.path.rglob('*.json'):
            if any(x in str(f) for x in ['node_modules', 'dist/']): continue
            name = f.name.lower()
            if name in ['db.config.json', 'database.json'] or 'config' in name:
                try:
                    src = f.read_text(errors='ignore')
                    rel = str(f.relative_to(self.path))
                    self._check_db_config(src, f, rel)
                except: pass
        return self.issues

    def _check_async_patterns(self, src, f, rel):
        # Sync fs in hot paths
        sync_fs = re.findall(r'fs\.read(?:File|dir)Sync|fs\.write(?:File)?Sync|fs\.existsSync', src)
        if sync_fs:
            self.issues.append(Issue(
                id='NODE001', title=f'Synchronous fs Call in Server Code ({len(sync_fs)} found)',
                description=f'Found {len(sync_fs)} synchronous filesystem calls: {list(set(sync_fs[:3]))}. Sync fs calls BLOCK the entire Node.js event loop. Every concurrent request waits until the disk I/O completes. Under load, this serializes all traffic.',
                fix='Replace with async fs.promises.readFile / fs.promises.writeFile or use streams.',
                code_before='const data = fs.readFileSync(\'config.json\', \'utf8\');\n// BLOCKS: all requests wait for disk I/O',
                code_after='const data = await fs.promises.readFile(\'config.json\', \'utf8\');\n// Non-blocking: event loop continues serving other requests',
                file=rel, severity=Severity.HIGH, layer=Layer.BACKEND,
                impact=8, effort=3, occurrences=len(sync_fs),
                perf_gain='Unblocks event loop, allows Node to serve concurrent requests during I/O'
            ))
        # Missing Promise.all for independent async calls
        lines = src.split('\n')
        sequential_awaits = []
        for i in range(len(lines)-1):
            if re.search(r'await\s+\w+', lines[i]) and re.search(r'await\s+\w+', lines[i+1]):
                # Check if they seem independent (no variable from line i used in line i+1)
                m1 = re.search(r'const (\w+)\s*=\s*await', lines[i])
                if m1:
                    varname = m1.group(1)
                    if varname not in lines[i+1]:
                        sequential_awaits.append(i+1)
        if len(sequential_awaits) >= 2:
            self.issues.append(Issue(
                id='NODE002', title='Sequential await for Independent Promises',
                description=f'Found {len(sequential_awaits)} places with back-to-back awaits on independent operations. These run one-at-a-time adding latencies together. If op1=200ms and op2=150ms, sequential=350ms. Parallel=200ms.',
                fix='Use Promise.all() to run independent async operations in parallel.',
                code_before='const user = await getUser(id);      // 200ms\nconst config = await getConfig();    // 150ms\n// Total: 350ms (sequential)',
                code_after='const [user, config] = await Promise.all([\n  getUser(id),      // \\\n  getConfig()       //  > 200ms (parallel)\n]);               // /',
                file=rel, severity=Severity.HIGH, layer=Layer.BACKEND,
                impact=7, effort=3, occurrences=len(sequential_awaits),
                perf_gain=f'Reduces latency of independent async operations by up to 50%'
            ))
        # Unhandled promise rejections
        then_count = src.count('.then(')
        catch_count = src.count('.catch(')
        if then_count > 0 and catch_count < then_count // 2:
            self.issues.append(Issue(
                id='NODE003', title='Promise Chains Without .catch() (Unhandled Rejections)',
                description=f'Found {then_count} .then() chains but only {catch_count} .catch() handlers. Unhandled promise rejections crash Node.js processes in newer versions and cause silent failures in older ones.',
                fix='Add .catch() to every promise chain or use try/catch with async/await.',
                code_before='fetchData().then(d => process(d));\n// If fetchData rejects: UnhandledPromiseRejectionWarning',
                code_after='try {\n  const d = await fetchData();\n  process(d);\n} catch (err) {\n  logger.error(err); // handle gracefully\n}',
                file=rel, severity=Severity.MEDIUM, layer=Layer.BACKEND,
                impact=6, effort=3, occurrences=then_count - catch_count,
                perf_gain='Prevents silent failures and process crashes under load'
            ))

    def _check_seneca(self, src, f, rel):
        if 'seneca' not in src.lower() and 'seneca' not in rel.lower(): return
        # seneca.act inside loop
        if ('seneca.act(' in src or '.act(' in src) and ('for(' in src or 'forEach' in src or 'for (' in src):
            self.issues.append(Issue(
                id='SEN001', title='Seneca .act() Called Inside Loop',
                description='Calling seneca.act() inside a for/forEach loop fires N sequential microservice calls. Each waits for the previous. For N=100 items with 10ms latency each = 1 second blocked.',
                fix='Batch items and send as a single act, or use Promise.all to parallelize act calls.',
                code_before='for (const item of items) {\n  await seneca.act(\'role:inventory,cmd:update\', { item });\n  // N sequential microservice calls\n}',
                code_after='// Option 1: Batch\nawait seneca.act(\'role:inventory,cmd:updateBatch\', { items });\n// Option 2: Parallel\nawait Promise.all(items.map(item =>\n  seneca.act(\'role:inventory,cmd:update\', { item })\n));',
                file=rel, severity=Severity.CRITICAL, layer=Layer.BACKEND,
                impact=9, effort=4, occurrences=1,
                perf_gain='Reduces N×latency to max(latency) for batch operations'
            ))
        # Missing timeout on seneca act
        if '.act(' in src and 'timeout' not in src.lower():
            self.issues.append(Issue(
                id='SEN002', title='Seneca .act() Without Timeout',
                description='Seneca act calls without timeout will hang indefinitely if the target plugin is slow or dead. This blocks the calling request handler, exhausting the thread pool.',
                fix='Set timeout in seneca.act options or configure global timeout: seneca({ timeout: 5000 })',
                code_before='seneca.act(\'role:payment,cmd:charge\', data, cb);\n// Hangs forever if payment service is slow',
                code_after='seneca.act(\'role:payment,cmd:charge\', data,\n  { timeout$: 5000 }, // 5s max\n  cb\n);',
                file=rel, severity=Severity.HIGH, layer=Layer.BACKEND,
                impact=7, effort=2, occurrences=src.count('.act('),
                perf_gain='Prevents cascading timeouts from hanging the entire request pipeline'
            ))

    def _check_db_patterns(self, src, f, rel):
        # N+1 query pattern: query inside loop
        lines = src.split('\n')
        in_loop = False
        loop_depth = 0
        query_in_loop = 0
        for line in lines:
            if re.search(r'\bfor\s*\(|\bforEach\b|\bfor\s+\(.*of\b|\bmap\s*\(', line):
                in_loop = True
                loop_depth += 1
            if in_loop and re.search(r'\.query\s*\(|\.execute\s*\(|\.find\s*\(|\.findOne\s*\(|\.select\s*\(|db\.\w+', line):
                query_in_loop += 1
            if line.count('{') != line.count('}'):
                pass
            if re.search(r'^\s*}\s*[;,]?\s*$', line) and in_loop:
                loop_depth = max(0, loop_depth - 1)
                if loop_depth == 0: in_loop = False
        if query_in_loop > 0:
            self.issues.append(Issue(
                id='NODE004', title=f'N+1 Database Query Pattern ({query_in_loop} occurrence(s))',
                description=f'Detected {query_in_loop} database query call(s) inside iteration loops. This is the classic N+1 problem: 1 query to get N records, then N queries for each record\'s details. At N=100 rows with 5ms/query = 505ms. At N=1000 = 5005ms.',
                fix='Use JOIN queries or IN clauses to fetch related data in a single query. Use ORM eager loading (include/populate).',
                code_before='const orders = await db.query(\'SELECT * FROM orders\');\nfor (const order of orders) {\n  order.user = await db.query(\n    \'SELECT * FROM users WHERE id = ?\', [order.user_id]\n  ); // N extra queries!\n}',
                code_after='const orders = await db.query(`\n  SELECT o.*, u.name, u.email\n  FROM orders o\n  JOIN users u ON u.id = o.user_id\n`); // 1 query total',
                file=rel, severity=Severity.CRITICAL, layer=Layer.BACKEND,
                impact=10, effort=4, occurrences=query_in_loop,
                perf_gain='Reduces DB load from O(N) queries to O(1) per request'
            ))
        # No pagination in API return
        if ('SELECT *' in src or 'find({})' in src or 'findAll()' in src) and 'LIMIT' not in src and 'limit' not in src:
            self.issues.append(Issue(
                id='NODE005', title='Database Query Returns All Rows (No LIMIT)',
                description='Query fetches ALL rows with no LIMIT clause. As table grows, response time grows proportionally. A 1M row table will return all 1M rows, bloating memory and response payload.',
                fix='Always add LIMIT/OFFSET or cursor-based pagination. Return paginated metadata (total, page, limit) in response.',
                code_before="const users = await db.query('SELECT * FROM users');\n// Returns ALL rows always",
                code_after="const { page = 1, limit = 50 } = req.query;\nconst offset = (page - 1) * limit;\nconst users = await db.query(\n  'SELECT * FROM users LIMIT ? OFFSET ?',\n  [limit, offset]\n);",
                file=rel, severity=Severity.CRITICAL, layer=Layer.BACKEND,
                impact=10, effort=3, occurrences=1,
                perf_gain='Limits response to fixed size regardless of table growth'
            ))
        # No caching for repeated queries
        if src.count('.query(') > 4 or src.count('.find(') > 4:
            self.issues.append(Issue(
                id='NODE006', title='No Caching Layer for Repeated DB Queries',
                description='Multiple DB queries detected with no caching (Redis/Memcached). Identical queries for static/slow-changing data hit the DB every time.',
                fix='Add Redis cache with TTL for frequently-read, rarely-changed data. Use node-cache for in-process caching.',
                code_before='async getConfig() {\n  return await db.query(\'SELECT * FROM config\');\n  // Hits DB on every request\n}',
                code_after='async getConfig() {\n  const cached = await redis.get(\'config\');\n  if (cached) return JSON.parse(cached);\n  const data = await db.query(\'SELECT * FROM config\');\n  await redis.setex(\'config\', 300, JSON.stringify(data));\n  return data;\n}',
                file=rel, severity=Severity.HIGH, layer=Layer.BACKEND,
                impact=8, effort=5, occurrences=1,
                perf_gain='Eliminates DB hits for cacheable data, reduces DB load by 60-90%'
            ))

    def _check_api_responses(self, src, f, rel):
        # Sending entire object without field selection
        if ('res.json(' in src or 'res.send(' in src) and 'SELECT *' in src:
            self.issues.append(Issue(
                id='NODE007', title='API Returns Full DB Row (Over-fetching)',
                description='API response includes all database columns including sensitive/unused fields. Increases payload size, wastes bandwidth, and leaks internal schema to clients.',
                fix='Select only needed columns in SQL. Use a DTO/serializer to shape API responses explicitly.',
                code_before="const user = await db.query('SELECT * FROM users WHERE id = ?', [id]);\nres.json(user); // sends password_hash, internal_id, audit_fields...",
                code_after="const user = await db.query(\n  'SELECT id, name, email, avatar FROM users WHERE id = ?', [id]\n);\nres.json(user); // only what client needs",
                file=rel, severity=Severity.MEDIUM, layer=Layer.BACKEND,
                impact=5, effort=2, occurrences=1,
                perf_gain='Reduces response payload size, faster JSON serialization'
            ))
        # No compression middleware
        if 'express' in src and 'compress' not in src and 'gzip' not in src:
            self.issues.append(Issue(
                id='NODE008', title='No Response Compression (gzip/brotli)',
                description='Express server has no compression middleware. JSON API responses sent uncompressed. A 200KB JSON payload compresses to ~20KB with gzip (90% reduction).',
                fix='Add compression middleware: npm install compression, then app.use(compression())',
                code_before="const app = express();\n// No compression\napp.use(router);",
                code_after="const compression = require('compression');\napp.use(compression()); // auto gzip/deflate\napp.use(router);",
                file=rel, severity=Severity.MEDIUM, layer=Layer.BACKEND,
                impact=6, effort=1, occurrences=1,
                perf_gain='Reduces API response sizes by 70-90%, faster network transfer'
            ))

    def _check_memory(self, src, f, rel):
        # Large in-memory arrays grown without bound
        if re.search(r'let\s+\w+\s*=\s*\[\]', src) and '.push(' in src and 'splice' not in src and 'shift' not in src:
            pushes = src.count('.push(')
            if pushes > 5:
                self.issues.append(Issue(
                    id='NODE009', title='Unbounded In-Memory Array Growth',
                    description=f'Found array that grows via {pushes} .push() calls with no cleanup (splice/shift/slice). In a long-running server, this leaks memory indefinitely.',
                    fix='Cap the array size, use a circular buffer, or stream data instead of accumulating.',
                    code_before='let events = [];\nsetInterval(() => {\n  events.push(getEvent()); // grows forever\n}, 100);',
                    code_after='const MAX = 1000;\nlet events = [];\nsetInterval(() => {\n  events.push(getEvent());\n  if (events.length > MAX) events.shift(); // cap size\n}, 100);',
                    file=rel, severity=Severity.HIGH, layer=Layer.BACKEND,
                    impact=7, effort=2, occurrences=pushes,
                    perf_gain='Prevents memory growth causing GC pressure and eventual OOM'
                ))
    
    def _check_db_config(self, src, f, rel):
        try:
            import json
            config = json.loads(src)
            pool = config.get('pool', config.get('database', {}).get('pool', {}))
            if isinstance(pool, dict):
                max_val = pool.get('max', pool.get('maximum', None))
                if max_val is not None and int(max_val) < 5:
                    self.issues.append(Issue(
                        id='NODE010', title=f'RDS Connection Pool Too Small (max={max_val})',
                        description=f'Database connection pool max={max_val}. Under concurrent load, requests queue waiting for a connection. Each queued request adds latency equal to the wait time. For production, pool should be 10-20.',
                        fix='Increase pool.max to 10-20 based on RDS instance size. Formula: pool_size = (core_count * 2) + spindle_count',
                        code_before=f'pool: {{ max: {max_val}, min: 0 }}\n// Only {max_val} concurrent DB operations',
                        code_after='pool: { max: 15, min: 2, acquire: 30000, idle: 10000 }\n// 15 concurrent DB connections',
                        file=rel, severity=Severity.HIGH, layer=Layer.BACKEND,
                        impact=8, effort=1, occurrences=1,
                        perf_gain='Eliminates connection queue wait time under concurrent load'
                    ))
        except: pass
