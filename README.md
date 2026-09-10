# ⚡ Performance Optimizer — Advanced Multi-Stack Analyzer

> **NOT SonarQube.** This is a pure performance-specific analyzer.  
> Focus: Angular UI performance, Node.js/Seneca bottlenecks, SQL/RDS query issues, AWS config.

---

## 🚀 Quick Start

```bash
# Install dependencies (only standard library needed!)
python3 --version  # Needs Python 3.7+

# Scan frontend only
python3 optimizer.py --frontend /path/to/angular-repo

# Scan backend only
python3 optimizer.py --backend /path/to/node-repo

# Scan both (recommended)
python3 optimizer.py --frontend /path/to/angular-repo --backend /path/to/node-repo

# Monorepo
python3 optimizer.py --project /path/to/monorepo

# With JSON output + verbose
python3 optimizer.py --frontend ./fe --backend ./be --json --verbose
```

## 📊 Output

- `performance_report.html` — Interactive dashboard (open in browser)
- `performance_report.json` — Machine-readable data (with `--json` flag)

---

## 🔍 What It Detects (Performance-Specific)

### Angular / Frontend
| ID | Check | Impact |
|---|---|---|
| ANG001 | Missing OnPush Change Detection | 65% re-render reduction |
| ANG002 | Mutable @Input mutation (breaks OnPush) | Correct CD behavior |
| ANG003 | detectChanges() inside loop | Eliminates N render cycles |
| ANG004 | **Observable memory leaks (no unsubscribe)** | Eliminates memory growth |
| ANG005 | Nested subscribe() — callback hell | Race condition elimination |
| ANG006 | **API call without pagination (FETCH ALL)** | 70%+ TTI improvement |
| ANG007 | No debounceTime on user input | 85% fewer API calls |
| ANG008 | No HTTP response caching (shareReplay) | Eliminates redundant requests |
| ANG009 | ***ngFor without trackBy** | 99% fewer DOM operations |
| ANG010 | **No virtual scrolling for large lists** | Renders only ~20 DOM nodes |
| ANG011 | Method calls in templates | Eliminates repeated computations |
| ANG012 | Wildcard imports (bundle bloat) | 50-70KB bundle reduction |
| ANG013 | No lazy loading routes | 40-60% initial bundle reduction |

### Node.js / Seneca Backend
| ID | Check | Impact |
|---|---|---|
| NODE001 | Sync fs calls (blocks event loop) | Unblocks concurrency |
| NODE002 | Sequential await for independent ops | 50% latency reduction |
| NODE003 | Missing .catch() handlers | Prevents silent failures |
| NODE004 | **N+1 database query pattern** | O(N) → O(1) DB queries |
| NODE005 | **No LIMIT on DB queries (returns ALL rows)** | Fixed response size |
| NODE006 | No caching layer (Redis) | 60-90% DB load reduction |
| NODE007 | API over-fetching (SELECT *) | Smaller payloads |
| NODE008 | No gzip/brotli compression | 70-90% response size reduction |
| NODE009 | Unbounded in-memory array | Prevents OOM |
| NODE010 | RDS connection pool too small | Eliminates queue wait |
| SEN001 | **Seneca .act() inside loop** | N×latency → max(latency) |
| SEN002 | Seneca .act() without timeout | Prevents hanging requests |

### SQL / RDS
| ID | Check | Impact |
|---|---|---|
| SQL001 | SELECT * usage | Faster queries, less I/O |
| SQL002 | UPDATE/DELETE without WHERE | Data integrity |
| SQL003 | SELECT without LIMIT | Fixed result size |
| SQL004 | **Missing indexes on FK columns** | O(N) → O(log N) lookups |
| SQL005 | SQL string concatenation (no plan cache) | DB plan reuse |
| SQL006 | LIKE with leading wildcard | Enables index usage |

### AWS / Infrastructure
| ID | Check | Impact |
|---|---|---|
| AWS001 | Lambda memory too low | 50-75% faster execution |
| AWS002 | No CloudFront CDN | 200ms → 20ms static assets |
| AWS003 | Lambda without timeout | Prevents runaway costs |

---

## 📈 Scoring

- Each issue carries a **severity** (Critical/High/Medium/Low) and **penalty weight**
- **Overall score** = weighted average: Frontend 40% + Backend 30% + DB 20% + Infra 10%
- **Priority rank** = Impact/Effort ratio (fix high-impact, low-effort first)

---

## 🛠 Requirements

- Python 3.7+
- No external packages required (pure stdlib)
- HTML report requires browser with JavaScript (Chart.js loaded from CDN)

---

## 📁 Project Structure

```
perf-optimizer/
├── optimizer.py          # Entry point
├── analyzers/
│   ├── angular_analyzer.py   # Angular/TypeScript checks
│   ├── node_analyzer.py      # Node.js + Seneca checks
│   ├── sql_analyzer.py       # SQL query checks
│   └── aws_analyzer.py       # AWS config checks
├── core/
│   ├── issue.py              # Issue data model + severity
│   └── scorer.py             # Scoring engine
└── reporter/
    └── html_reporter.py      # Interactive HTML dashboard generator
```

---

## 💡 Tips

- Run with `--verbose` to see every issue with file paths in terminal
- Run with `--json` to get machine-readable output for CI/CD integration
- The HTML report is **self-contained** — email it to your manager directly
- Re-run after fixes to see score improvement
