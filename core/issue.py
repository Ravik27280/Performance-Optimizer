from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class Severity(Enum):
    CRITICAL = 'critical'
    HIGH     = 'high'
    MEDIUM   = 'medium'
    LOW      = 'low'

class Layer(Enum):
    FRONTEND    = 'frontend'
    BACKEND     = 'backend'
    DATABASE    = 'database'
    INFRA       = 'infra'

@dataclass
class Issue:
    id: str
    title: str
    description: str
    fix: str
    code_before: str
    code_after: str
    file: str
    severity: Severity
    layer: Layer
    impact: int        # 1-10
    effort: int        # 1-10
    occurrences: int
    perf_gain: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    category: str = 'Performance'
    doc_url: Optional[str] = None

    @property
    def priority_score(self) -> float:
        """Higher = fix first. Impact/Effort ratio."""
        return round(self.impact / max(self.effort, 1), 2)

    @property
    def severity_order(self) -> int:
        order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
        return order.get(self.severity, 3)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'fix': self.fix,
            'code_before': self.code_before,
            'code_after': self.code_after,
            'file': self.file,
            'line_number': self.line_number,
            'code_snippet': self.code_snippet,
            'category': self.category,
            'doc_url': self.doc_url,
            'severity': self.severity.value,
            'layer': self.layer.value,
            'impact': self.impact,
            'effort': self.effort,
            'occurrences': self.occurrences,
            'perf_gain': self.perf_gain,
            'priority_score': self.priority_score,
        }
