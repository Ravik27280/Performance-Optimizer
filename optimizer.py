#!/usr/bin/env python3
"""
Performance Optimizer v2.0 - Advanced Multi-Stack Analyzer
Angular • Node.js • Seneca • SQL • AWS
NOT SonarQube — Performance-Specific Only

Usage:
  python optimizer.py --frontend /path/to/angular-repo
  python optimizer.py --backend /path/to/node-repo
  python optimizer.py --project /path/to/monorepo
  python optimizer.py --frontend ./fe --backend ./be --fail-on critical --min-score 70
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set

sys.path.insert(0, os.path.dirname(__file__))

from analyzers.angular_analyzer import AngularAnalyzer
from analyzers.react_analyzer import ReactAnalyzer
from analyzers.node_analyzer import NodeAnalyzer
from analyzers.sql_analyzer import SqlAnalyzer
from analyzers.aws_analyzer import AwsAnalyzer
from core.scorer import Scorer
from core.issue import Severity, Issue
from reporter.html_reporter import HtmlReporter

BANNER = """
┌─────────────────────────────────────────────────────────────┐
│   PERFORMANCE OPTIMIZER v2.5 PRO                            │
│   Enterprise Multi-Stack Performance Intelligence          │
│   Angular • React • Node.js • SQL • AWS Cloud               │
│   NOT SonarQube — Performance-Specific Only                 │
└─────────────────────────────────────────────────────────────┘
"""

DEFAULT_EXCLUDES = [
    'node_modules', '.git', 'dist', 'build', '.angular', '.next',
    'coverage', '.vscode', '.idea', 'package-lock.json', 'yarn.lock'
]

def should_exclude(path_str: str, custom_excludes: List[str]) -> bool:
    normalized = path_str.replace('\\', '/')
    all_excludes = DEFAULT_EXCLUDES + custom_excludes
    return any(ex in normalized for ex in all_excludes if ex)

def count_files(path: str, custom_excludes: List[str]) -> int:
    p = Path(path)
    count = 0
    extensions = ['*.ts', '*.js', '*.jsx', '*.tsx', '*.html', '*.sql', '*.json', '*.yml', '*.yaml', '*.tf']
    for ext in extensions:
        for f in p.rglob(ext):
            if not should_exclude(str(f), custom_excludes):
                count += 1
    return count

def detect_tech(frontend_path: str, backend_path: str) -> str:
    techs = []
    checked_paths = set(filter(None, [frontend_path, backend_path]))
    for path in checked_paths:
        p = Path(path)
        pkg = p / 'package.json'
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding='utf-8', errors='ignore'))
                deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                if '@angular/core' in deps:
                    ver = deps['@angular/core'].lstrip('^~')
                    techs.append(f'Angular {ver.split(".")[0]}')
                if 'react' in deps:
                    ver = deps['react'].lstrip('^~')
                    techs.append(f'React {ver.split(".")[0]}')
                if 'next' in deps:
                    techs.append('Next.js')
                if 'vue' in deps:
                    techs.append('Vue')
                if 'seneca' in deps:
                    techs.append('Seneca.js')
                if 'express' in deps:
                    techs.append('Express')
                if 'nest' in deps or '@nestjs/core' in deps:
                    techs.append('NestJS')
                node_ver = data.get('engines', {}).get('node', '')
                if node_ver:
                    techs.append(f'Node {node_ver}')
            except Exception:
                pass

        # Check for AWS Infra
        if any(p.rglob('serverless.yml')) or any(p.rglob('*.tf')) or any(p.rglob('cloudformation*.yml')):
            if 'AWS' not in techs:
                techs.append('AWS Cloud')
        # Check for SQL files
        if any(p.rglob('*.sql')):
            if 'SQL/RDS' not in techs:
                techs.append('SQL/RDS')

    return ' • '.join(techs) if techs else 'Angular • React • Node.js • SQL • AWS'

def run_analyzers(frontend_path: str, backend_path: str, verbose: bool = False) -> List[Issue]:
    all_issues = []
    is_monorepo = (frontend_path and backend_path and Path(frontend_path).resolve() == Path(backend_path).resolve())

    if is_monorepo or (frontend_path and not backend_path):
        target = frontend_path
        print(f'  🔍 Analyzing unified project: {target}')
        if Path(target).exists():
            print('     🅰️  Running Angular Analyzer...')
            all_issues.extend(AngularAnalyzer(target).analyze())
            print('     ⚛️  Running React Analyzer...')
            all_issues.extend(ReactAnalyzer(target).analyze())
            print('     🟢  Running Node.js & Seneca Analyzer...')
            all_issues.extend(NodeAnalyzer(target).analyze())
            print('     🗄️  Running SQL & Database Analyzer...')
            all_issues.extend(SqlAnalyzer(target).analyze())
            print('     ☁️  Running AWS & Infrastructure Analyzer...')
            all_issues.extend(AwsAnalyzer(target).analyze())
        return all_issues

    # Separate frontend and backend paths
    if frontend_path:
        fp = Path(frontend_path)
        if fp.exists():
            print(f'  🅰️  Analyzing Angular/Frontend: {frontend_path}')
            issues = AngularAnalyzer(frontend_path).analyze()
            all_issues.extend(issues)
            print(f'     Found {len(issues)} Angular performance issues')

            print(f'  ⚛️  Analyzing React/Frontend: {frontend_path}')
            react_issues = ReactAnalyzer(frontend_path).analyze()
            all_issues.extend(react_issues)
            print(f'     Found {len(react_issues)} React performance issues')
        else:
            print(f'  ❌ Frontend path not found: {frontend_path}')

    if backend_path:
        bp = Path(backend_path)
        if bp.exists():
            print(f'  🟢  Analyzing Node.js/Seneca: {backend_path}')
            node_issues = NodeAnalyzer(backend_path).analyze()
            all_issues.extend(node_issues)
            print(f'     Found {len(node_issues)} backend performance issues')

            print(f'  🗄️  Analyzing SQL/Database: {backend_path}')
            sql_issues = SqlAnalyzer(backend_path).analyze()
            all_issues.extend(sql_issues)
            print(f'     Found {len(sql_issues)} database performance issues')

            print(f'  ☁️  Analyzing AWS/Infra config: {backend_path}')
            aws_issues = AwsAnalyzer(backend_path).analyze()
            all_issues.extend(aws_issues)
            print(f'     Found {len(aws_issues)} infrastructure issues')
        else:
            print(f'  ❌ Backend path not found: {backend_path}')

    return all_issues

def print_summary(scores: dict, issues: List[Issue]):
    s = scores
    print(f'''
┌{'─'*58}┐
│  PERFORMANCE SCAN RESULTS                                │
├{'─'*58}┤
│  Overall Score : {s['overall']:>3}/100  {'(🔴 Critical)' if s['overall']<45 else '(⚠️ Needs Work)' if s['overall']<65 else '(🟡 Fair)' if s['overall']<80 else '(✅ Good)':16}{'':13}│
│  Frontend      : {s['frontend']:>3}/100{'':36}│
│  Backend       : {s['backend']:>3}/100{'':36}│
│  Database      : {s['database']:>3}/100{'':36}│
│  Infra         : {s['infra']:>3}/100{'':36}│
├{'─'*58}┤
│  🔴 Critical: {s['by_severity']['critical']:<4}  🟠 High: {s['by_severity']['high']:<4}  🟡 Medium: {s['by_severity']['medium']:<4}  🟢 Low: {s['by_severity']['low']:<4}  │
│  Total Issues : {s['total_issues']:>3}{'':42}│
└{'─'*58}┘''')

    if s.get('top3'):
        print('\n  🚨 TOP ACTIONABLE FIXES (Show to leadership):')
        for idx, t in enumerate(s['top3'], 1):
            line_str = f":{t['line_number']}" if t.get('line_number') else ""
            print(f'   {idx}. [{t["severity"].upper()}] {t["title"]}')
            print(f'      Location : {t["file"]}{line_str}')
            print(f'      Gain     : {t["perf_gain"]}')

def generate_markdown_summary(out_path: str, scores: dict, meta: dict, issues: List[Issue]):
    s = scores
    md = f"""# Performance Optimizer Scan Summary

**Overall Health Score**: `{s['overall']}/100`  
**Target Project**: `{meta.get('project', 'Application')}`  
**Scan Timestamp**: `{meta.get('scan_time')}`  
**Analyzed Files**: `{meta.get('files_scanned')}` in `{meta.get('duration')}s`  

---

### 📊 Layer Breakdown
| Layer | Score | Status |
| :--- | :--- | :--- |
| **Frontend (Angular / React)** | `{s['frontend']}/100` | {'🔴 Critical' if s['frontend']<50 else '🟠 High Risk' if s['frontend']<70 else '✅ Good'} |
| **Node.js / Seneca** | `{s['backend']}/100` | {'🔴 Critical' if s['backend']<50 else '🟠 High Risk' if s['backend']<70 else '✅ Good'} |
| **SQL / Database** | `{s['database']}/100` | {'🔴 Critical' if s['database']<50 else '🟠 High Risk' if s['database']<70 else '✅ Good'} |
| **AWS / Cloud Infra** | `{s['infra']}/100` | {'🔴 Critical' if s['infra']<50 else '🟠 High Risk' if s['infra']<70 else '✅ Good'} |

### 🚨 Top Critical Bottlenecks
"""
    for idx, t in enumerate(s.get('top3', []), 1):
        md += f"\n{idx}. **[{t['severity'].upper()}] {t['title']}**\n"
        md += f"   - **File**: `{t['file']}`\n"
        md += f"   - **Impact**: {t['perf_gain']}\n"

    md += "\n> 💡 *Generated by [Performance Optimizer v2.5 PRO](https://github.com/Ravik27280/Performance-Optimizer)*\n"

    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(md)
    print(f'  📝 Markdown summary saved: {out_path}')

def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description='Performance Optimizer v2.5 PRO - Enterprise Multi-Stack Performance Analyzer'
    )
    parser.add_argument('--frontend', '-f', help='Path to Angular frontend repo', default=None)
    parser.add_argument('--backend',  '-b', help='Path to Node.js/Seneca backend repo', default=None)
    parser.add_argument('--project',  '-p', help='Path to monorepo (scans entire workspace)', default=None)
    parser.add_argument('--output',   '-o', help='Output HTML report path', default='performance_report.html')
    parser.add_argument('--json',     '-j', help='Output machine-readable JSON report', action='store_true')
    parser.add_argument('--markdown-summary', '-m', help='Generate markdown report summary for PR comments', default=None)
    parser.add_argument('--exclude',  '-e', help='Comma-separated directory patterns to exclude', default='')
    parser.add_argument('--fail-on',  help='Fail CI with exit 1 if issues matching severity exist (critical, high)', default=None)
    parser.add_argument('--min-score', help='Fail CI with exit 1 if overall score is below threshold (0-100)', type=int, default=None)
    parser.add_argument('--verbose',  '-v', help='Verbose terminal output', action='store_true')
    args = parser.parse_args()

    frontend_path = args.frontend or args.project
    backend_path  = args.backend  or args.project
    custom_excludes = [x.strip() for x in args.exclude.split(',') if x.strip()]

    if not frontend_path and not backend_path:
        print('  ❌ ERROR: Provide at least one of --frontend, --backend, or --project')
        print('  Example: python optimizer.py --frontend ./angular-app --backend ./node-api')
        parser.print_help()
        sys.exit(1)

    print(f'  📁 Frontend path : {frontend_path or "(not provided)"}')
    print(f'  📁 Backend path  : {backend_path  or "(not provided)"}')
    print(f'  💾 HTML Output   : {args.output}')

    total_files = 0
    if frontend_path and Path(frontend_path).exists():
        total_files += count_files(frontend_path, custom_excludes)
    if backend_path and Path(backend_path).exists() and Path(backend_path).resolve() != Path(frontend_path or '').resolve():
        total_files += count_files(backend_path, custom_excludes)

    tech = detect_tech(frontend_path, backend_path)
    print(f'  🔎 Detected tech : {tech}')
    print(f'  📁 Files to scan : {total_files}')
    print('\n  Running analyzers...')

    start_time = time.time()
    all_issues = run_analyzers(frontend_path, backend_path, verbose=args.verbose)
    duration = round(time.time() - start_time, 2)

    print(f'\n  ✔ Scan completed in {duration}s')

    # Deduplicate issues with same (id, file, line_number)
    seen: Set[tuple] = set()
    unique_issues = []
    for issue in all_issues:
        key = (issue.id, issue.file, issue.line_number)
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)
    all_issues = unique_issues

    # Compute scores
    scorer = Scorer()
    scores = scorer.compute(all_issues)
    print_summary(scores, all_issues)

    # Render HTML Dashboard
    scan_time = datetime.now().strftime('%d %b %Y, %I:%M %p')
    project_name = Path(frontend_path or backend_path).name or "Performance Project"
    meta = {
        'project': project_name,
        'scan_time': scan_time,
        'files_scanned': total_files,
        'duration': duration,
        'tech': tech,
    }

    reporter = HtmlReporter(all_issues, scores, meta)
    reporter.render(args.output)
    print(f'\n  📊 Interactive HTML Dashboard saved: {args.output}')

    # JSON export
    if args.json:
        json_path = args.output.replace('.html', '.json') if args.output.endswith('.html') else f"{args.output}.json"
        report_data = {
            'meta': meta,
            'scores': scores,
            'issues': [i.to_dict() for i in all_issues],
        }
        with open(json_path, 'w', encoding='utf-8') as jf:
            json.dump(report_data, jf, indent=2)
        print(f'  💾 Machine-readable JSON saved: {json_path}')

    # Markdown summary
    if args.markdown_summary:
        generate_markdown_summary(args.markdown_summary, scores, meta, all_issues)

    # CI/CD Quality Gate evaluation
    exit_code = 0
    if args.fail_on:
        threshold_sev = args.fail_on.lower()
        critical_count = scores['by_severity'].get('critical', 0)
        high_count = scores['by_severity'].get('high', 0)

        if threshold_sev == 'critical' and critical_count > 0:
            print(f'\n  ❌ CI QUALITY GATE FAILED: Found {critical_count} critical performance issues (--fail-on critical)')
            exit_code = 1
        elif threshold_sev == 'high' and (critical_count > 0 or high_count > 0):
            print(f'\n  ❌ CI QUALITY GATE FAILED: Found {critical_count} critical and {high_count} high issues (--fail-on high)')
            exit_code = 1

    if args.min_score is not None:
        if scores['overall'] < args.min_score:
            print(f'\n  ❌ CI QUALITY GATE FAILED: Overall score {scores["overall"]} is below minimum threshold of {args.min_score} (--min-score {args.min_score})')
            exit_code = 1

    if exit_code == 0:
        print('\n  ✔ Done! All quality checks passed.\n')
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
