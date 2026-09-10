from typing import List
from core.issue import Issue, Severity, Layer

class Scorer:
    def compute(self, issues: List[Issue]) -> dict:
        def layer_score(layer: Layer) -> int:
            sub = [i for i in issues if i.layer == layer]
            if not sub: return 100
            penalty = sum(
                {Severity.CRITICAL: 18, Severity.HIGH: 9, Severity.MEDIUM: 4, Severity.LOW: 1}[i.severity]
                for i in sub
            )
            return max(0, min(100, 100 - penalty))

        frontend_score = layer_score(Layer.FRONTEND)
        backend_score  = layer_score(Layer.BACKEND)
        db_score       = layer_score(Layer.DATABASE)
        infra_score    = layer_score(Layer.INFRA)
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
        file_issues: dict = {}
        for i in issues:
            file_issues.setdefault(i.file, []).append(i)
        worst_files = sorted(file_issues.items(), key=lambda x: (
            -sum(3 if ii.severity==Severity.CRITICAL else 2 if ii.severity==Severity.HIGH else 1 for ii in x[1])
        ))[:10]
        file_scores = []
        for fp, fi in worst_files:
            penalty = sum(18 if ii.severity==Severity.CRITICAL else 9 if ii.severity==Severity.HIGH else 4 for ii in fi)
            score = max(0, min(100, 100 - penalty))
            file_scores.append({'file': fp, 'issues': len(fi), 'score': score,
                                'critical': sum(1 for ii in fi if ii.severity==Severity.CRITICAL),
                                'high': sum(1 for ii in fi if ii.severity==Severity.HIGH)})

        # Top issues for exec summary (highest impact, lowest effort)
        top3 = sorted(issues, key=lambda i: (-i.impact, i.effort))[:3]

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
        }
