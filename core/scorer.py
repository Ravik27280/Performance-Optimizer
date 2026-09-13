import math
from typing import List, Dict, Any
from core.issue import Issue, Severity, Layer

class Scorer:
    def compute(self, issues: List[Issue]) -> Dict[str, Any]:
        severity_weights = {
            Severity.CRITICAL: 22,
            Severity.HIGH: 12,
            Severity.MEDIUM: 5,
            Severity.LOW: 2
        }

        def compute_layer_score(layer: Layer) -> int:
            sub = [i for i in issues if i.layer == layer]
            if not sub:
                return 100
            # Diminishing returns penalty calculation
            raw_penalty = sum(severity_weights.get(i.severity, 2) * min(max(i.occurrences, 1), 5) for i in sub)
            # Smooth asymptotic curve: 100 / (1 + (penalty / 38)^1.15)
            damped_score = 100.0 / (1.0 + (raw_penalty / 38.0) ** 1.15)
            return max(5, min(100, round(damped_score)))

        frontend_score = compute_layer_score(Layer.FRONTEND)
        backend_score  = compute_layer_score(Layer.BACKEND)
        db_score       = compute_layer_score(Layer.DATABASE)
        infra_score    = compute_layer_score(Layer.INFRA)

        overall = round(
            frontend_score * 0.40 +
            backend_score  * 0.30 +
            db_score       * 0.20 +
            infra_score    * 0.10
        )

        by_sev = {s.value: 0 for s in Severity}
        by_layer = {l.value: 0 for l in Layer}
        for i in issues:
            by_sev[i.severity.value] += 1
            by_layer[i.layer.value]  += 1

        # File breakdown
        file_issues: Dict[str, List[Issue]] = {}
        for i in issues:
            file_issues.setdefault(i.file, []).append(i)

        worst_files = sorted(file_issues.items(), key=lambda x: (
            -sum(severity_weights.get(ii.severity, 2) for ii in x[1])
        ))[:10]

        file_scores = []
        for fp, fi in worst_files:
            file_raw = sum(severity_weights.get(ii.severity, 2) for ii in fi)
            f_score = max(5, min(100, round(100.0 / (1.0 + (file_raw / 28.0) ** 1.15))))
            file_scores.append({
                'file': fp,
                'issues': len(fi),
                'score': f_score,
                'critical': sum(1 for ii in fi if ii.severity == Severity.CRITICAL),
                'high': sum(1 for ii in fi if ii.severity == Severity.HIGH),
                'medium': sum(1 for ii in fi if ii.severity == Severity.MEDIUM),
                'low': sum(1 for ii in fi if ii.severity == Severity.LOW)
            })

        # Top issues sorted by priority_score (Impact/Effort) and severity
        sorted_issues = sorted(issues, key=lambda i: (i.severity_order, -i.priority_score))
        top3 = sorted_issues[:3]

        # Projected impact calculations
        has_dom_issues = any(i.id in ['ANG001', 'ANG003', 'ANG009', 'ANG010'] for i in issues)
        has_db_loop = any(i.id in ['NODE004', 'SQL004', 'SQL003', 'NODE005'] for i in issues)
        mem_leak_count = sum(1 for i in issues if i.id in ['ANG004', 'NODE009', 'NODE011'])
        bundle_reduction = sum(45 if i.id == 'ANG013' else 25 if i.id == 'ANG012' else 0 for i in issues)

        metrics = {
            'dom_render_waste_pct': 65 if has_dom_issues else 0,
            'db_query_reduction_pct': 85 if has_db_loop else 0,
            'memory_leak_count': mem_leak_count,
            'bundle_reduction_kb': bundle_reduction,
        }

        return {
            'overall': overall,
            'frontend': frontend_score,
            'backend':  backend_score,
            'database': db_score,
            'infra':    infra_score,
            'by_severity': by_sev,
            'by_layer': by_layer,
            'total_issues': len(issues),
            'top3': [i.to_dict() for i in top3],
            'worst_files': file_scores,
            'metrics': metrics,
        }
