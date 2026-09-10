import os, re, json
from pathlib import Path
from core.issue import Issue, Severity, Layer

class AngularAnalyzer:
    def __init__(self, path):
        self.path = Path(path)
        self.issues = []

    def analyze(self):
        for f in self.path.rglob('*.ts'):
            if any(x in str(f) for x in ['node_modules', '.spec.', 'dist/', '.d.ts']): continue
            try:
                src = f.read_text(errors='ignore')
                if '@Component' in src: self._check_component(src, f)
                if 'subscribe(' in src: self._check_subscriptions(src, f)
                if 'HttpClient' in src or 'http.get' in src.lower(): self._check_http(src, f)
                self._check_imports(src, f)
            except: pass
        for f in self.path.rglob('*.html'):
            if any(x in str(f) for x in ['node_modules', 'dist/']): continue
            try:
                src = f.read_text(errors='ignore')
                self._check_template(src, f)
            except: pass
        for f in self.path.rglob('*-routing.module.ts'):
            if 'node_modules' in str(f): continue
            try:
                src = f.read_text(errors='ignore')
                self._check_routing(src, f)
            except: pass
        return self.issues

    def _check_component(self, src, f):
        rel = str(f.relative_to(self.path))
        # OnPush check
        if '@Component' in src and 'ChangeDetectionStrategy.OnPush' not in src:
            self.issues.append(Issue(
                id='ANG001', title='Missing OnPush Change Detection',
                description='Component uses Default change detection. Angular re-renders the ENTIRE component tree on every browser event (click, mousemove, keyup). With OnPush, re-renders only on @Input() reference change or async pipe emit.',
                fix='Add changeDetection: ChangeDetectionStrategy.OnPush to @Component decorator. Also ensure inputs are immutable (use spread/Object.assign instead of mutation).',
                code_before='@Component({ selector: \'app-x\', template: \'...\' })\nexport class XComponent {}',
                code_after='@Component({\n  selector: \'app-x\',\n  template: \'...\',\n  changeDetection: ChangeDetectionStrategy.OnPush\n})\nexport class XComponent {}',
                file=rel, severity=Severity.CRITICAL, layer=Layer.FRONTEND,
                impact=9, effort=3, occurrences=1,
                perf_gain='Up to 65% reduction in DOM re-renders for data-heavy UIs'
            ))
        # Large @Input arrays not using immutable pattern
        if 'Input()' in src and '.push(' in src:
            self.issues.append(Issue(
                id='ANG002', title='Mutable Input Mutation (Breaks OnPush)',
                description='Pushing to an @Input() array mutates the reference. OnPush will NOT detect this change, causing stale UI. Also causes unintended shared-state bugs.',
                fix='Use immutable spread: this.items = [...this.items, newItem] instead of this.items.push(newItem)',
                code_before='this.dataList.push(newItem); // OnPush won\'t detect',
                code_after='this.dataList = [...this.dataList, newItem]; // new ref = OnPush detects',
                file=rel, severity=Severity.HIGH, layer=Layer.FRONTEND,
                impact=7, effort=2, occurrences=src.count('.push('),
                perf_gain='Ensures change detection works correctly with OnPush'
            ))
        # ChangeDetectorRef.detectChanges in loops
        if 'detectChanges()' in src and ('for(' in src or 'forEach' in src or 'for (' in src):
            self.issues.append(Issue(
                id='ANG003', title='detectChanges() Called Inside Loop',
                description='Manually triggering change detection inside a loop causes N synchronous re-renders, freezing the browser UI thread.',
                fix='Batch updates, call detectChanges() once after loop completes, or use markForCheck() instead.',
                code_before='items.forEach(i => { this.process(i); this.cdr.detectChanges(); })',
                code_after='items.forEach(i => this.process(i));\nthis.cdr.detectChanges(); // once after loop',
                file=rel, severity=Severity.HIGH, layer=Layer.FRONTEND,
                impact=8, effort=2, occurrences=1,
                perf_gain='Eliminates N redundant render cycles per loop iteration'
            ))

    def _check_subscriptions(self, src, f):
        rel = str(f.relative_to(self.path))
        sub_count = src.count('.subscribe(')
        unsub_count = src.count('unsubscribe(') + src.count('takeUntil(') + src.count('async pipe') + src.count('| async')
        if sub_count > 0 and unsub_count == 0 and '@Component' in src:
            self.issues.append(Issue(
                id='ANG004', title='Observable Memory Leak – No Unsubscribe',
                description=f'Found {sub_count} subscribe() calls with no unsubscribe, takeUntil, or async pipe. Each subscription stays alive after component destroy, accumulates handlers, and can replay events on destroyed views causing ExpressionChangedAfterItHasBeenCheckedError.',
                fix='Use takeUntil(this.destroy$) pattern with ngOnDestroy, or use the async pipe in templates to auto-unsubscribe.',
                code_before='ngOnInit() {\n  this.service.data$.subscribe(d => this.data = d);\n  // Subscription leaks when component destroys\n}',
                code_after='private destroy$ = new Subject<void>();\nngOnInit() {\n  this.service.data$.pipe(takeUntil(this.destroy$))\n    .subscribe(d => this.data = d);\n}\nngOnDestroy() { this.destroy$.next(); this.destroy$.complete(); }',
                file=rel, severity=Severity.CRITICAL, layer=Layer.FRONTEND,
                impact=8, effort=4, occurrences=sub_count,
                perf_gain='Eliminates memory growth per navigation, prevents ghost event handlers'
            ))
        # Nested subscriptions
        if 'subscribe(' in src:
            lines = src.split('\n')
            for i, line in enumerate(lines):
                if '.subscribe(' in line:
                    snippet = '\n'.join(lines[i:i+8])
                    if '.subscribe(' in snippet[snippet.index('.subscribe(')+12:]:
                        self.issues.append(Issue(
                            id='ANG005', title='Nested subscribe() – Callback Hell',
                            description='subscribe() inside subscribe() creates nested async callbacks. This causes race conditions, memory leaks, and blocks parallelism.',
                            fix='Use switchMap, concatMap, or forkJoin to compose Observables instead of nesting.',
                            code_before='.subscribe(id => {\n  this.service.getDetails(id).subscribe(d => ...)\n  // Race condition: old request may resolve after new one\n})',
                            code_after='.pipe(\n  switchMap(id => this.service.getDetails(id))\n).subscribe(d => ...);',
                            file=rel, severity=Severity.HIGH, layer=Layer.FRONTEND,
                            impact=7, effort=5, occurrences=1,
                            perf_gain='Eliminates race conditions, enables request cancellation'
                        ))
                        break

    def _check_http(self, src, f):
        rel = str(f.relative_to(self.path))
        # Fetch all data without pagination
        has_get = 'http.get(' in src.lower() or '.get(' in src
        has_pagination = any(x in src.lower() for x in ['page', 'limit', 'offset', 'pagesize', 'perpage', 'skip', 'take'])
        has_search_subscribe = 'subscribe(' in src
        if has_get and not has_pagination and has_search_subscribe:
            self.issues.append(Issue(
                id='ANG006', title='API Call Without Pagination – Fetching All Data',
                description='HTTP GET call has no page/limit/offset parameters. This fetches the ENTIRE dataset from the server at once. As data grows, response time grows linearly, browser JS heap bloats, and Angular must render thousands of DOM nodes.',
                fix='Add page/limit params to API call. Use Angular CDK Virtual Scroll (CdkVirtualScrollViewport) for the list. Implement server-side pagination in the backend.',
                code_before='this.http.get<Item[]>(\'api/items\')\n  .subscribe(items => this.items = items);\n// Fetches ALL 50,000 items at once',
                code_after='this.http.get<Page<Item>>(\'api/items\', {\n  params: { page: this.page, limit: 50 }\n}).subscribe(res => {\n  this.items = res.data;\n  this.total = res.total;\n});',
                file=rel, severity=Severity.CRITICAL, layer=Layer.FRONTEND,
                impact=10, effort=5, occurrences=src.lower().count('http.get(') + src.lower().count(".get('") + src.lower().count('.get(`'),
                perf_gain='Reduces initial payload from MB to KB, cuts Time-to-Interactive by 70%+'
            ))
        # No debounce on user input
        if ('fromEvent' in src or 'valueChanges' in src) and 'debounceTime' not in src:
            self.issues.append(Issue(
                id='ANG007', title='No debounceTime on User Input Stream',
                description='Reactive form valueChanges or fromEvent fires an API call on EVERY keystroke. A user typing 10 chars fires 10 requests — most are wasted.',
                fix='Add debounceTime(300) and distinctUntilChanged() to the pipe before the switchMap.',
                code_before='this.searchControl.valueChanges\n  .pipe(switchMap(q => this.api.search(q)))\n  .subscribe(...);\n// Fires request on every keypress!',
                code_after='this.searchControl.valueChanges.pipe(\n  debounceTime(300),\n  distinctUntilChanged(),\n  switchMap(q => this.api.search(q))\n).subscribe(...);',
                file=rel, severity=Severity.HIGH, layer=Layer.FRONTEND,
                impact=7, effort=1, occurrences=1,
                perf_gain='Reduces API calls by ~85% for search/filter interactions'
            ))
        # No caching / repeated API calls
        if src.count('http.get(') > 3 or src.count(".get('") > 3:
            self.issues.append(Issue(
                id='ANG008', title='No HTTP Response Caching (shareReplay Missing)',
                description='Multiple components likely call the same endpoint repeatedly. Without caching, identical API calls are made on every component init.',
                fix='Add shareReplay(1) to shared data streams in services. Use Angular HTTP interceptor for global cache-control.',
                code_before='getData() {\n  return this.http.get(\'api/config\');\n  // Called 5x = 5 network requests\n}',
                code_after='private cache$ = this.http.get(\'api/config\')\n  .pipe(shareReplay(1)); // cached\ngetData() { return this.cache$; }',
                file=rel, severity=Severity.MEDIUM, layer=Layer.FRONTEND,
                impact=6, effort=2, occurrences=1,
                perf_gain='Eliminates redundant API calls for shared/static data'
            ))

    def _check_template(self, src, f):
        rel = str(f.relative_to(self.path))
        # ngFor without trackBy
        ngfor_matches = re.findall(r'\*ngFor', src)
        trackby_matches = re.findall(r'trackBy', src)
        if len(ngfor_matches) > len(trackby_matches):
            missing = len(ngfor_matches) - len(trackby_matches)
            self.issues.append(Issue(
                id='ANG009', title=f'*ngFor Without trackBy ({missing} occurrence(s))',
                description=f'Found {len(ngfor_matches)} *ngFor directives, only {len(trackby_matches)} use trackBy. Without trackBy, Angular destroys and re-creates ALL DOM nodes on every data change — even when only 1 item changed. With 1000 rows, this means 1000 DOM operations per update.',
                fix='Add trackBy function. For items with id: trackByFn(index, item) { return item.id; }',
                code_before='<div *ngFor="let item of items">{{item.name}}</div>\n<!-- Destroys & recreates ALL nodes on update -->',
                code_after='<div *ngFor="let item of items; trackBy: trackById">{{item.name}}</div>\n// In component: trackById = (i, item) => item.id;',
                file=rel, severity=Severity.CRITICAL, layer=Layer.FRONTEND,
                impact=8, effort=2, occurrences=missing,
                perf_gain='Reduces DOM operations by up to 99% for list updates'
            ))
        # No virtual scroll for large lists
        if '*ngFor' in src and 'cdk-virtual-scroll-viewport' not in src and 'virtual-scroll' not in src:
            self.issues.append(Issue(
                id='ANG010', title='No Virtual Scrolling for Large List',
                description='List renders ALL items to DOM at once. If the list has 500+ items, Angular renders 500 DOM nodes — most invisible. Browser must layout and paint all of them.',
                fix='Use Angular CDK CdkVirtualScrollViewport. Only renders visible items (~20), recycles DOM nodes as user scrolls.',
                code_before='<div *ngFor="let item of items">\n  <!-- Renders ALL 5000 items -->\n</div>',
                code_after='<cdk-virtual-scroll-viewport itemSize="50" style="height:500px">\n  <div *cdkVirtualFor="let item of items">\n    {{ item.name }}\n  </div>\n</cdk-virtual-scroll-viewport>',
                file=rel, severity=Severity.HIGH, layer=Layer.FRONTEND,
                impact=9, effort=4, occurrences=len(ngfor_matches),
                perf_gain='Renders only ~20 DOM nodes regardless of list size — critical for large datasets'
            ))
        # Method calls in templates (performance anti-pattern)
        method_calls = re.findall(r'{{\s*\w+\(', src)
        if len(method_calls) > 2:
            self.issues.append(Issue(
                id='ANG011', title=f'Method Calls in Template ({len(method_calls)} found)',
                description='Method calls in Angular templates are invoked on EVERY change detection cycle. A method called in a template with 100ms intervals = 600 method executions per minute. For expensive calculations this kills performance.',
                fix='Use pure Pipes instead of methods, or pre-compute values in ngOnInit/ngOnChanges and bind to a property.',
                code_before='<!-- Called on every change detection: -->\n<div>{{ formatDate(item.date) }}</div>\n<div>{{ calculateTotal(items) }}</div>',
                code_after='<!-- Use pipe (cached): -->\n<div>{{ item.date | date:\'short\' }}</div>\n<!-- Or pre-compute: -->\n<div>{{ totalAmount }}</div> // set in ngOnChanges',
                file=rel, severity=Severity.HIGH, layer=Layer.FRONTEND,
                impact=7, effort=3, occurrences=len(method_calls),
                perf_gain='Eliminates repeated expensive computations on every render cycle'
            ))

    def _check_imports(self, src, f):
        rel = str(f.relative_to(self.path))
        # Full module imports instead of specific
        if 'import * from' in src or "from 'lodash'" in src or 'import _ from' in src:
            self.issues.append(Issue(
                id='ANG012', title='Wildcard / Full Library Import (Bundle Bloat)',
                description='Importing entire lodash or using import * pulls the WHOLE library into your bundle even if you use 1 function. Lodash alone is 70KB+ minified.',
                fix='Import only the specific function: import debounce from "lodash/debounce" instead of import _ from "lodash"',
                code_before="import _ from 'lodash'; // 70KB added to bundle\n_.debounce(fn, 300);",
                code_after="import debounce from 'lodash/debounce'; // ~2KB\ndebounce(fn, 300);",
                file=rel, severity=Severity.MEDIUM, layer=Layer.FRONTEND,
                impact=5, effort=2, occurrences=1,
                perf_gain='Can reduce bundle size by 50-70KB+'
            ))

    def _check_routing(self, src, f):
        rel = str(f.relative_to(self.path))
        eager = re.findall(r'component:\s*\w+Component', src)
        lazy = re.findall(r'loadChildren|loadComponent', src)
        if len(eager) > 2 and len(lazy) == 0:
            self.issues.append(Issue(
                id='ANG013', title=f'No Lazy Loading – {len(eager)} Routes Eagerly Loaded',
                description=f'All {len(eager)} routes load their modules at app startup. User pays the full JS parse+compile cost upfront even for pages they never visit. Initial bundle includes code for ALL features.',
                fix='Use loadChildren with dynamic import for each route. Angular will code-split automatically.',
                code_before="{ path: 'dashboard', component: DashboardComponent }\n// DashboardModule loaded at startup",
                code_after="{ path: 'dashboard',\n  loadChildren: () => import('./dashboard/dashboard.module')\n    .then(m => m.DashboardModule) }\n// Loaded only when user visits /dashboard",
                file=rel, severity=Severity.HIGH, layer=Layer.FRONTEND,
                impact=8, effort=4, occurrences=len(eager),
                perf_gain=f'Can reduce initial bundle by 40-60%. Splits into {len(eager)} separate chunks'
            ))
