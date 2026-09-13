# Performance Optimizer v2.5 PRO — Advanced Multi-Stack Analyzer

> **NOT SonarQube.** This is an enterprise static performance & latency intelligence engine.  
> **Targeted Runtimes**: Angular (14–19+), React (17–19+) & Next.js, Node.js & Seneca.js, SQL / Database Indexes, and AWS Serverless.  
> Zero external dependencies — runs in `<0.05s` with Python 3.7+ standard library.

[![Live Portal](https://img.shields.io/badge/Live_Portal-GitHub_Pages-6366f1?style=for-the-badge&logo=github)](https://ravik27280.github.io/Performance-Optimizer/)
[![Python 3.7+](https://img.shields.io/badge/Python-3.7+-06b6d4?style=for-the-badge&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-10b981?style=for-the-badge)](https://opensource.org/licenses/MIT)

🌐 **Live Interactive Web Portal & Diagnostic Scanner**: [https://ravik27280.github.io/Performance-Optimizer/](https://ravik27280.github.io/Performance-Optimizer/)

---

## ⚡ Installation & CLI Setup

Install locally or as an editable package for global terminal access:

```bash
# Clone the repository
git clone https://github.com/Ravik27280/Performance-Optimizer.git
cd Performance-Optimizer

# Install package globally / in virtual environment
pip install -e .

# Verify CLI installation
perf-optimizer --help
```

---

## 🚀 Quick Start Examples

```bash
# 1. Scan current repository / monorepo
perf-optimizer --project .

# 2. Scan separate frontend and backend directories
perf-optimizer --frontend ./angular-app --backend ./node-api

# 3. Enforce CI/CD Quality Gate (Exit 1 on critical issues or score < 75)
perf-optimizer --project . --fail-on critical --min-score 75

# 4. Generate HTML dashboard, JSON audit, and PR Markdown summary
perf-optimizer --project . --json --markdown-summary pr_summary.md --output report.html

# 5. Alternatively, run directly with python (zero pip packages required)
python optimizer.py --project . --verbose
```

---

## 📊 Output Formats

- **`performance_report.html`** — Interactive executive dashboard with code diff previews, ROI impact calculations, and dark/light modes.
- **`performance_report.json`** — Machine-readable audit data with exact line numbers and defect categories for custom tooling.
- **`pr_summary.md`** — Markdown report table designed for automated Pull Request comments in GitHub Actions and GitLab CI.

---

## 🤖 GitHub Actions CI/CD Integration

Create `.github/workflows/perf-audit.yml` to automatically run audits on every Pull Request:

```yaml
name: Performance Quality Gate

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install Performance Optimizer
        run: pip install -e .
      - name: Run Performance Audit
        run: |
          perf-optimizer --project . --fail-on critical --min-score 75
```

---

## 🛡️ CLI Flags & Options

| Argument | Description | Example |
|---|---|---|
| `--project`, `-p` | Path to monorepo or project (scans entire workspace) | `--project .` |
| `--frontend`, `-f` | Path to Angular or React frontend codebase | `--frontend ./src/web` |
| `--backend`, `-b` | Path to Node.js/Seneca/Express codebase | `--backend ./src/api` |
| `--fail-on` | Fails CI with exit code `1` if issues matching severity exist | `--fail-on critical` or `--fail-on high` |
| `--min-score` | Fails CI with exit code `1` if overall score is below threshold | `--min-score 75` |
| `--exclude`, `-e` | Comma-separated directory patterns to exclude | `--exclude "legacy,tmp,e2e"` |
| `--json`, `-j` | Generates machine-readable JSON report | `--json` |
| `--markdown-summary`, `-m` | Generates PR comment summary file | `--markdown-summary pr_summary.md` |
| `--output`, `-o` | Custom HTML report output path | `--output ./dist/perf_report.html` |
| `--verbose`, `-v` | Detailed terminal output during scan | `--verbose` |

---

## 🔇 Inline Rule Suppression

Suppress false positives or accepted trade-offs directly in code:

```typescript
// Angular / TypeScript / JavaScript
// perf-ignore ANG001
@Component({ ... })

// Node.js
// perf-ignore NODE001
const bootConfig = fs.readFileSync('boot.json', 'utf8');

// SQL / Schema
-- perf-ignore SQL004
CREATE TABLE temp_session ( ... );
```

---

## 🔍 What It Detects (Performance-Specific)

### Angular / Modern Frontend (Angular 16–19+)
| ID | Check | Category | Impact |
|---|---|---|---|
| **ANG001** | Missing OnPush Change Detection | DOM Re-render | 65% re-render reduction |
| **ANG002** | Direct @Input Property Mutation | Change Detection | Restores OnPush change detection |
| **ANG003** | `detectChanges()` Synchronously Inside Loop | Render Cycle | Eliminates N render cycles |
| **ANG004** | Observable Memory Leak (Missing Unsubscribe / Teardown) | Memory Leak | Eliminates heap growth per route |
| **ANG005** | Nested `subscribe()` Callback Anti-pattern | Concurrency | Eliminates race conditions & request leaks |
| **ANG006** | API Call Without Pagination (Full Collection Fetch) | Network & Heap | 70%+ TTI improvement |
| **ANG007** | Missing `debounceTime` on Reactive Form Streams | Network | Up to 85% fewer API requests |
| **ANG008** | Missing HTTP Response Caching (`shareReplay`) | Network | Eliminates duplicate network calls |
| **ANG009** | `*ngFor` Without `trackBy` or `@for` Without `track` | DOM Performance | 99% fewer DOM node recreations |
| **ANG010** | Missing Virtual Scrolling for Large Lists | DOM Performance | Renders only ~20 DOM nodes |
| **ANG011** | Method Calls in Template Interpolation | DOM Re-render | Eliminates expensive method re-evaluations |
| **ANG012** | Wildcard / Full Library Imports (`lodash`, `rxjs/Rx`) | Bundle Size | 50–80KB bundle reduction |
| **ANG013** | No Lazy Loading Routes (All Eager at Startup) | Bundle Size | 40–60% initial bundle cut |
| **ANG014** | Heavy Subcomponents Rendered Without `@defer` | Core Web Vitals | Speeds up LCP & initial chunk parse |

### React & Next.js (React 17–19+)
| ID | Check | Category | Impact |
|---|---|---|---|
| **REACT001** | Array Index as `key` in List Rendering | Reconciliation | Enables DOM node reuse on mutations |
| **REACT002** | Direct State Mutation Anti-pattern | State Management | Prevents broken re-render schedules |
| **REACT003** | `useEffect` Missing Dependency Array | Render Loop | Eliminates runaway infinite re-render loops |
| **REACT004** | Expensive Array Calculations Without `useMemo` | CPU Efficiency | Avoids heavy sorting/filtering recalculations |
| **REACT005** | Eager Route Components Without `React.lazy()` | Bundle Size | 30–50% smaller initial JS chunks |
| **REACT006** | Context Value Recreated as New Object on Render | Re-render Cascade | Stops cascading subtree re-renders |

### Node.js / Seneca / Express Backend
| ID | Check | Category | Impact |
|---|---|---|---|
| **NODE001** | Synchronous `fs` Calls in Runtime Execution Paths | Event Loop | Unblocks Node.js event loop |
| **NODE002** | Sequential `await` on Independent Operations | Concurrency | Up to 50% latency reduction |
| **NODE003** | Promise Chains Without `.catch()` | Stability | Prevents unhandled rejections |
| **NODE004** | **N+1 Database Query Pattern in Loop** | Database I/O | O(N) → O(1) query roundtrips |
| **NODE005** | **Database Queries Without LIMIT (Returns All Rows)** | Database I/O | Caps payload and memory bounds |
| **NODE006** | No Caching Layer for Repeated Queries (Redis) | Database I/O | 60–90% database load reduction |
| **NODE007** | API Response Over-fetching (`SELECT *` to `res.json`) | Serialization | Smaller payloads, faster JSON encode |
| **NODE008** | Express Missing Gzip/Brotli Compression | Network | 70–90% smaller response sizes |
| **NODE009** | Unbounded In-Memory Array Growth | Memory Leak | Prevents OOM crashes |
| **NODE010** | Database Connection Pool Configured Too Small | Database I/O | Eliminates connection queue delays |
| **NODE011** | **EventEmitter Memory Leak (Missing Listener Teardown)** | Memory Leak | Eliminates closure/listener leaks |
| **NODE012** | **HTTP Requests Missing Connection Reuse (`keepAlive: true`)** | Network | Saves 50–100ms TLS handshakes |
| **SEN001** | Seneca `.act()` Inside Iteration Loop | Microservice RPC | N×latency → max(latency) |
| **SEN002** | Seneca `.act()` Without Explicit Timeout | Stability | Prevents cascading request hangs |

### SQL / RDS / Database
| ID | Check | Category | Impact |
|---|---|---|---|
| **SQL001** | `SELECT *` Column Over-fetching | Database I/O | Faster queries, less I/O |
| **SQL002** | UPDATE/DELETE Without WHERE Clause | Data Integrity | Prevents full table locks & corruption |
| **SQL003** | SELECT Without LIMIT | Result Bounds | Fixed result set size |
| **SQL004** | **Missing Index on Foreign Key Columns** | Indexing | Converts O(N) table scan to O(log N) |
| **SQL005** | SQL Query Built via String Concatenation | Plan Cache | Reuses compiled query plans |
| **SQL006** | `LIKE '%query'` Leading Wildcard (B-Tree Incompatible) | Indexing | Enables index seeks |
| **SQL007** | **Deep OFFSET Pagination Antipattern** | Query Optimization | Keyset pagination saves O(N) discard |

### AWS / Serverless / Cloud Infrastructure
| ID | Check | Category | Impact |
|---|---|---|---|
| **AWS001** | Lambda Memory Allocated Too Low (<512MB) | CPU & Latency | 50–75% faster execution |
| **AWS002** | Static S3 Hosting Without CloudFront CDN | Edge Delivery | 300ms → 20ms global asset delivery |
| **AWS003** | Lambda Functions Without Explicit Timeout | Cost & Timeouts | Prevents runaway costs on hangs |
| **AWS005** | **Lambda Direct to RDS Without RDS Proxy** | Connection Pool | Prevents DB connection exhaustion |

---

## 📈 Scoring Engine

- **Asymptotic Logarithmic Curve**: Avoids artificial zero-score cliffs; accurately reflects true performance health for codebases of any size.
- **Architectural Layer Weights**:
  $$\text{Overall} = 40\% \text{Frontend} + 30\% \text{Backend} + 20\% \text{Database} + 10\% \text{Infra}$$
- **Priority Rank**: Calculated via $\text{Impact} / \max(\text{Effort}, 1)$ to prioritize high-impact, low-effort wins.

---

## 🧪 Automated Testing

Run the included unit test suite:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
