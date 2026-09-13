import os
import re
from pathlib import Path
from typing import List, Tuple
from core.issue import Issue, Severity, Layer

class ReactAnalyzer:
    def __init__(self, path: str):
        self.path = Path(path)
        self.issues: List[Issue] = []

    def analyze(self) -> List[Issue]:
        extensions = ['*.jsx', '*.tsx', '*.js', '*.ts']
        for ext in extensions:
            for f in self.path.rglob(ext):
                if any(x in str(f) for x in ['node_modules', '.spec.', '.test.', 'dist/', 'build/', '.git', '.d.ts']):
                    continue
                try:
                    src = f.read_text(encoding='utf-8', errors='ignore')
                    # Only analyze files that look like React components or hooks
                    if not self._is_react_file(src):
                        continue
                    rel = str(f.relative_to(self.path)).replace('\\', '/')
                    lines = src.splitlines()

                    self._check_keys_in_map(src, lines, rel)
                    self._check_inline_objects_and_handlers(src, lines, rel)
                    self._check_use_effect(src, lines, rel)
                    self._check_memo_and_callbacks(src, lines, rel)
                    self._check_lazy_loading(src, lines, rel)
                    self._check_context_bloat(src, lines, rel)
                except Exception:
                    pass

        return self.issues

    def _is_react_file(self, src: str) -> bool:
        return any(k in src for k in ['import React', 'from "react"', "from 'react'", 'useState', 'useEffect', '<div', '</', 'className='])

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

    def _check_keys_in_map(self, src: str, lines: List[str], rel: str):
        # REACT001: Array index as key in .map() or missing key
        map_index_as_key = re.search(r'\.map\(\s*\((?:\w+,\s*(\w+))\)\s*=>\s*<[A-Za-z0-9_]+\s+[^>]*key=\{(\1)\}', src)
        if map_index_as_key:
            line_no, snippet = self._find_line(lines, re.compile(r'key=\{' + map_index_as_key.group(1) + r'\}'))
            if not self._is_suppressed(lines, line_no - 1, 'REACT001'):
                self.issues.append(Issue(
                    id='REACT001',
                    title='Array Index Used as React Key in List Rendering',
                    description='Using array index (`key={index}`) breaks React DOM reconciliation when items are reordered, inserted, or filtered. React re-renders and re-mounts DOM nodes instead of reusing them, degrading 60 FPS performance and breaking form input state.',
                    fix='Use stable unique IDs for keys: `key={item.id}`.',
                    code_before='items.map((item, index) => (\n  <ListItem key={index} data={item} />\n));',
                    code_after='items.map(item => (\n  <ListItem key={item.id} data={item} />\n));',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='DOM Reconciliation',
                    doc_url='https://react.dev/learn/rendering-lists#why-does-react-need-keys',
                    severity=Severity.HIGH,
                    layer=Layer.FRONTEND,
                    impact=8,
                    effort=1,
                    occurrences=1,
                    perf_gain='Enables React to reuse DOM nodes during list mutations'
                ))

    def _check_inline_objects_and_handlers(self, src: str, lines: List[str], rel: str):
        # REACT002: Inline arrow functions or object literals inside heavy JSX list renders
        inline_handlers = re.findall(r'<\w+[^>]+(?:onClick|onChange)=\{\s*\([^)]*\)\s*=>', src)
        if len(inline_handlers) >= 3 and '.map(' in src:
            line_no, snippet = self._find_line(lines, re.compile(r'(?:onClick|onChange)=\{\s*\([^)]*\)\s*=>'))
            if not self._is_suppressed(lines, line_no - 1, 'REACT002'):
                self.issues.append(Issue(
                    id='REACT002',
                    title=f'Inline Arrow Functions in JSX Render Loop ({len(inline_handlers)} instances)',
                    description='Passing inline arrow functions or new object literals to JSX props in loops allocates a new function instance on every render tick. This defeats `React.memo` child optimizations.',
                    fix='Extract handlers with `useCallback` or pass item identifier to a shared handler.',
                    code_before='<button onClick={() => handleDelete(item.id)}>Delete</button>',
                    code_after='const handleDelete = useCallback((id) => deleteItem(id), []);\n// In component:\n<DeleteItemButton id={item.id} onDelete={handleDelete} />',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Re-render Optimization',
                    doc_url='https://react.dev/reference/react/useCallback',
                    severity=Severity.MEDIUM,
                    layer=Layer.FRONTEND,
                    impact=7,
                    effort=2,
                    occurrences=len(inline_handlers),
                    perf_gain='Prevents cascading re-renders of memoized child components'
                ))

    def _check_use_effect(self, src: str, lines: List[str], rel: str):
        # REACT003: useEffect with missing dependency array (infinite render loop)
        no_dep_effects = re.findall(r'useEffect\(\s*(?:async\s*)?\(\)\s*=>\s*\{[^}]+(?:\n\s*[^}]+)*\}\s*\)', src)
        if no_dep_effects:
            line_no, snippet = self._find_line(lines, 'useEffect(')
            if not self._is_suppressed(lines, line_no - 1, 'REACT003'):
                self.issues.append(Issue(
                    id='REACT003',
                    title='useEffect Missing Dependency Array (Executes on Every Render)',
                    description='useEffect called without a second dependency array `[]` executes after EVERY single component render. If it modifies state, it triggers an infinite re-render loop that locks the browser UI.',
                    fix='Add appropriate dependency array `[prop, state]` or `[]` for mount-only execution.',
                    code_before='useEffect(() => {\n  fetchData();\n}); // Fires on every render tick!',
                    code_after='useEffect(() => {\n  fetchData();\n}, [query]); // Only executes when query changes',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Lifecycle & Loops',
                    doc_url='https://react.dev/reference/react/useEffect#specifying-reactive-dependencies',
                    severity=Severity.CRITICAL,
                    layer=Layer.FRONTEND,
                    impact=10,
                    effort=1,
                    occurrences=len(no_dep_effects),
                    perf_gain='Eliminates continuous re-rendering loops and browser freezing'
                ))

    def _check_memo_and_callbacks(self, src: str, lines: List[str], rel: str):
        # REACT004: Heavy computational loops without useMemo
        if ('filter(' in src or 'sort(' in src or 'reduce(' in src) and ('useMemo' not in src and 'useState' in src):
            if any(k in src for k in ['items', 'records', 'data', 'products', 'table']):
                line_no, snippet = self._find_line(lines, re.compile(r'\.(?:filter|sort|reduce)\('))
                if line_no > 1 and not self._is_suppressed(lines, line_no - 1, 'REACT004'):
                    self.issues.append(Issue(
                        id='REACT004',
                        title='Expensive Array Calculation Unmemoized (Missing useMemo)',
                        description='Filtering, sorting, or reducing large arrays in the component render body recalculates on EVERY unrelated parent re-render or keystroke.',
                        fix='Wrap the expensive calculation in `useMemo(() => compute(), [data])`.',
                        code_before='const filtered = items.filter(i => i.active).sort((a,b) => b.val - a.val);',
                        code_after='const filtered = useMemo(() => {\n  return items.filter(i => i.active).sort((a,b) => b.val - a.val);\n}, [items]);',
                        file=rel,
                        line_number=line_no,
                        code_snippet=snippet,
                        category='Render Performance',
                        doc_url='https://react.dev/reference/react/useMemo',
                        severity=Severity.HIGH,
                        layer=Layer.FRONTEND,
                        impact=7,
                        effort=2,
                        occurrences=1,
                        perf_gain='Avoids re-filtering and sorting thousands of items on unrelated state updates'
                    ))

    def _check_lazy_loading(self, src: str, lines: List[str], rel: str):
        # REACT005: React Router routes without React.lazy()
        if ('react-router' in src or 'react-router-dom' in src or '<Route' in src) and 'React.lazy' not in src and 'lazy(' not in src:
            route_count = len(re.findall(r'<Route\s+', src))
            if route_count >= 3:
                line_no, snippet = self._find_line(lines, '<Route')
                if not self._is_suppressed(lines, line_no - 1, 'REACT005'):
                    self.issues.append(Issue(
                        id='REACT005',
                        title=f'All {route_count} Routes Eagerly Bundled (Missing React.lazy)',
                        description='All route components are statically imported in the root router. The client downloads code for all screens at initial load, increasing TTI by 40-70%.',
                        fix='Use `const Dashboard = React.lazy(() => import("./Dashboard"));` wrapped in `<Suspense>`.',
                        code_before='import Dashboard from "./Dashboard";\n<Route path="/dash" element={<Dashboard />} />',
                        code_after='const Dashboard = React.lazy(() => import("./Dashboard"));\n<Suspense fallback={<Spinner />}>\n  <Route path="/dash" element={<Dashboard />} />\n</Suspense>',
                        file=rel,
                        line_number=line_no,
                        code_snippet=snippet,
                        category='Bundle Size & Code Splitting',
                        doc_url='https://react.dev/reference/react/lazy',
                        severity=Severity.HIGH,
                        layer=Layer.FRONTEND,
                        impact=8,
                        effort=3,
                        occurrences=route_count,
                        perf_gain='Reduces initial JS bundle size by 40-60%'
                    ))

    def _check_context_bloat(self, src: str, lines: List[str], rel: str):
        # REACT006: Context value passing new object literal without useMemo
        context_provider = re.search(r'<\w+Context\.Provider\s+value=\{\{([^}]+)\}\}', src)
        if context_provider:
            line_no, snippet = self._find_line(lines, re.compile(r'<\w+Context\.Provider'))
            if not self._is_suppressed(lines, line_no - 1, 'REACT006'):
                self.issues.append(Issue(
                    id='REACT006',
                    title='React Context Value Recreated on Every Render (Missing useMemo)',
                    description='Passing `value={{ state, actions }}` creates a new object reference on every render, causing ALL consuming components in the entire subtree to re-render regardless of whether the actual values changed.',
                    fix='Wrap the context value in `useMemo(() => ({ state, actions }), [state])`.',
                    code_before='<AppContext.Provider value={{ user, settings }}>',
                    code_after='const value = useMemo(() => ({ user, settings }), [user, settings]);\n<AppContext.Provider value={value}>',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Context & State Performance',
                    doc_url='https://react.dev/reference/react/useContext#optimizing-re-renders-when-passing-objects-and-functions',
                    severity=Severity.HIGH,
                    layer=Layer.FRONTEND,
                    impact=8,
                    effort=2,
                    occurrences=1,
                    perf_gain='Stops accidental re-renders across the entire context subscriber tree'
                ))
