#!/usr/bin/env python3
"""
Performance Optimizer - Advanced Multi-Stack Analyzer
Usage:
  python optimizer.py --frontend /path/to/angular-repo
  python optimizer.py --backend /path/to/node-repo
  python optimizer.py --frontend /path/to/fe --backend /path/to/be
  python optimizer.py --project /path/to/monorepo
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from analyzers.angular_analyzer import AngularAnalyzer
from analyzers.node_analyzer    import NodeAnalyzer
from analyzers.sql_analyzer     import SqlAnalyzer
from analyzers.aws_analyzer     import AwsAnalyzer
from core.scorer                import Scorer
from reporter.html_reporter     import HtmlReporter


BANNER = """
┌─────────────────────────────────────────────────────┐
│   ⚡ PERFORMANCE OPTIMIZER v1.0                     │
│   Advanced Multi-Stack Analyzer                   │
│   Angular • Node.js • Seneca • SQL • AWS          │
│   NOT SonarQube — Performance-Specific Only        │
└─────────────────────────────────────────────────────┘
"""


def count_files(path: str) -> int:
    p = Path(path)
    count = 0
    for ext in ['*.ts', '*.js', '*.html', '*.sql', '*.json', '*.yml', '*.yaml']:
        for f in p.rglob(ext):
            if 'node_modules' not in str(f) and 'dist/' not in str(f):
                count += 1
    return count


def detect_tech(frontend_path, backend_path) -> str:
    techs = []
    for path in [frontend_path, backend_path]:
        if not path: continue
        p = Path(path)
        pkg = p / 'package.json'
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                if '@angular/core' in deps:
                    ver = deps['@angular/core'].lstrip('^~')
                    techs.append(f'Angular {ver.split(".")[0]}')
                if 'seneca' in deps:
                    techs.append('Seneca.js')
                if 'express' in deps:
                    techs.append('Express')
                node_ver = data.get('engines', {}).get('node', '')
                if node_ver:
                    techs.append(f'Node {node_ver}')
            except: pass
        # Check for AWS
        if any(p.rglob('serverless.yml')) or any(p.rglob('*.tf')) or any(p.rglob('cloudformation*.yml')):
            techs.append('AWS')
        # Check for SQL files
        if any(p.rglob('*.sql')):
            techs.append('SQL/RDS')
    return ' • '.join(techs) if techs else 'Angular • Node.js • Seneca • AWS RDS'


def run_analyzers(frontend_path, backend_path, verbose=False):
    all_issues = []

    if frontend_path:
        fp = Path(frontend_path)
        if not fp.exists():
            print(f'  ❌ Frontend path not found: {frontend_path}')
        else:
            print(f'  🅰️  Analyzing Angular/Frontend: {frontend_path}')
            analyzer = AngularAnalyzer(frontend_path)
            issues = analyzer.analyze()
            all_issues.extend(issues)
            print(f'     Found {len(issues)} frontend performance issues')
            if verbose:
                for i in issues:
                    print(f'       [{i.severity.value.upper()}] {i.id}: {i.title} ({i.file})')

    if backend_path:
        bp = Path(backend_path)
        if not bp.exists():
            print(f'  ❌ Backend path not found: {backend_path}')
        else:
            print(f'  🟢  Analyzing Node.js/Seneca: {backend_path}')
            analyzer = NodeAnalyzer(backend_path)
            issues = analyzer.analyze()
            all_issues.extend(issues)
            print(f'     Found {len(issues)} backend performance issues')

            print(f'  🗄️  Analyzing SQL/Database: {backend_path}')
            sql_analyzer = SqlAnalyzer(backend_path)
            sql_issues = sql_analyzer.analyze()
            all_issues.extend(sql_issues)
            print(f'     Found {len(sql_issues)} database performance issues')

            print(f'  ☁️  Analyzing AWS/Infra config: {backend_path}')
            aws_analyzer = AwsAnalyzer(backend_path)
            aws_issues = aws_analyzer.analyze()
            all_issues.extend(aws_issues)
            print(f'     Found {len(aws_issues)} infrastructure issues')

    # Also run SQL + AWS on frontend path if provided
    if frontend_path and Path(frontend_path).exists():
        aws_analyzer = AwsAnalyzer(frontend_path)
        aws_issues = aws_analyzer.analyze()
        all_issues.extend(aws_issues)

    return all_issues


def print_summary(scores, issues):
    s = scores
    print(f'''
┌{'─'*54}┐
│  PERFORMANCE SCAN RESULTS{'':29}│
├{'─'*54}┤
│  Overall Score : {s['overall']:>3}/100  {'(🔴 Critical)' if s['overall']<40 else '(⚠️ Needs Work)' if s['overall']<65 else '(🟡 Fair)' if s['overall']<80 else '(✅ Good)':16}{'':9}│
│  Frontend      : {s['frontend']:>3}/100{'':32}│
│  Backend       : {s['backend']:>3}/100{'':32}│
│  Database      : {s['database']:>3}/100{'':32}│
│  Infra         : {s['infra']:>3}/100{'':32}│
├{'─'*54}┤
│  🔴 Critical: {s['by_severity']['critical']:<4}  🟠 High: {s['by_severity']['high']:<4}  🟡 Medium: {s['by_severity']['medium']:<4}  🟢 Low: {s['by_severity']['low']:<4}  │
│  Total Issues : {s['total_issues']:>3}{'':38}│
└{'─'*54}┘''')

    if s['top3']:
        print('\n  🚨 TOP ISSUES (show to manager):')
        for i, t in enumerate(s['top3'], 1):
            print(f'   {i}. [{t["severity"].upper()}] {t["title"]}')
            print(f'      Impact: {t["perf_gain"]}')


def main():
    print(BANNER)

    parser = argparse.ArgumentParser(
        description='Performance Optimizer - Advanced Multi-Stack Analyzer'
    )
    parser.add_argument('--frontend', '-f', help='Path to Angular frontend repo', default=None)
    parser.add_argument('--backend',  '-b', help='Path to Node.js/Seneca backend repo', default=None)
    parser.add_argument('--project',  '-p', help='Path to monorepo (scans everything)', default=None)
    parser.add_argument('--output',   '-o', help='Output HTML file path', default='performance_report.html')
    parser.add_argument('--json',     '-j', help='Also output JSON report', action='store_true')
    parser.add_argument('--verbose',  '-v', help='Verbose output', action='store_true')
    args = parser.parse_args()

    frontend_path = args.frontend or args.project
    backend_path  = args.backend  or args.project

    if not frontend_path and not backend_path:
        print('  ERROR: Provide at least one of --frontend, --backend, or --project')
        print('  Example: python optimizer.py --frontend ./angular-app --backend ./node-api')
        parser.print_help()
        sys.exit(1)

    print(f'  📁 Frontend path : {frontend_path or "(not provided)"}')
    print(f'  📁 Backend path  : {backend_path  or "(not provided)"}')
    print(f'  💾 Output        : {args.output}')
    print()

    # Count files
    total_files = 0
    if frontend_path and Path(frontend_path).exists(): total_files += count_files(frontend_path)
    if backend_path  and Path(backend_path).exists() and backend_path != frontend_path:
        total_files += count_files(backend_path)

    # Detect tech stack
    tech = detect_tech(frontend_path, backend_path)
    print(f'  🔎 Detected tech : {tech}')
    print(f'  📁 Files to scan : {total_files}')
    print()
    print('  Running analyzers...')
    print()

    start = time.time()
    all_issues = run_analyzers(frontend_path, backend_path, verbose=args.verbose)
    duration = round(time.time() - start, 1)

    print(f'\n  ✔ Scan complete in {duration}s')

    # Deduplicate issues with same id+file
    seen = set()
    unique_issues = []
    for issue in all_issues:
        key = (issue.id, issue.file)
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)
    all_issues = unique_issues

    # Score
    scorer = Scorer()
    scores = scorer.compute(all_issues)

    print_summary(scores, all_issues)

    # Generate HTML
    scan_time = datetime.now().strftime('%d %b %Y, %I:%M %p')
    meta = {
        'project': Path(frontend_path or backend_path).name,
        'scan_time': scan_time,
        'files_scanned': total_files,
        'duration': duration,
        'tech': tech,
    }
    reporter = HtmlReporter(all_issues, scores, meta)
    reporter.render(args.output)
    print(f'\n  📊 HTML Report saved: {args.output}')
    print(f'  💡 Open in browser to see interactive dashboard')

    # JSON output
    if args.json:
        json_path = args.output.replace('.html', '.json')
        report_data = {
            'meta': meta,
            'scores': scores,
            'issues': [i.to_dict() for i in all_issues],
        }
        with open(json_path, 'w') as jf:
            json.dump(report_data, jf, indent=2)
        print(f'  💾 JSON Report saved: {json_path}')

    print()
    print('  Done! Show the HTML report to your manager. ⚡')
    print()


if __name__ == '__main__':
    main()
