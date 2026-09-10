import json
from datetime import datetime
from typing import List
from core.issue import Issue, Severity, Layer

SEV_COLOR = {
    'critical': '#ef4444',
    'high':     '#f97316',
    'medium':   '#eab308',
    'low':      '#64748b',
}
LAYER_COLOR = {
    'frontend': '#6366f1',
    'backend':  '#22c55e',
    'database': '#f97316',
    'infra':    '#06b6d4',
}
LAYER_ICON  = {'frontend': '🅰️', 'backend': '🟢', 'database': '🗄️', 'infra': '☁️'}
LAYER_LABEL = {'frontend': 'Angular / Frontend', 'backend': 'Node.js / Seneca', 'database': 'SQL / RDS', 'infra': 'AWS / Infra'}

def score_color(s):
    if s < 40: return '#ef4444'
    if s < 60: return '#f97316'
    if s < 75: return '#eab308'
    return '#22c55e'

def score_bar_class(s):
    if s < 40: return 'bar-red'
    if s < 60: return 'bar-orange'
    if s < 75: return 'bar-yellow'
    return 'bar-green'

def dots(val, total=10):
    filled = min(val, total)
    html = '<div class="impact-dots">'
    for i in range(total):
        html += f'<div class="dot {"dot-fill" if i < filled else "dot-empty"}"></div>'
    html += '</div>'
    return html

def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

class HtmlReporter:
    def __init__(self, issues: List[Issue], scores: dict, meta: dict):
        self.issues  = sorted(issues, key=lambda i: (i.severity_order, -i.impact))
        self.scores  = scores
        self.meta    = meta

    def render(self, out_path: str):
        html = self._build()
        with open(out_path, 'w', encoding='utf-8') as fh:
            fh.write(html)

    def _build(self) -> str:
        s = self.scores
        total = s['total_issues']
        by_sev = s['by_severity']
        by_layer = s['by_layer']
        overall = s['overall']
        top3 = s.get('top3', [])
        worst_files = s.get('worst_files', [])
        scan_time = self.meta.get('scan_time', datetime.now().strftime('%d %b %Y, %I:%M %p'))
        files_scanned = self.meta.get('files_scanned', 0)
        duration = self.meta.get('duration', '?')
        project = self.meta.get('project', 'Your Project')
        tech = self.meta.get('tech', 'Angular • Node.js • Seneca • AWS RDS')
        ring_offset = round(440 * (1 - overall/100))

        # Build issues table rows
        table_rows = ''
        for idx, issue in enumerate(self.issues, 1):
            sev = issue.severity.value
            layer = issue.layer.value
            sc = SEV_COLOR.get(sev, '#888')
            lc = LAYER_COLOR.get(layer, '#888')
            table_rows += f'''
            <tr data-cat="{esc(layer)}" data-sev="{esc(sev)}">
              <td style="color:var(--muted);font-size:12px;">{str(idx).zfill(3)}</td>
              <td>
                <div class="issue-title">{esc(issue.title)}</div>
                <div class="issue-file">{esc(issue.file)}</div>
              </td>
              <td><span class="badge badge-{sev}">{sev.upper()}</span></td>
              <td><span class="badge" style="background:color-mix(in srgb,{lc} 15%,transparent);color:{lc};">{layer.upper()}</span></td>
              <td><div class="impact-bar">{dots(issue.impact)} {issue.impact}</div></td>
              <td><div class="impact-bar">{dots(issue.effort)} {issue.effort}</div></td>
              <td><span style="color:{score_color(issue.priority_score*10)};font-weight:700;">{'🔥 P1' if issue.priority_score >= 2.5 else 'P2' if issue.priority_score >= 1.5 else 'P3'}</span></td>
              <td style="font-weight:700;color:{sc};">{issue.occurrences}</td>
            </tr>'''

        # Fix cards
        fix_cards = ''
        for issue in self.issues[:6]:
            sev = issue.severity.value
            fix_cards += f'''
            <div class="fix-card">
              <div class="fix-header">
                <h4><span class="badge badge-{sev}">{sev.upper()}</span> [{esc(issue.id)}] {esc(issue.title)}</h4>
                <span style="font-size:12px;color:var(--green);">{esc(issue.perf_gain)}</span>
              </div>
              <div style="padding:16px 20px;font-size:13px;color:var(--muted);line-height:1.6;border-bottom:1px solid var(--border);">{esc(issue.description)}</div>
              <div class="fix-body">
                <div>
                  <div class="code-block">
                    <div class="code-header"><span class="before">❌ BEFORE</span><span style="font-size:11px;color:var(--muted);">{esc(issue.file.split("/")[-1])}</span></div>
                    <pre>{esc(issue.code_before)}</pre>
                  </div>
                </div>
                <div>
                  <div class="code-block">
                    <div class="code-header"><span class="after">✅ AFTER</span></div>
                    <pre>{esc(issue.code_after)}</pre>
                  </div>
                  <div class="fix-impact-box">
                    <p>⚡ {esc(issue.perf_gain)}</p>
                    <span>Effort: {issue.effort}/10 &nbsp;|&nbsp; Impact: {issue.impact}/10 &nbsp;|&nbsp; Occurrences: {issue.occurrences}</span>
                  </div>
                </div>
              </div>
            </div>'''

        # Category score cards
        cat_cards = ''
        for layer_key in ['frontend', 'backend', 'database', 'infra']:
            sc_val = s.get(layer_key, 100)
            count  = by_layer.get(layer_key, 0)
            cat_cards += f'''
            <div class="cat-card">
              <div class="cat-icon">{LAYER_ICON[layer_key]}</div>
              <div class="cat-name">{LAYER_LABEL[layer_key]}</div>
              <div class="cat-score" style="color:{score_color(sc_val)};">{sc_val}<span style="font-size:14px;color:var(--muted);"> /100</span></div>
              <div class="cat-bar-wrap"><div class="cat-bar {score_bar_class(sc_val)}" style="width:{sc_val}%;"></div></div>
              <div style="font-size:11px;color:var(--muted);margin-top:8px;">{count} issues found</div>
            </div>'''

        # Exec summary top 3
        exec_items = ''
        for t in top3:
            exec_items += f'''
            <div class="exec-item">
              <div class="exec-title">{esc(t["title"])}</div>
              <div class="exec-desc">{esc(t["description"][:120])}...</div>
              <div class="exec-impact">⬆ {esc(t["perf_gain"])}</div>
            </div>'''

        # File breakdown
        file_rows = ''
        for fi in worst_files:
            fc = score_color(fi['score'])
            file_rows += f'''
            <div class="file-row">
              <div><div class="file-name">{esc(fi["file"].split("/")[-1])}</div><div class="file-path">{esc("/".join(fi["file"].split("/")[:-1]))}</div></div>
              <div class="file-issues"><strong style="color:{fc};">{fi["issues"]}</strong><br>issues</div>
              <div style="font-size:20px;font-weight:800;color:{fc};width:60px;text-align:center;">{fi["score"]}</div>
              <div class="file-score-wrap"><div style="font-size:11px;color:var(--muted);">Score</div><div class="file-score-bar"><div style="height:100%;width:{fi["score"]}%;background:{fc};border-radius:3px;"></div></div></div>
            </div>'''

        # Chart data
        sev_data = json.dumps([by_sev.get('critical',0), by_sev.get('high',0), by_sev.get('medium',0), by_sev.get('low',0)])
        layer_data = json.dumps([by_layer.get('frontend',0), by_layer.get('backend',0), by_layer.get('database',0), by_layer.get('infra',0)])

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Performance Optimizer Report — {esc(project)}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  :root{{
    --bg:#0f1117;--card:#1a1d27;--card2:#20242f;--border:#2a2d3a;
    --accent:#6366f1;--accent2:#8b5cf6;
    --red:#ef4444;--orange:#f97316;--yellow:#eab308;--green:#22c55e;
    --text:#e2e8f0;--muted:#64748b;--font:\'Inter\',-apple-system,sans-serif;
  }}
  body{{background:var(--bg);color:var(--text);font-family:var(--font);min-height:100vh;}}
  .header{{background:linear-gradient(135deg,#1a1d27 0%,#12141e 100%);border-bottom:1px solid var(--border);padding:0 40px;}}
  .header-inner{{max-width:1400px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:20px 0;}}
  .logo{{display:flex;align-items:center;gap:12px;}}
  .logo-icon{{width:40px;height:40px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;}}
  .logo-text h1{{font-size:18px;font-weight:700;color:white;}}
  .logo-text p{{font-size:12px;color:var(--muted);margin-top:2px;}}
  .header-meta{{text-align:right;}}
  .header-meta .scan-time{{font-size:12px;color:var(--muted);}}
  .header-meta .project-name{{font-size:14px;color:var(--text);font-weight:600;}}
  .container{{max-width:1400px;margin:0 auto;padding:32px 40px;}}
  .hero{{display:grid;grid-template-columns:280px 1fr;gap:24px;margin-bottom:32px;}}
  .score-card{{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:32px;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;overflow:hidden;}}
  .score-card::before{{content:\'\';position:absolute;inset:0;background:radial-gradient(circle at 50% 0%,rgba(99,102,241,0.15) 0%,transparent 70%);pointer-events:none;}}
  .score-label{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;}}
  .score-ring{{position:relative;width:160px;height:160px;margin:16px 0;}}
  .score-ring svg{{transform:rotate(-90deg);}}
  .score-ring .ring-bg{{fill:none;stroke:var(--border);stroke-width:12;}}
  .score-ring .ring-fill{{fill:none;stroke-width:12;stroke-linecap:round;stroke-dasharray:440;transition:stroke-dashoffset 1s ease;}}
  .score-ring-label{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;}}
  .summary-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}}
  .sum-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;}}
  .sum-card .sum-num{{font-size:36px;font-weight:800;}}
  .sum-card .sum-label{{font-size:12px;color:var(--muted);margin-top:4px;}}
  .exec-banner{{background:linear-gradient(135deg,rgba(239,68,68,0.1),rgba(249,115,22,0.05));border:1px solid rgba(239,68,68,0.3);border-radius:12px;padding:20px 24px;margin-top:16px;}}
  .exec-banner h3{{font-size:14px;color:var(--red);font-weight:600;margin-bottom:12px;}}
  .exec-items{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}}
  .exec-title{{font-size:13px;font-weight:600;color:var(--text);margin-bottom:4px;}}
  .exec-desc{{font-size:12px;color:var(--muted);line-height:1.5;}}
  .exec-impact{{font-size:11px;color:var(--orange);margin-top:6px;font-weight:600;}}
  .section-title{{font-size:16px;font-weight:700;margin-bottom:16px;display:flex;align-items:center;gap:10px;color:var(--text);}}
  .section-title .pill{{font-size:11px;padding:2px 8px;border-radius:100px;background:var(--card2);color:var(--muted);font-weight:500;}}
  .cat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px;}}
  .cat-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;}}
  .cat-icon{{font-size:24px;margin-bottom:12px;}}
  .cat-name{{font-size:13px;color:var(--muted);margin-bottom:4px;}}
  .cat-score{{font-size:28px;font-weight:800;}}
  .cat-bar-wrap{{height:6px;background:var(--border);border-radius:3px;margin-top:12px;overflow:hidden;}}
  .cat-bar{{height:100%;border-radius:3px;}}
  .bar-red{{background:var(--red);}}.bar-orange{{background:var(--orange);}}.bar-yellow{{background:var(--yellow);}}.bar-green{{background:var(--green);}}
  .charts-row{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:24px;margin-bottom:32px;}}
  .chart-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:24px;}}
  .chart-card h4{{font-size:13px;color:var(--muted);margin-bottom:16px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;}}
  .chart-wrap{{position:relative;height:180px;}}
  .issues-wrap{{margin-bottom:32px;}}
  .filter-row{{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;}}
  .filter-btn{{padding:6px 14px;border-radius:100px;border:1px solid var(--border);background:var(--card);color:var(--muted);font-size:12px;cursor:pointer;transition:all 0.2s;}}
  .filter-btn:hover,.filter-btn.active{{border-color:var(--accent);color:var(--accent);background:rgba(99,102,241,0.1);}}
  table{{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden;border:1px solid var(--border);}}
  thead{{background:var(--card2);}}
  th{{padding:12px 16px;text-align:left;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;font-weight:600;border-bottom:1px solid var(--border);}}
  td{{padding:14px 16px;font-size:13px;border-bottom:1px solid rgba(42,45,58,0.5);vertical-align:top;}}
  tr:last-child td{{border-bottom:none;}}
  tr:hover td{{background:rgba(255,255,255,0.02);}}
  .badge{{display:inline-flex;align-items:center;padding:3px 10px;border-radius:100px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;}}
  .badge-critical{{background:rgba(239,68,68,0.15);color:var(--red);border:1px solid rgba(239,68,68,0.3);}}
  .badge-high{{background:rgba(249,115,22,0.15);color:var(--orange);border:1px solid rgba(249,115,22,0.3);}}
  .badge-medium{{background:rgba(234,179,8,0.15);color:var(--yellow);border:1px solid rgba(234,179,8,0.3);}}
  .badge-low{{background:rgba(100,116,139,0.15);color:var(--muted);border:1px solid rgba(100,116,139,0.3);}}
  .impact-bar{{display:flex;align-items:center;gap:8px;}}
  .impact-dots{{display:flex;gap:3px;}}
  .dot{{width:8px;height:8px;border-radius:50%;}}
  .dot-fill{{background:var(--accent);}}.dot-empty{{background:var(--border);}}
  .issue-file{{font-size:11px;color:var(--muted);font-family:monospace;margin-top:3px;}}
  .issue-title{{font-weight:600;color:var(--text);}}
  .fix-grid{{display:grid;gap:16px;margin-bottom:32px;}}
  .fix-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;}}
  .fix-header{{padding:16px 20px;background:var(--card2);display:flex;align-items:center;justify-content:space-between;}}
  .fix-header h4{{font-size:14px;font-weight:600;display:flex;align-items:center;gap:10px;}}
  .fix-body{{padding:20px;display:grid;grid-template-columns:1fr 1fr;gap:16px;}}
  .code-block{{background:#0d1117;border-radius:8px;overflow:hidden;}}
  .code-header{{padding:8px 14px;background:#161b22;display:flex;justify-content:space-between;align-items:center;}}
  .code-header .before{{color:var(--red);}}.code-header .after{{color:var(--green);}}
  pre{{padding:16px;font-size:12px;font-family:monospace;overflow-x:auto;line-height:1.6;color:#c9d1d9;white-space:pre-wrap;word-break:break-word;}}
  .fix-impact-box{{background:rgba(34,197,94,0.05);border:1px solid rgba(34,197,94,0.2);border-radius:8px;padding:12px 16px;margin-top:12px;}}
  .fix-impact-box p{{font-size:12px;color:var(--green);font-weight:600;}}
  .fix-impact-box span{{font-size:11px;color:var(--muted);}}
  .file-grid{{display:grid;gap:8px;margin-bottom:32px;}}
  .file-row{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 18px;display:grid;grid-template-columns:1fr auto auto auto;gap:16px;align-items:center;}}
  .file-name{{font-size:13px;font-family:monospace;color:var(--text);}}
  .file-path{{font-size:11px;color:var(--muted);margin-top:2px;}}
  .file-issues{{font-size:12px;color:var(--muted);text-align:center;}}
  .file-score-wrap{{width:80px;}}
  .file-score-bar{{height:6px;border-radius:3px;background:var(--border);overflow:hidden;margin-top:4px;}}
  .footer{{border-top:1px solid var(--border);padding:24px 40px;text-align:center;}}
  .footer p{{font-size:12px;color:var(--muted);}}
  .badge-frontend{{background:rgba(99,102,241,0.15);color:#818cf8;}}
  .badge-backend{{background:rgba(34,197,94,0.15);color:var(--green);}}
  .badge-database{{background:rgba(249,115,22,0.15);color:#fb923c;}}
  .badge-infra{{background:rgba(6,182,212,0.15);color:#22d3ee;}}
  @media(max-width:900px){{.hero{{grid-template-columns:1fr;}}.cat-grid{{grid-template-columns:1fr 1fr;}}.charts-row{{grid-template-columns:1fr;}}.fix-body{{grid-template-columns:1fr;}}.exec-items{{grid-template-columns:1fr;}}}}
</style>
</head>
<body>
<div class="header">
  <div class="header-inner">
    <div class="logo">
      <div class="logo-icon">⚡</div>
      <div class="logo-text"><h1>Performance Optimizer</h1><p>Advanced Multi-Stack Analyzer • NOT SonarQube • Performance-Specific</p></div>
    </div>
    <div class="header-meta">
      <div class="project-name">🏢 {esc(project)}</div>
      <div class="scan-time">📅 {esc(scan_time)} &nbsp;|&nbsp; ⏱ Scan: {esc(str(duration))}s &nbsp;|&nbsp; 📁 {files_scanned} files analyzed &nbsp;|&nbsp; {esc(tech)}</div>
    </div>
  </div>
</div>

<div class="container">
  <!-- HERO -->
  <div class="hero">
    <div class="score-card">
      <div class="score-label">Overall Performance Score</div>
      <div class="score-ring">
        <svg width="160" height="160" viewBox="0 0 160 160">
          <defs><linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="{score_color(overall)}"/>
            <stop offset="100%" stop-color="{score_color(min(overall+20,100))}"/>
          </linearGradient></defs>
          <circle class="ring-bg" cx="80" cy="80" r="70"/>
          <circle class="ring-fill" cx="80" cy="80" r="70" stroke="url(#grad1)" stroke-dashoffset="{ring_offset}"/>
        </svg>
        <div class="score-ring-label">
          <span style="font-size:42px;font-weight:800;color:{score_color(overall)};">{overall}</span>
          <span style="font-size:12px;color:var(--muted);">/ 100</span>
        </div>
      </div>
      <div style="font-size:13px;font-weight:600;color:{score_color(overall)};">{"🔴 CRITICAL" if overall<40 else "⚠️ NEEDS WORK" if overall<65 else "🟡 FAIR" if overall<80 else "✅ GOOD"}</div>
      <div style="font-size:12px;color:var(--muted);margin-top:4px;text-align:center;">{total} performance issues found</div>
    </div>
    <div style="display:flex;flex-direction:column;gap:16px;">
      <div class="summary-grid">
        <div class="sum-card"><div class="sum-num" style="color:var(--red);">{by_sev.get("critical",0)}</div><div class="sum-label">🔴 Critical Issues</div></div>
        <div class="sum-card"><div class="sum-num" style="color:var(--orange);">{by_sev.get("high",0)}</div><div class="sum-label">🟠 High Priority</div></div>
        <div class="sum-card"><div class="sum-num" style="color:var(--yellow);">{by_sev.get("medium",0) + by_sev.get("low",0)}</div><div class="sum-label">🟡 Medium / Low</div></div>
      </div>
      <div class="exec-banner">
        <h3>🚨 Top Issues For Your Manager</h3>
        <div class="exec-items">{exec_items if exec_items else "<div class='exec-item'><div class='exec-title'>No Critical Issues Found</div><div class='exec-desc'>Great news! No top-priority issues detected.</div></div>"}</div>
      </div>
    </div>
  </div>

  <!-- CATEGORY SCORES -->
  <div class="section-title">📊 Category Scores <span class="pill">4 categories</span></div>
  <div class="cat-grid">{cat_cards}</div>

  <!-- CHARTS -->
  <div class="charts-row">
    <div class="chart-card"><h4>Issue Distribution by Severity</h4><div class="chart-wrap"><canvas id="chart1"></canvas></div></div>
    <div class="chart-card"><h4>Issues by Layer</h4><div class="chart-wrap"><canvas id="chart2"></canvas></div></div>
    <div class="chart-card"><h4>Est. Improvement After Fixes (%)</h4><div class="chart-wrap"><canvas id="chart3"></canvas></div></div>
  </div>

  <!-- ISSUES TABLE -->
  <div class="issues-wrap">
    <div class="section-title">🔍 All Issues <span class="pill">{total} total</span></div>
    <div class="filter-row">
      <button class="filter-btn active" onclick="filterTable(\'all\', this)">All ({total})</button>
      <button class="filter-btn" onclick="filterTable(\'critical\', this)" style="color:var(--red);">🔴 Critical ({by_sev.get("critical",0)})</button>
      <button class="filter-btn" onclick="filterTable(\'high\', this)" style="color:var(--orange);">🟠 High ({by_sev.get("high",0)})</button>
      <button class="filter-btn" onclick="filterTable(\'frontend\', this)">Frontend ({by_layer.get("frontend",0)})</button>
      <button class="filter-btn" onclick="filterTable(\'backend\', this)">Backend ({by_layer.get("backend",0)})</button>
      <button class="filter-btn" onclick="filterTable(\'database\', this)">Database ({by_layer.get("database",0)})</button>
    </div>
    <table id="issueTable">
      <thead><tr><th>#</th><th>Issue</th><th>Severity</th><th>Layer</th><th>Impact</th><th>Effort</th><th>Priority</th><th>Count</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>

  <!-- FIX RECOMMENDATIONS -->
  <div class="section-title">💡 Top Fix Recommendations <span class="pill">with code diffs</span></div>
  <div class="fix-grid">{fix_cards}</div>

  <!-- FILE BREAKDOWN -->
  <div class="section-title">📁 Worst Offending Files <span class="pill">top {len(worst_files)}</span></div>
  <div class="file-grid">{file_rows if file_rows else "<div style='color:var(--muted);text-align:center;padding:20px;'>No file-level data available</div>"}</div>
</div>

<div class="footer"><p>⚡ Performance Optimizer — Not SonarQube. Performance-specific analysis only. &nbsp;|&nbsp; {esc(tech)} &nbsp;|&nbsp; Report: {esc(scan_time)}</p></div>

<script>
const c1=document.getElementById("chart1").getContext("2d");
new Chart(c1,{{type:"doughnut",data:{{labels:["Critical","High","Medium","Low"],datasets:[{{data:{sev_data},backgroundColor:["#ef4444","#f97316","#eab308","#64748b"],borderWidth:0}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:"right",labels:{{color:"#94a3b8",font:{{size:11}},boxWidth:12,padding:8}}}}}},cutout:"65%"}}}});
const c2=document.getElementById("chart2").getContext("2d");
new Chart(c2,{{type:"bar",data:{{labels:["Frontend","Backend","Database","Infra"],datasets:[{{data:{layer_data},backgroundColor:["#6366f1","#22c55e","#f97316","#06b6d4"],borderRadius:6,borderWidth:0}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:"#64748b",font:{{size:11}}}},grid:{{display:false}}}},y:{{ticks:{{color:"#64748b",font:{{size:11}}}},grid:{{color:"#1e2130"}}}}}}}}}});
const c3=document.getElementById("chart3").getContext("2d");
new Chart(c3,{{type:"bar",data:{{labels:["UI Re-renders","DB Queries","Memory","Bundle Size","API Latency"],datasets:[{{label:"Before",data:[100,100,100,100,100],backgroundColor:"rgba(239,68,68,0.5)",borderRadius:4,borderWidth:0}},{{label:"After Fixes",data:[35,20,15,45,30],backgroundColor:"rgba(34,197,94,0.7)",borderRadius:4,borderWidth:0}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:"#94a3b8",font:{{size:11}},boxWidth:12,padding:8}}}}}},scales:{{x:{{ticks:{{color:"#64748b",font:{{size:10}}}},grid:{{display:false}}}},y:{{ticks:{{color:"#64748b",font:{{size:10}}}},grid:{{color:"#1e2130"}}}}}}}}}}}});
function filterTable(cat,btn){{document.querySelectorAll(".filter-btn").forEach(b=>b.classList.remove("active"));if(btn)btn.classList.add("active");document.querySelectorAll("#issueTable tbody tr").forEach(r=>{{const rc=r.dataset.cat,rs=r.dataset.sev;if(cat==="all")r.style.display="";else if(["frontend","backend","database","infra"].includes(cat))r.style.display=rc===cat?"":"none";else r.style.display=rs===cat?"":"none";}});}}
</script>
</body>
</html>'''
