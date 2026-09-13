import os
import re
from pathlib import Path
from typing import List, Tuple, Optional
from core.issue import Issue, Severity, Layer

class AngularAnalyzer:
    def __init__(self, path: str):
        self.path = Path(path)
        self.issues: List[Issue] = []

    def analyze(self) -> List[Issue]:
        for f in self.path.rglob('*.ts'):
            if any(x in str(f) for x in ['node_modules', '.spec.', 'dist/', '.d.ts', '.angular', '.git']):
                continue
            try:
                src = f.read_text(encoding='utf-8', errors='ignore')
                rel = str(f.relative_to(self.path)).replace('\\', '/')
                lines = src.splitlines()

                if '@Component' in src:
                    self._check_component(src, lines, rel)
                if 'subscribe(' in src:
                    self._check_subscriptions(src, lines, rel)
                if 'HttpClient' in src or 'http.get' in src.lower() or 'this.http.' in src:
                    self._check_http(src, lines, rel)
                self._check_imports(src, lines, rel)
            except Exception:
                pass

        for f in self.path.rglob('*.html'):
            if any(x in str(f) for x in ['node_modules', 'dist/', '.angular', '.git']):
                continue
            try:
                src = f.read_text(encoding='utf-8', errors='ignore')
                rel = str(f.relative_to(self.path)).replace('\\', '/')
                lines = src.splitlines()
                self._check_template(src, lines, rel)
            except Exception:
                pass

        for f in self.path.rglob('*-routing.module.ts'):
            if any(x in str(f) for x in ['node_modules', 'dist/', '.angular', '.git']):
                continue
            try:
                src = f.read_text(encoding='utf-8', errors='ignore')
                rel = str(f.relative_to(self.path)).replace('\\', '/')
                lines = src.splitlines()
                self._check_routing(src, lines, rel)
            except Exception:
                pass

        return self.issues

    def _is_suppressed(self, lines: List[str], line_idx: int, rule_id: str) -> bool:
        """Checks for // perf-ignore [RULE_ID] on current or previous line."""
        check_lines = []
        if 0 <= line_idx < len(lines):
            check_lines.append(lines[line_idx])
        if 0 <= line_idx - 1 < len(lines):
            check_lines.append(lines[line_idx - 1])
        for cl in check_lines:
            if f'perf-ignore {rule_id}' in cl or 'perf-ignore-all' in cl:
                return True
        return False

    def _find_line(self, lines: List[str], regex_or_str: str) -> Tuple[int, str]:
        for idx, line in enumerate(lines, 1):
            if isinstance(regex_or_str, str) and regex_or_str in line:
                return idx, line.strip()
            elif hasattr(regex_or_str, 'search') and regex_or_str.search(line):
                return idx, line.strip()
        return 1, (lines[0].strip() if lines else '')

    def _check_component(self, src: str, lines: List[str], rel: str):
        # ANG001: Missing OnPush Change Detection
        if '@Component' in src and 'ChangeDetectionStrategy.OnPush' not in src:
            line_no, snippet = self._find_line(lines, '@Component')
            if not self._is_suppressed(lines, line_no - 1, 'ANG001'):
                self.issues.append(Issue(
                    id='ANG001',
                    title='Missing OnPush Change Detection Strategy',
                    description='Component uses default change detection. Angular dirty-checks the entire component subtree on every DOM event, timer, and HTTP response. OnPush restricts checks to @Input() reference changes or async pipe emissions.',
                    fix='Add `changeDetection: ChangeDetectionStrategy.OnPush` to @Component decorator.',
                    code_before='@Component({\n  selector: "app-feature",\n  templateUrl: "./feature.component.html"\n})\nexport class FeatureComponent {}',
                    code_after='@Component({\n  selector: "app-feature",\n  templateUrl: "./feature.component.html",\n  changeDetection: ChangeDetectionStrategy.OnPush\n})\nexport class FeatureComponent {}',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='DOM Re-renders',
                    doc_url='https://angular.dev/best-practices/runtime-performance#onpush-change-detection',
                    severity=Severity.HIGH,
                    layer=Layer.FRONTEND,
                    impact=9,
                    effort=3,
                    occurrences=1,
                    perf_gain='Up to 65% reduction in DOM re-renders for data-heavy UIs'
                ))

        # ANG002: Direct Input Mutation
        input_props = re.findall(r'@Input\(\)\s+(?:public\s+|readonly\s+)?(\w+)', src)
        for prop in input_props:
            push_pattern = rf'this\.{prop}\.push\('
            m = re.search(push_pattern, src)
            if m:
                line_no, snippet = self._find_line(lines, f'this.{prop}.push(')
                if not self._is_suppressed(lines, line_no - 1, 'ANG002'):
                    self.issues.append(Issue(
                        id='ANG002',
                        title=f'Direct Mutation of @Input Property `{prop}`',
                        description=f'Mutating `this.{prop}.push(...)` alters internal state without changing object reference. With OnPush, Angular will fail to detect changes, leading to stale DOM updates.',
                        fix=f'Use immutable array spreading: `this.{prop} = [...this.{prop}, item];`',
                        code_before=f'this.{prop}.push(newItem); // Fails OnPush change detection',
                        code_after=f'this.{prop} = [...this.{prop}, newItem]; // Emits new object reference',
                        file=rel,
                        line_number=line_no,
                        code_snippet=snippet,
                        category='Change Detection',
                        doc_url='https://angular.dev/best-practices/runtime-performance',
                        severity=Severity.HIGH,
                        layer=Layer.FRONTEND,
                        impact=7,
                        effort=2,
                        occurrences=1,
                        perf_gain='Guarantees correct change propagation under OnPush'
                    ))
                    break

        # ANG003: detectChanges inside loop
        for idx, line in enumerate(lines, 1):
            if 'detectChanges()' in line:
                # Check previous 8 lines for loop declarations
                prev_block = '\n'.join(lines[max(0, idx - 8):idx])
                if any(loop_k in prev_block for loop_k in ['for (', 'for(', 'forEach(', '.map(']):
                    if not self._is_suppressed(lines, idx - 1, 'ANG003'):
                        self.issues.append(Issue(
                            id='ANG003',
                            title='detectChanges() Synchronously Called Inside Loop',
                            description='Triggering change detection inside a loop forces synchronous DOM calculation on every single item iteration, locking the browser UI thread.',
                            fix='Batch updates and call `markForCheck()` or trigger `detectChanges()` once after loop terminates.',
                            code_before='items.forEach(item => {\n  this.updateItem(item);\n  this.cdr.detectChanges(); // N synchronous renders!\n});',
                            code_after='items.forEach(item => this.updateItem(item));\nthis.cdr.markForCheck(); // Batched single cycle',
                            file=rel,
                            line_number=idx,
                            code_snippet=line.strip(),
                            category='Render Cycle',
                            severity=Severity.CRITICAL,
                            layer=Layer.FRONTEND,
                            impact=8,
                            effort=2,
                            occurrences=1,
                            perf_gain='Eliminates N redundant render cycles'
                        ))
                        break

    def _check_subscriptions(self, src: str, lines: List[str], rel: str):
        # ANG004: Observable subscription leak
        has_take_until = 'takeUntil(' in src or 'takeUntilDestroyed(' in src or 'take(1)' in src or 'first()' in src
        if not has_take_until and '@Component' in src:
            for idx, line in enumerate(lines, 1):
                if '.subscribe(' in line and not self._is_suppressed(lines, idx - 1, 'ANG004'):
                    self.issues.append(Issue(
                        id='ANG004',
                        title='Observable Subscription Memory Leak (Missing Teardown)',
                        description='Subscription created without takeUntilDestroyed, take(1), or unsubscribe. Retains component instance and view DOM tree in memory after route navigation.',
                        fix='Use Angular 16+ `takeUntilDestroyed(this.destroyRef)` or use the `| async` template pipe.',
                        code_before='ngOnInit() {\n  this.service.data$.subscribe(d => this.data = d);\n}',
                        code_after='private destroyRef = inject(DestroyRef);\n\nngOnInit() {\n  this.service.data$.pipe(\n    takeUntilDestroyed(this.destroyRef)\n  ).subscribe(d => this.data = d);\n}',
                        file=rel,
                        line_number=idx,
                        code_snippet=line.strip(),
                        category='Memory Leak',
                        doc_url='https://angular.dev/guide/signals/rxjs-interop',
                        severity=Severity.CRITICAL,
                        layer=Layer.FRONTEND,
                        impact=9,
                        effort=3,
                        occurrences=src.count('.subscribe('),
                        perf_gain='Prevents progressive memory growth across route transitions'
                    ))
                    break

        # ANG005: Nested subscribe callback hell
        for idx, line in enumerate(lines, 1):
            if '.subscribe(' in line:
                chunk = '\n'.join(lines[idx:min(len(lines), idx + 8)])
                if '.subscribe(' in chunk:
                    if not self._is_suppressed(lines, idx - 1, 'ANG005'):
                        self.issues.append(Issue(
                            id='ANG005',
                            title='Nested subscribe() Callback Anti-pattern',
                            description='Subscribing inside a subscribe handler causes race conditions, unhandled rejections, and disables automatic request cancellation.',
                            fix='Flatten using RxJS higher-order mapping operators like `switchMap` or `concatMap`.',
                            code_before='this.route.params.subscribe(p => {\n  this.api.getUser(p.id).subscribe(u => this.user = u);\n});',
                            code_after='this.route.params.pipe(\n  switchMap(p => this.api.getUser(p.id))\n).subscribe(u => this.user = u);',
                            file=rel,
                            line_number=idx,
                            code_snippet=line.strip(),
                            category='Concurrency & Flow',
                            severity=Severity.HIGH,
                            layer=Layer.FRONTEND,
                            impact=7,
                            effort=3,
                            occurrences=1,
                            perf_gain='Eliminates race conditions and redundant network requests'
                        ))
                        break

    def _check_http(self, src: str, lines: List[str], rel: str):
        # ANG006: Unpaginated list fetch
        has_get = 'http.get(' in src.lower() or 'this.http.get' in src.lower()
        has_pagination = any(p in src.lower() for p in ['page', 'limit', 'offset', 'pagesize', 'skip', 'take'])
        if has_get and not has_pagination and any(k in src.lower() for k in ['items', 'orders', 'users', 'list', 'all', 'records']):
            line_no, snippet = self._find_line(lines, re.compile(r'http\.get', re.IGNORECASE))
            if not self._is_suppressed(lines, line_no - 1, 'ANG006'):
                self.issues.append(Issue(
                    id='ANG006',
                    title='Unpaginated HTTP Collection Request (Full Dataset Fetch)',
                    description='HTTP GET fetches entire data collections without pagination parameters. As tables grow, payload size balloons from KB to tens of MBs, blocking client CPU.',
                    fix='Add query parameters for page and limit; paginate on both server and client.',
                    code_before='this.http.get<Order[]>("/api/orders").subscribe(data => this.orders = data);',
                    code_after='this.http.get<Paged<Order>>("/api/orders", {\n  params: { page: this.page, limit: 25 }\n}).subscribe(res => this.orders = res.items);',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Network & Bundle',
                    severity=Severity.CRITICAL,
                    layer=Layer.FRONTEND,
                    impact=10,
                    effort=4,
                    occurrences=1,
                    perf_gain='Reduces payload by 80%+ and cuts Time-to-Interactive'
                ))

        # ANG007: No debounce on user input
        if ('valueChanges' in src or 'fromEvent' in src) and 'debounceTime' not in src:
            line_no, snippet = self._find_line(lines, 'valueChanges')
            if line_no == 1:
                line_no, snippet = self._find_line(lines, 'fromEvent')
            if not self._is_suppressed(lines, line_no - 1, 'ANG007'):
                self.issues.append(Issue(
                    id='ANG007',
                    title='Missing debounceTime on Reactive Form / Input Stream',
                    description='Form `valueChanges` triggers downstream API requests or expensive filter calculations on every single keystroke.',
                    fix='Add `debounceTime(300)` and `distinctUntilChanged()` into the pipe operator.',
                    code_before='this.searchControl.valueChanges.pipe(\n  switchMap(q => this.api.search(q))\n).subscribe();',
                    code_after='this.searchControl.valueChanges.pipe(\n  debounceTime(300),\n  distinctUntilChanged(),\n  switchMap(q => this.api.search(q))\n).subscribe();',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Network Optimization',
                    severity=Severity.HIGH,
                    layer=Layer.FRONTEND,
                    impact=7,
                    effort=1,
                    occurrences=1,
                    perf_gain='Cuts redundant network requests by up to 85%'
                ))

    def _check_template(self, src: str, lines: List[str], rel: str):
        # ANG009: *ngFor without trackBy or @for without track
        ngfor_matches = len(re.findall(r'\*ngFor', src))
        trackby_matches = len(re.findall(r'trackBy', src))
        for_without_track = re.findall(r'@for\s*\([^;)]+\)', src) # missing track

        if ngfor_matches > trackby_matches:
            line_no, snippet = self._find_line(lines, '*ngFor')
            if not self._is_suppressed(lines, line_no - 1, 'ANG009'):
                self.issues.append(Issue(
                    id='ANG009',
                    title=f'*ngFor Loop Missing trackBy Identifier ({ngfor_matches - trackby_matches} un-tracked)',
                    description='Without trackBy, Angular destroys and recreates all DOM nodes in the list when data refreshes, causing UI stutter and input focus loss.',
                    fix='Use modern Angular `@for (item of items; track item.id)` or add `trackBy: trackById`.',
                    code_before='<div *ngFor="let item of items">{{ item.name }}</div>',
                    code_after='@for (item of items; track item.id) {\n  <div>{{ item.name }}</div>\n}',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='DOM Performance',
                    doc_url='https://angular.dev/guide/templates/control-flow#for-loop',
                    severity=Severity.CRITICAL,
                    layer=Layer.FRONTEND,
                    impact=8,
                    effort=1,
                    occurrences=ngfor_matches - trackby_matches,
                    perf_gain='Reduces DOM node re-creations by up to 99%'
                ))

        # ANG011: Method calls in template interpolation
        method_calls = re.findall(r'{{\s*([a-zA-Z0-9_]+)\(', src)
        if len(method_calls) >= 2:
            line_no, snippet = self._find_line(lines, re.compile(r'{{\s*[a-zA-Z0-9_]+\('))
            if not self._is_suppressed(lines, line_no - 1, 'ANG011'):
                self.issues.append(Issue(
                    id='ANG011',
                    title=f'Method Calls in Template Interpolation ({len(method_calls)} detected)',
                    description='Invoking methods in template bindings evaluates the method on every single change detection tick (hundreds of times per second during interactions).',
                    fix='Replace method calls with pure Pipes or pre-computed signal/component properties.',
                    code_before='<div>{{ formatPrice(item.price) }}</div> <!-- Runs every cycle -->',
                    code_after='<div>{{ item.price | currency }}</div> <!-- Cached pure pipe -->',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='DOM Re-renders',
                    severity=Severity.HIGH,
                    layer=Layer.FRONTEND,
                    impact=7,
                    effort=2,
                    occurrences=len(method_calls),
                    perf_gain='Eliminates repeated execution of heavy template methods'
                ))

        # ANG014: Missing @defer for heavy components
        if '<app-' in src and '@defer' not in src and len(re.findall(r'<app-[\w-]+', src)) >= 3:
            line_no, snippet = self._find_line(lines, re.compile(r'<app-[\w-]+'))
            if not self._is_suppressed(lines, line_no - 1, 'ANG014'):
                self.issues.append(Issue(
                    id='ANG014',
                    title='Heavy Subcomponents Rendered Without @defer (Lazy Viewport)',
                    description='Non-critical below-the-fold components are loaded synchronously in the initial bundle. Angular 17+ deferrable views delay JS download until visible.',
                    fix='Wrap heavy below-the-fold components in `@defer (on viewport) { ... }`.',
                    code_before='<app-heavy-chart [data]="chartData" />',
                    code_after='@defer (on viewport) {\n  <app-heavy-chart [data]="chartData" />\n} @placeholder {\n  <div class="chart-skeleton">Loading chart...</div>\n}',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Network & Bundle',
                    doc_url='https://angular.dev/guide/templates/defer',
                    severity=Severity.MEDIUM,
                    layer=Layer.FRONTEND,
                    impact=7,
                    effort=2,
                    occurrences=1,
                    perf_gain='Reduces initial JS chunk size and speeds up Largest Contentful Paint (LCP)'
                ))

    def _check_imports(self, src: str, lines: List[str], rel: str):
        # ANG012: Full library wildcard imports
        if 'import * as _' in src or "from 'lodash'" in src or "from 'rxjs/Rx'" in src:
            line_no, snippet = self._find_line(lines, re.compile(r"(?:from 'lodash'|import \* as _|from 'rxjs/Rx')"))
            if not self._is_suppressed(lines, line_no - 1, 'ANG012'):
                self.issues.append(Issue(
                    id='ANG012',
                    title='Unoptimized Full Library Import (Bundle Bloat)',
                    description='Importing entire libraries like `lodash` or legacy RxJS bundles disables tree-shaking and adds 70KB+ unnecessary JS to client downloads.',
                    fix='Import individual functions: `import debounce from "lodash/debounce";` or use native JS.',
                    code_before='import _ from "lodash";\n_.cloneDeep(data);',
                    code_after='import cloneDeep from "lodash/cloneDeep";\ncloneDeep(data); // Or structuredClone(data)',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Bundle Optimization',
                    severity=Severity.MEDIUM,
                    layer=Layer.FRONTEND,
                    impact=6,
                    effort=2,
                    occurrences=1,
                    perf_gain='Saves 50KB-80KB in production bundle size'
                ))

    def _check_routing(self, src: str, lines: List[str], rel: str):
        # ANG013: Eager routing without lazy loading
        eager_routes = re.findall(r'component:\s*\w+Component', src)
        lazy_routes = re.findall(r'loadChildren|loadComponent', src)
        if len(eager_routes) >= 3 and len(lazy_routes) == 0:
            line_no, snippet = self._find_line(lines, 'component:')
            if not self._is_suppressed(lines, line_no - 1, 'ANG013'):
                self.issues.append(Issue(
                    id='ANG013',
                    title=f'All {len(eager_routes)} Routes Loaded Eagerly at Startup',
                    description='All application feature modules load on initial page visit. Users download, parse, and compile code for routes they may never navigate to.',
                    fix='Convert route definitions to use `loadComponent` or `loadChildren` with dynamic `import()`.',
                    code_before='{ path: "admin", component: AdminComponent }',
                    code_after='{ path: "admin", loadComponent: () => import("./admin/admin.component").then(m => m.AdminComponent) }',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Bundle Optimization',
                    severity=Severity.HIGH,
                    layer=Layer.FRONTEND,
                    impact=8,
                    effort=3,
                    occurrences=len(eager_routes),
                    perf_gain='Cuts initial bundle by 40-60% via automatic code splitting'
                ))
