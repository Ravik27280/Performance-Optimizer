import os
import re
from pathlib import Path
from typing import List, Tuple
from core.issue import Issue, Severity, Layer

class AwsAnalyzer:
    def __init__(self, path: str):
        self.path = Path(path)
        self.issues: List[Issue] = []

    def analyze(self) -> List[Issue]:
        target_extensions = ['*.json', '*.yml', '*.yaml', '*.tf']
        for ext in target_extensions:
            for f in self.path.rglob(ext):
                if any(x in str(f) for x in ['node_modules', 'dist/', '.git', 'package-lock.json']):
                    continue
                try:
                    src = f.read_text(encoding='utf-8', errors='ignore')
                    rel = str(f.relative_to(self.path)).replace('\\', '/')
                    lines = src.splitlines()
                    self._check_aws_config(src, lines, rel)
                except Exception:
                    pass
        return self.issues

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
            if isinstance(regex_or_str, str) and regex_or_str.lower() in line.lower():
                return idx, line.strip()
            elif hasattr(regex_or_str, 'search') and regex_or_str.search(line):
                return idx, line.strip()
        return 1, (lines[0].strip() if lines else '')

    def _check_aws_config(self, src: str, lines: List[str], rel: str):
        sl = src.lower()

        # AWS001: Lambda memory too low (<512MB)
        mem_match = re.search(r'memorysize["\s:]+([0-9]+)', sl)
        if mem_match:
            val = int(mem_match.group(1))
            if val < 512:
                line_no, snippet = self._find_line(lines, re.compile(r'memorysize', re.IGNORECASE))
                if not self._is_suppressed(lines, line_no - 1, 'AWS001'):
                    self.issues.append(Issue(
                        id='AWS001',
                        title=f'Lambda Memory Allocated Too Low ({val} MB)',
                        description=f'Lambda configured with only {val} MB memory. AWS CPU allocation scales proportionally with memory. Functions with <512MB memory suffer from throttled CPU, running 3-4x slower.',
                        fix='Increase MemorySize to 512 MB - 1024 MB. Faster completion often results in equal or lower net AWS cost.',
                        code_before=f'MemorySize: {val} # Under-allocated CPU',
                        code_after='MemorySize: 512 # Full vCPU core access; up to 65% faster completion',
                        file=rel,
                        line_number=line_no,
                        code_snippet=snippet,
                        category='Serverless Latency',
                        doc_url='https://docs.aws.amazon.com/lambda/latest/dg/configuration-function-common.html#configuration-memory-console',
                        severity=Severity.HIGH,
                        layer=Layer.INFRA,
                        impact=7,
                        effort=1,
                        occurrences=1,
                        perf_gain='Cuts function runtime duration by up to 60%'
                    ))

        # AWS002: Static assets served without CloudFront CDN
        has_s3 = 's3' in sl and any(w in sl for w in ['website', 'static', 'hosting', 'bucket'])
        has_cdn = 'cloudfront' in sl or 'distribution' in sl
        if has_s3 and not has_cdn:
            line_no, snippet = self._find_line(lines, 's3')
            if not self._is_suppressed(lines, line_no - 1, 'AWS002'):
                self.issues.append(Issue(
                    id='AWS002',
                    title='Static S3 Hosting Without CloudFront Edge CDN',
                    description='Frontend static assets are served directly from an S3 bucket in a single region. Distant global users experience 200-500ms latency on every asset download.',
                    fix='Deploy an Amazon CloudFront distribution in front of S3 with gzip/brotli compression enabled.',
                    code_before='# Assets served from single S3 bucket region\n# Global users: 300ms+ roundtrip',
                    code_after='# CloudFront CDN distribution with edge caching\n# Global users: 15-30ms from local edge',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Edge & CDN',
                    severity=Severity.HIGH,
                    layer=Layer.INFRA,
                    impact=8,
                    effort=3,
                    occurrences=1,
                    perf_gain='Reduces static asset latency from ~350ms to 20ms globally'
                ))

        # AWS005: Lambda directly connecting to RDS without RDS Proxy
        if ('lambda' in sl or 'serverless' in sl) and ('rds' in sl or 'postgres' in sl or 'mysql' in sl) and 'proxy' not in sl:
            line_no, snippet = self._find_line(lines, re.compile(r'(?:rds|postgres|mysql)', re.IGNORECASE))
            if not self._is_suppressed(lines, line_no - 1, 'AWS005'):
                self.issues.append(Issue(
                    id='AWS005',
                    title='Serverless Lambda Connecting to RDS Without RDS Proxy',
                    description='Lambda functions executing concurrent requests spawn hundreds of unpooled database connections, quickly exhausting RDS connection limits and leading to connection refusal errors.',
                    fix='Place an Amazon RDS Proxy between Lambda and RDS to pool and multiplex database connections.',
                    code_before='DB_HOST: "my-rds-cluster.rds.amazonaws.com" # Direct unpooled connection',
                    code_after='DB_HOST: "my-proxy.proxy-xxx.rds.amazonaws.com" # Multiplexed pool via RDS Proxy',
                    file=rel,
                    line_number=line_no,
                    code_snippet=snippet,
                    category='Connection Pooling',
                    severity=Severity.HIGH,
                    layer=Layer.INFRA,
                    impact=9,
                    effort=4,
                    occurrences=1,
                    perf_gain='Prevents database connection exhaustion during traffic bursts'
                ))
