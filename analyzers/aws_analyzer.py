import re, json
from pathlib import Path
from core.issue import Issue, Severity, Layer

class AwsAnalyzer:
    def __init__(self, path):
        self.path = Path(path)
        self.issues = []

    def analyze(self):
        for f in list(self.path.rglob('*.json')) + list(self.path.rglob('*.yml')) + list(self.path.rglob('*.yaml')):
            if 'node_modules' in str(f): continue
            try:
                src = f.read_text(errors='ignore')
                rel = str(f.relative_to(self.path))
                self._check_aws_config(src, rel)
            except: pass
        return self.issues

    def _check_aws_config(self, src, rel):
        sl = src.lower()
        # Lambda memory too low
        mem_matches = re.findall(r'memorysize["\s:]+([0-9]+)', sl)
        for m in mem_matches:
            if int(m) < 512:
                self.issues.append(Issue(
                    id='AWS001', title=f'Lambda Memory Too Low ({m}MB)',
                    description=f'Lambda configured with only {m}MB memory. Lambda CPU allocation scales linearly with memory. Low memory = slow CPU = slower execution = higher cost (duration x memory). 128MB Lambda can be 4x slower than 512MB for the same code.',
                    fix='Increase Lambda memory to 512MB-1024MB. Use Lambda Power Tuning tool to find optimal setting.',
                    code_before=f'MemorySize: {m}  # Slow CPU allocation',
                    code_after='MemorySize: 512  # 4x more CPU, often same or lower cost due to faster execution',
                    file=rel, severity=Severity.MEDIUM, layer=Layer.INFRA,
                    impact=6, effort=1, occurrences=len(mem_matches),
                    perf_gain='Can reduce Lambda duration by 50-75%, may reduce cost too'
                ))
                break
        # No CloudFront / CDN
        has_s3_website = 's3' in sl and ('website' in sl or 'static' in sl or 'hosting' in sl)
        has_cloudfront = 'cloudfront' in sl or 'distribution' in sl
        if has_s3_website and not has_cloudfront:
            self.issues.append(Issue(
                id='AWS002', title='Static Assets Served Without CDN (CloudFront)',
                description='Frontend assets appear to be served directly from S3 without CloudFront. Every user request hits S3 in one region. Users far from that region experience high latency.',
                fix='Add CloudFront distribution in front of S3. Enable gzip compression, set cache-control headers. Use S3 Transfer Acceleration if needed.',
                code_before='# Static files served from S3 bucket directly\n# ap-southeast-1 users OK, eu-west users: 300ms+ latency',
                code_after='# CloudFront CDN: 400+ edge locations worldwide\n# Same user in EU: 20-30ms latency from nearest edge',
                file=rel, severity=Severity.HIGH, layer=Layer.INFRA,
                impact=8, effort=4, occurrences=1,
                perf_gain='Reduces static asset latency from 200-500ms to 10-30ms globally'
            ))
        # No timeout on Lambda
        if 'timeout' not in sl and 'lambda' in sl:
            self.issues.append(Issue(
                id='AWS003', title='Lambda Functions Without Explicit Timeout',
                description='Lambda functions without explicit timeout default to 3 seconds. If a downstream service (RDS, external API) hangs, Lambda retries and accumulates cost. Set explicit timeouts per function purpose.',
                fix='Set Timeout explicitly per function. API handlers: 10-15s. Background jobs: 60-300s.',
                code_before='# No Timeout set\n# Defaults to 3s - may timeout before RDS query completes',
                code_after='Timeout: 15  # seconds\n# Match to expected operation duration + buffer',
                file=rel, severity=Severity.MEDIUM, layer=Layer.INFRA,
                impact=5, effort=1, occurrences=1,
                perf_gain='Prevents unexpected timeouts and reduces retry-related cost spikes'
            ))
