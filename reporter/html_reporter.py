import json
from datetime import datetime
from typing import List, Dict, Any
from core.issue import Issue, Severity, Layer

def score_color(s: int) -> str:
    if s < 45: return '#f43f5e'
    if s < 65: return '#f59e0b'
    if s < 80: return '#eab308'
    return '#10b981'

def esc(s: Any) -> str:
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

class HtmlReporter:
    def __init__(self, issues: List[Issue], scores: Dict[str, Any], meta: Dict[str, Any]):
        self.issues = sorted(issues, key=lambda i: (i.severity_order, -i.priority_score))
        self.scores = scores
        self.meta = meta

    def render(self, out_path: str):
        html = self._build()
        with open(out_path, 'w', encoding='utf-8') as fh:
            fh.write(html)

    def _build(self) -> str:
        s = self.scores
        total = s.get('total_issues', 0)
        by_sev = s.get('by_severity', {})
        by_layer = s.get('by_layer', {})
        overall = s.get('overall', 100)
        top3 = s.get('top3', [])
        worst_files = s.get('worst_files', [])
        metrics = s.get('metrics', {})

        scan_time = self.meta.get('scan_time', datetime.now().strftime('%d %b %Y, %I:%M %p'))
        files_scanned = self.meta.get('files_scanned', 0)
        duration = self.meta.get('duration', '0.01')
        project = self.meta.get('project', 'Project')
        tech = self.meta.get('tech', 'Angular • React • Node.js • SQL • AWS')

        # SVG Circle circumference: 2 * pi * 70 = ~440
        ring_offset = round(440 * (1 - overall / 100))
        s_color = score_color(overall)

        status_text = "Critical Latency Risks" if overall < 50 else "Optimization Required" if overall < 70 else "Fair Performance" if overall < 85 else "Production Ready"
        status_badge_class = "sev-critical" if overall < 50 else "sev-high" if overall < 70 else "sev-medium" if overall < 85 else "sev-ready"

        table_rows_html = []
        sim_checklist_html = []

        for idx, issue in enumerate(self.issues, 1):
            row_id = f"diag_row_{idx}"
            sev = issue.severity.value
            layer = issue.layer.value
            sc = score_color(round(issue.priority_score * 10))
            line_display = f":{issue.line_number}" if issue.line_number else ""
            clean_file = issue.file.replace('\\', '/')

            pt_weight = 18 if issue.severity == Severity.CRITICAL else 10 if issue.severity == Severity.HIGH else 4
            search_str = f"{issue.id} {issue.title} {clean_file} {issue.category} {issue.description}".lower()

            main_row = f'''
            <tr class="main-row" onclick="toggleRow('{row_id}')" data-sev="{esc(sev)}" data-layer="{esc(layer)}" data-search="{esc(search_str)}">
              <td><span class="rule-token">{esc(issue.id)}</span></td>
              <td>
                <div class="row-issue-title">{esc(issue.title)}</div>
                <div class="row-issue-file">{esc(clean_file)}{line_display}</div>
              </td>
              <td><span class="badge-tag sev-{esc(sev)}">{esc(sev.upper())}</span></td>
              <td><span class="badge-tag layer-{esc(layer)}">{esc(layer.upper())}</span></td>
              <td><span style="font-weight:700;color:{score_color(issue.impact * 10)};">{issue.impact}/10</span> <span style="font-size:11px;color:var(--text-dim);">(Effort: {issue.effort})</span></td>
              <td><span class="p-rank" style="color:{sc};">{'P1' if issue.priority_score >= 2.5 else 'P2' if issue.priority_score >= 1.5 else 'P3'}</span></td>
              <td><button class="btn btn-ghost" style="padding:3px 9px;font-size:11px;">Diff</button></td>
            </tr>
            <tr class="expanded-row" id="{row_id}">
              <td colspan="7">
                <div class="diff-wrapper">
                  <div class="diff-desc">
                    <strong>Architectural Risk:</strong> {esc(issue.description)}
                  </div>
                  <div class="diff-split">
                    <div class="diff-pane">
                      <div class="diff-pane-head bad">
                        <span class="head-tag">Offending Code</span>
                        <span class="head-file">{esc(clean_file)}{line_display}</span>
                      </div>
                      <pre class="diff-code">{esc(issue.code_before)}</pre>
                    </div>
                    <div class="diff-pane">
                      <div class="diff-pane-head good">
                        <span class="head-tag">Remediated Code</span>
                        <button class="copy-chip" onclick="copySnippet(this)">Copy Patch</button>
                      </div>
                      <pre class="diff-code">{esc(issue.code_after)}</pre>
                    </div>
                  </div>
                  <div class="diff-footer">
                    <span class="diff-gain">
                      <span class="icon" style="width:13px;height:13px;"><svg viewBox="0 0 24 24" width="13" height="13"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg></span>
                      <span>{esc(issue.perf_gain)}</span>
                    </span>
                    {f'<a href="{esc(issue.doc_url)}" target="_blank" class="diff-link">Documentation →</a>' if issue.doc_url else ''}
                  </div>
                </div>
              </td>
            </tr>'''
            table_rows_html.append(main_row)

            if idx <= 10:
                sim_item = f'''
                <label class="sim-item">
                  <input type="checkbox" onchange="recalculateSimScore()" data-points="{pt_weight}">
                  <div class="sim-body">
                    <div class="sim-title">
                      <span>[{esc(issue.id)}] {esc(issue.title)}</span>
                      <span class="badge-tag sev-{esc(sev)}">+{pt_weight} pts</span>
                    </div>
                    <div class="sim-desc">{esc(issue.perf_gain)} • {esc(clean_file)}</div>
                  </div>
                </label>'''
                sim_checklist_html.append(sim_item)

        table_rows = '\n'.join(table_rows_html) if table_rows_html else '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--text-dim);">No performance defects detected. Codebase is clean.</td></tr>'
        sim_checklist = '\n'.join(sim_checklist_html) if sim_checklist_html else '<p style="color:var(--text-dim);">No defects available for simulation.</p>'

        exec_cards = ''
        for t in top3:
            exec_cards += f'''
            <div class="exec-card">
              <span class="badge-tag sev-{esc(t["severity"])}" style="margin-bottom:8px;">{esc(t["severity"].upper())} • {esc(t["layer"].upper())}</span>
              <h5>{esc(t["title"])}</h5>
              <p>{esc(t["description"][:130])}...</p>
              <div class="gain-text">
                <span class="icon" style="width:13px;height:13px;"><svg viewBox="0 0 24 24" width="13" height="13"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg></span>
                <span>{esc(t["perf_gain"])}</span>
              </div>
            </div>'''
        if not exec_cards:
            exec_cards = '<div class="exec-card"><h5>No Critical Defects</h5><p>No critical performance defects detected in the analyzed scope.</p></div>'

        file_cards = ''
        for fi in worst_files:
            fc = score_color(fi['score'])
            clean_name = fi['file'].replace('\\', '/').split('/')[-1]
            clean_dir = '/'.join(fi['file'].replace('\\', '/').split('/')[:-1])
            file_cards += f'''
            <div class="hotspot-item">
              <div class="hotspot-info">
                <div class="hotspot-name">{esc(clean_name)}</div>
                <div class="hotspot-dir">{esc(clean_dir or '.')}</div>
                <div class="hotspot-tags">
                  {f'<span class="badge-tag sev-critical">{fi["critical"]} Critical</span>' if fi["critical"] else ''}
                  {f'<span class="badge-tag sev-high">{fi["high"]} High</span>' if fi["high"] else ''}
                  <span class="badge-tag sev-neutral">{fi["issues"]} Total</span>
                </div>
              </div>
              <div style="text-align:right;">
                <div class="hotspot-score" style="color:{fc};">{fi["score"]}<span style="font-size:12px;color:var(--text-dim);">/100</span></div>
                <span style="font-size:11px;color:var(--text-dim);font-weight:600;">File Rating</span>
              </div>
            </div>'''
        if not file_cards:
            file_cards = '<p style="color:var(--text-dim);padding:20px;">No hotspot files found.</p>'

        sev_chart_data = json.dumps([by_sev.get('critical', 0), by_sev.get('high', 0), by_sev.get('medium', 0), by_sev.get('low', 0)])
        layer_chart_data = json.dumps([by_layer.get('frontend', 0), by_layer.get('backend', 0), by_layer.get('database', 0), by_layer.get('infra', 0)])

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Performance Intelligence Report — {esc(project)}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #07090e;
    --bg-surface: #0c0f17;
    --card: #111622;
    --card-hover: #161c2b;
    --card-active: #1c2438;
    --border: rgba(255, 255, 255, 0.08);
    --border-highlight: rgba(99, 102, 241, 0.4);
    --primary: #6366f1;
    --primary-light: #818cf8;
    --primary-glow: rgba(99, 102, 241, 0.22);
    --cyan: #06b6d4;
    --emerald: #10b981;
    --emerald-bg: rgba(16, 185, 129, 0.08);
    --crimson: #f43f5e;
    --crimson-bg: rgba(244, 63, 94, 0.08);
    --amber: #f59e0b;
    --amber-bg: rgba(245, 158, 11, 0.08);
    --text: #f8fafc;
    --text-muted: #94a3b8;
    --text-dim: #64748b;
    --code-bg: #07090e;
    --font: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
    --radius: 12px;
    --radius-lg: 16px;
    --ease: cubic-bezier(0.16, 1, 0.3, 1);
  }}

  [data-theme="light"] {{
    --bg: #f8fafc;
    --bg-surface: #ffffff;
    --card: #ffffff;
    --card-hover: #f1f5f9;
    --card-active: #e2e8f0;
    --border: rgba(0, 0, 0, 0.08);
    --border-highlight: rgba(79, 70, 229, 0.4);
    --primary: #4f46e5;
    --primary-light: #6366f1;
    --primary-glow: rgba(79, 70, 229, 0.12);
    --cyan: #0891b2;
    --emerald: #059669;
    --emerald-bg: rgba(5, 150, 105, 0.08);
    --crimson: #e11d48;
    --crimson-bg: rgba(225, 29, 72, 0.08);
    --amber: #d97706;
    --amber-bg: rgba(217, 119, 6, 0.08);
    --text: #0f172a;
    --text-muted: #475569;
    --text-dim: #64748b;
    --code-bg: #0f172a;
  }}

  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    line-height: 1.6;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
    transition: background 0.35s var(--ease), color 0.35s var(--ease);
  }}

  /* GLOBAL SVG SAFETY RESET */
  svg {{
    max-width: 100%;
    max-height: 100%;
    box-sizing: border-box;
    display: block;
  }}

  .icon {{
    width: 16px;
    height: 16px;
    min-width: 16px;
    min-height: 16px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    line-height: 1;
    overflow: hidden;
  }}
  .icon svg {{
    width: 16px;
    height: 16px;
    max-width: 16px;
    max-height: 16px;
    stroke: currentColor;
    fill: none;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
    flex-shrink: 0;
  }}

  .header {{
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(20px);
  }}
  .header-inner {{
    max-width: 1400px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 32px;
  }}
  .brand-group {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .brand-glyph {{
    width: 38px;
    height: 38px;
    min-width: 38px;
    min-height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    box-shadow: 0 0 20px var(--primary-glow);
    overflow: hidden;
    flex-shrink: 0;
  }}
  .brand-glyph svg {{
    width: 20px !important;
    height: 20px !important;
    max-width: 20px !important;
    max-height: 20px !important;
    stroke: currentColor;
    fill: none;
    stroke-width: 2;
  }}
  .brand-text h1 {{
    font-size: 17px;
    font-weight: 800;
    letter-spacing: -0.4px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .brand-text p {{
    font-size: 12px;
    color: var(--text-muted);
  }}
  .header-actions {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .btn {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--card);
    color: var(--text);
    transition: all 0.2s var(--ease);
    text-decoration: none;
  }}
  .btn:hover {{
    background: var(--card-hover);
    border-color: rgba(255,255,255,0.18);
  }}
  .btn-primary {{
    background: linear-gradient(135deg, #4f46e5, #6366f1);
    border-color: var(--primary);
    color: white;
    box-shadow: 0 4px 16px var(--primary-glow);
  }}
  .btn-primary:hover {{
    background: linear-gradient(135deg, #4338ca, #4f46e5);
  }}

  .nav-tabs {{
    display: flex;
    gap: 6px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-surface);
    padding: 0 32px;
    max-width: 1400px;
    margin: 0 auto;
  }}
  .tab-btn {{
    padding: 14px 20px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    font-size: 13.5px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s var(--ease);
  }}
  .tab-btn:hover {{ color: var(--text); }}
  .tab-btn.active {{
    color: var(--primary-light);
    border-bottom-color: var(--primary);
  }}
  .tab-count {{
    background: var(--card-hover);
    font-size: 11px;
    padding: 1px 7px;
    border-radius: 10px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }}

  .container {{
    max-width: 1400px;
    margin: 0 auto;
    padding: 32px 32px 64px 32px;
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; }}

  /* HERO SCORE SECTION */
  .hero-grid {{
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: 24px;
    margin-bottom: 32px;
  }}
  .score-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 30px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }}
  .score-card::before {{
    content: '';
    position: absolute;
    top: -60px;
    width: 220px;
    height: 220px;
    background: radial-gradient(circle, var(--primary-glow) 0%, transparent 70%);
    pointer-events: none;
  }}
  .score-ring-wrap {{
    position: relative;
    width: 170px;
    height: 170px;
    margin: 16px 0;
  }}
  .score-ring-wrap svg {{ transform: rotate(-90deg); }}
  .score-ring-bg {{
    fill: none;
    stroke: var(--border);
    stroke-width: 12;
  }}
  .score-ring-progress {{
    fill: none;
    stroke-width: 12;
    stroke-linecap: round;
    stroke-dasharray: 440;
    transition: stroke-dashoffset 1.2s var(--ease), stroke 0.5s;
  }}
  .score-ring-val {{
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }}
  .score-ring-num {{
    font-size: 50px;
    font-weight: 800;
    letter-spacing: -1.5px;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }}
  .score-status-badge {{
    padding: 4px 12px;
    border-radius: 100px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-top: 8px;
  }}

  /* METRICS ROW */
  .metrics-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;
  }}
  .metric-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
  }}
  .metric-icon-box {{
    width: 34px;
    height: 34px;
    border-radius: 8px;
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 12px;
    color: var(--primary-light);
  }}
  .metric-title {{
    font-size: 12.5px;
    color: var(--text-muted);
    font-weight: 500;
  }}
  .metric-val {{
    font-size: 26px;
    font-weight: 800;
    margin: 4px 0;
    letter-spacing: -0.5px;
  }}
  .metric-sub {{
    font-size: 11.5px;
    font-weight: 600;
    color: var(--emerald);
  }}

  .exec-banner {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 22px 26px;
  }}
  .exec-banner-title {{
    font-size: 13.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--primary-light);
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }}
  .exec-cards-row {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }}
  .exec-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
  }}
  .exec-card h5 {{
    font-size: 13.5px;
    font-weight: 700;
    margin-bottom: 4px;
  }}
  .exec-card p {{
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.5;
  }}
  .gain-text {{
    margin-top: 10px;
    font-size: 11.5px;
    color: var(--emerald);
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 5px;
  }}

  .section-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 32px 0 18px 0;
  }}
  .section-header h3 {{
    font-size: 17px;
    font-weight: 800;
    letter-spacing: -0.4px;
  }}

  .layer-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 18px;
    margin-bottom: 28px;
  }}
  .layer-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px;
    transition: transform 0.2s var(--ease), border-color 0.2s var(--ease);
  }}
  .layer-card:hover {{
    transform: translateY(-2px);
    border-color: var(--border-highlight);
  }}
  .layer-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }}
  .layer-title {{
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-muted);
  }}
  .layer-score {{
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.6px;
    font-variant-numeric: tabular-nums;
  }}
  .track-bar {{
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
    margin: 12px 0;
  }}
  .fill-bar {{
    height: 100%;
    border-radius: 3px;
    transition: width 0.8s var(--ease);
  }}

  .charts-row {{
    display: grid;
    grid-template-columns: 1fr 1fr 1.2fr;
    gap: 20px;
    margin-bottom: 36px;
  }}
  .chart-box {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 22px;
  }}
  .chart-box h4 {{
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-dim);
    margin-bottom: 16px;
  }}
  .chart-canvas-wrap {{
    position: relative;
    height: 190px;
  }}

  /* FILTER BAR */
  .filter-bar {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }}
  .search-wrap {{
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg);
    border: 1px solid var(--border);
    padding: 8px 14px;
    border-radius: 8px;
    flex: 1;
    min-width: 240px;
  }}
  .search-wrap input {{
    background: transparent;
    border: none;
    outline: none;
    color: var(--text);
    font-size: 13px;
    width: 100%;
    font-family: var(--font);
  }}
  .pill-group {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }}
  .pill-btn {{
    padding: 6px 12px;
    border-radius: 7px;
    font-size: 12px;
    font-weight: 600;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
  }}
  .pill-btn:hover, .pill-btn.active {{
    background: var(--card-active);
    border-color: var(--border-highlight);
    color: var(--text);
  }}

  /* ISSUES TABLE */
  .table-shell {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    margin-bottom: 36px;
  }}
  table.diag-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
  }}
  table.diag-table thead {{
    background: var(--bg-surface);
  }}
  table.diag-table th {{
    padding: 14px 20px;
    text-align: left;
    font-size: 11.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
  }}
  table.diag-table td {{
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
  }}
  table.diag-table tr.main-row {{
    cursor: pointer;
    transition: background 0.15s;
  }}
  table.diag-table tr.main-row:hover {{
    background: var(--card-hover);
  }}
  table.diag-table tr.expanded-row {{
    display: none;
    background: var(--bg-surface);
  }}
  table.diag-table tr.expanded-row.show {{
    display: table-row;
  }}

  .rule-token {{
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 700;
    color: var(--primary-light);
  }}
  .row-issue-title {{
    font-weight: 700;
    color: var(--text);
  }}
  .row-issue-file {{
    font-size: 11.5px;
    color: var(--text-dim);
    font-family: var(--font-mono);
    margin-top: 2px;
  }}

  .badge-tag {{
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    border-radius: 5px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }}
  .sev-critical {{ background: var(--crimson-bg); color: var(--crimson); border: 1px solid rgba(244,63,94,0.3); }}
  .sev-high {{ background: var(--amber-bg); color: var(--amber); border: 1px solid rgba(245,158,11,0.3); }}
  .sev-medium {{ background: rgba(99,102,241,0.1); color: var(--primary-light); border: 1px solid rgba(99,102,241,0.25); }}
  .sev-ready {{ background: var(--emerald-bg); color: var(--emerald); border: 1px solid rgba(16,185,129,0.3); }}
  .sev-neutral {{ background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid var(--border); }}

  .layer-frontend {{ background: rgba(99,102,241,0.1); color: #818cf8; border: 1px solid rgba(99,102,241,0.3); }}
  .layer-backend {{ background: rgba(16,185,129,0.1); color: #34d399; border: 1px solid rgba(16,185,129,0.3); }}
  .layer-database {{ background: rgba(245,158,11,0.1); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); }}
  .layer-infra {{ background: rgba(6,182,212,0.1); color: #22d3ee; border: 1px solid rgba(6,182,212,0.3); }}

  .diff-wrapper {{ padding: 22px; }}
  .diff-desc {{
    font-size: 13.5px;
    color: var(--text-muted);
    margin-bottom: 14px;
    line-height: 1.55;
  }}
  .diff-split {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }}
  .diff-pane {{
    background: var(--code-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }}
  .diff-pane-head {{
    padding: 8px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    font-weight: 700;
    border-bottom: 1px solid var(--border);
    background: rgba(255, 255, 255, 0.02);
  }}
  .diff-pane-head.bad {{ color: var(--crimson); }}
  .diff-pane-head.good {{ color: var(--emerald); }}
  pre.diff-code {{
    padding: 14px;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.65;
    color: #cbd5e1;
    white-space: pre-wrap;
    word-break: break-word;
  }}
  .diff-footer {{
    margin-top: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .diff-gain {{
    font-size: 12px;
    color: var(--emerald);
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 5px;
  }}
  .diff-link {{
    font-size: 11.5px;
    color: var(--primary-light);
    text-decoration: none;
    font-weight: 600;
  }}
  .diff-link:hover {{ text-decoration: underline; }}
  .copy-chip {{
    padding: 3px 8px;
    font-size: 10.5px;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: var(--card);
    color: var(--text-muted);
    cursor: pointer;
  }}
  .copy-chip:hover {{ color: var(--text); border-color: var(--primary); }}

  /* SIMULATOR & HOTSPOTS */
  .panel-box {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 26px;
    margin-bottom: 32px;
  }}
  .sim-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 22px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 18px;
  }}
  .sim-chips {{
    display: flex;
    align-items: center;
    gap: 28px;
  }}
  .sim-chip {{ text-align: center; }}
  .sim-chip .lbl {{
    font-size: 11px;
    color: var(--text-dim);
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.5px;
  }}
  .sim-chip .val {{
    font-size: 38px;
    font-weight: 800;
    line-height: 1;
    margin-top: 4px;
    font-variant-numeric: tabular-nums;
  }}
  .sim-arrow {{
    font-size: 20px;
    color: var(--emerald);
  }}
  .sim-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }}
  .sim-item {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 18px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    cursor: pointer;
    transition: all 0.2s var(--ease);
  }}
  .sim-item:hover {{ border-color: var(--border-highlight); }}
  .sim-item input[type="checkbox"] {{
    margin-top: 3px;
    accent-color: var(--primary);
    width: 16px;
    height: 16px;
  }}
  .sim-body {{ flex: 1; }}
  .sim-title {{
    font-size: 13.5px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .sim-desc {{
    font-size: 11.5px;
    color: var(--text-muted);
    margin-top: 2px;
  }}

  .hotspot-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
  }}
  .hotspot-item {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .hotspot-name {{
    font-family: var(--font-mono);
    font-size: 13.5px;
    font-weight: 700;
  }}
  .hotspot-dir {{
    font-size: 11.5px;
    color: var(--text-dim);
    margin-top: 2px;
  }}
  .hotspot-tags {{
    margin-top: 8px;
    display: flex;
    gap: 6px;
  }}
  .hotspot-score {{
    font-size: 26px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }}

  .footer {{
    border-top: 1px solid var(--border);
    background: var(--bg-surface);
    padding: 26px 32px;
    text-align: center;
    font-size: 12.5px;
    color: var(--text-muted);
  }}

  @media (max-width: 1024px) {{
    .hero-grid {{ grid-template-columns: 1fr; }}
    .metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .layer-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .charts-row {{ grid-template-columns: 1fr; }}
    .diff-split {{ grid-template-columns: 1fr; }}
    .sim-grid {{ grid-template-columns: 1fr; }}
    .hotspot-grid {{ grid-template-columns: 1fr; }}
    .exec-cards-row {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<header class="header">
  <div class="header-inner">
    <div class="brand-group">
      <div class="brand-glyph">
        <svg viewBox="0 0 24 24" width="20" height="20"><path d="M12 14l3-3"/><path d="M3.34 16a10 10 0 1 1 17.32 0"/></svg>
      </div>
      <div class="brand-text">
        <h1>Performance Optimizer <span class="badge-tag sev-medium">v2.5</span></h1>
        <p>Production Latency & Scalability Audit • {esc(tech)}</p>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn" onclick="toggleTheme()" aria-label="Toggle Theme">
        <span class="icon" id="themeSvg" style="width:14px;height:14px;">
          <svg viewBox="0 0 24 24" width="14" height="14"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/></svg>
        </span>
        <span>Theme</span>
      </button>
      <button class="btn" onclick="window.print()">
        <span class="icon" style="width:14px;height:14px;"><svg viewBox="0 0 24 24"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg></span>
        <span>PDF Print</span>
      </button>
      <button class="btn btn-primary" onclick="exportJSON()">
        <span class="icon" style="width:14px;height:14px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></span>
        <span>Export JSON</span>
      </button>
    </div>
  </div>
</header>

<nav class="nav-tabs">
  <button class="tab-btn active" onclick="switchTab('dashboard', this)">
    <span class="icon" style="width:15px;height:15px;"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg></span>
    <span>Executive Health</span>
  </button>
  <button class="tab-btn" onclick="switchTab('issues', this)">
    <span class="icon" style="width:15px;height:15px;"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>
    <span>Defect Explorer</span>
    <span class="tab-count">{total}</span>
  </button>
  <button class="tab-btn" onclick="switchTab('simulator', this)">
    <span class="icon" style="width:15px;height:15px;"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg></span>
    <span>Fix Simulator</span>
    <span class="tab-count" style="background:var(--emerald-bg);color:var(--emerald);">Interactive</span>
  </button>
  <button class="tab-btn" onclick="switchTab('files', this)">
    <span class="icon" style="width:15px;height:15px;"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg></span>
    <span>File Hotspots</span>
    <span class="tab-count">{len(worst_files)}</span>
  </button>
  <button class="tab-btn" onclick="switchTab('cicd', this)">
    <span class="icon" style="width:15px;height:15px;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></span>
    <span>CI/CD Governance</span>
  </button>
</nav>

<div class="container">

  <!-- TAB 1: EXECUTIVE HEALTH -->
  <section id="dashboard-tab" class="tab-panel active">
    <div class="hero-grid">
      <div class="score-card">
        <div style="font-size:11.5px;font-weight:700;color:var(--text-dim);letter-spacing:1px;text-transform:uppercase;">Overall System Health</div>
        <div class="score-ring-wrap">
          <svg width="170" height="170" viewBox="0 0 170 170">
            <circle class="score-ring-bg" cx="85" cy="85" r="70" />
            <circle id="heroScoreCircle" class="score-ring-progress" cx="85" cy="85" r="70" stroke="{s_color}" stroke-dashoffset="{ring_offset}" />
          </svg>
          <div class="score-ring-val">
            <span id="heroScoreNum" class="score-ring-num" style="color:{s_color};">{overall}</span>
            <span style="font-size:12px;color:var(--text-dim);font-weight:600;">/ 100</span>
          </div>
        </div>
        <div class="score-status-badge {status_badge_class}">{status_text}</div>
        <div style="font-size:12.5px;color:var(--text-muted);margin-top:10px;text-align:center;">
          {total} performance defects detected across {files_scanned} files analyzed ({duration}s).
        </div>
      </div>

      <div>
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-icon-box">
              <span class="icon"><svg viewBox="0 0 24 24" width="18" height="18"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg></span>
            </div>
            <div class="metric-title">DOM Re-render Waste</div>
            <div class="metric-val" style="color:var(--crimson);">-{metrics.get('dom_render_waste_pct', 0)}%</div>
            <div class="metric-sub">Up to 3x render speedup</div>
          </div>
          <div class="metric-card">
            <div class="metric-icon-box">
              <span class="icon"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg></span>
            </div>
            <div class="metric-title">Query Latency Waste</div>
            <div class="metric-val" style="color:var(--amber);">+{metrics.get('db_query_reduction_pct', 0)}%</div>
            <div class="metric-sub">N+1 & unindexed lookups</div>
          </div>
          <div class="metric-card">
            <div class="metric-icon-box">
              <span class="icon"><svg viewBox="0 0 24 24"><rect x="2" y="8" width="20" height="8" rx="2"/><path d="M6 19v-3"/><path d="M10 19v-3"/><path d="M14 19v-3"/><path d="M18 19v-3"/></svg></span>
            </div>
            <div class="metric-title">Heap Memory Leaks</div>
            <div class="metric-val" style="color:var(--crimson);">{metrics.get('memory_leak_count', 0)}</div>
            <div class="metric-sub">Unbounded RxJS & arrays</div>
          </div>
          <div class="metric-card">
            <div class="metric-icon-box">
              <span class="icon"><svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg></span>
            </div>
            <div class="metric-title">Bundle Bloat Potential</div>
            <div class="metric-val" style="color:var(--primary-light);">{metrics.get('bundle_reduction_kb', 0)} KB</div>
            <div class="metric-sub">Eager routes & * imports</div>
          </div>
        </div>

        <div class="exec-banner">
          <div class="exec-banner-title">
            <span>Primary Action Items for Leadership</span>
            <span style="font-size:11px;color:var(--text-dim);">Ranked by Impact/Effort Ratio</span>
          </div>
          <div class="exec-cards-row">{exec_cards}</div>
        </div>
      </div>
    </div>

    <div class="section-header">
      <h3>Architectural Layer Breakdown</h3>
      <span style="font-size:12px;color:var(--text-dim);">Frontend 40% • Backend 30% • Database 20% • Cloud 10%</span>
    </div>
    <div class="layer-grid">
      <div class="layer-card">
        <div class="layer-top">
          <span class="badge-tag layer-frontend">Frontend UI</span>
          <span style="font-size:12px;color:var(--text-dim);font-family:var(--font-mono);">{by_layer.get('frontend', 0)} issues</span>
        </div>
        <div class="layer-score" style="color:{score_color(s.get('frontend', 100))};">{s.get('frontend', 100)}<span style="font-size:13px;color:var(--text-dim);">/100</span></div>
        <div class="track-bar"><div class="fill-bar" style="width:{s.get('frontend', 100)}%;background:{score_color(s.get('frontend', 100))};"></div></div>
        <div style="font-size:11.5px;color:var(--text-muted);">Change detection, loops, teardown</div>
      </div>

      <div class="layer-card">
        <div class="layer-top">
          <span class="badge-tag layer-backend">Node.js / Seneca</span>
          <span style="font-size:12px;color:var(--text-dim);font-family:var(--font-mono);">{by_layer.get('backend', 0)} issues</span>
        </div>
        <div class="layer-score" style="color:{score_color(s.get('backend', 100))};">{s.get('backend', 100)}<span style="font-size:13px;color:var(--text-dim);">/100</span></div>
        <div class="track-bar"><div class="fill-bar" style="width:{s.get('backend', 100)}%;background:{score_color(s.get('backend', 100))};"></div></div>
        <div style="font-size:11.5px;color:var(--text-muted);">Event loop, N+1 queries, sockets</div>
      </div>

      <div class="layer-card">
        <div class="layer-top">
          <span class="badge-tag layer-database">SQL / Database</span>
          <span style="font-size:12px;color:var(--text-dim);font-family:var(--font-mono);">{by_layer.get('database', 0)} issues</span>
        </div>
        <div class="layer-score" style="color:{score_color(s.get('database', 100))};">{s.get('database', 100)}<span style="font-size:13px;color:var(--text-dim);">/100</span></div>
        <div class="track-bar"><div class="fill-bar" style="width:{s.get('database', 100)}%;background:{score_color(s.get('database', 100))};"></div></div>
        <div style="font-size:11.5px;color:var(--text-muted);">Indexes, deep OFFSET, plan cache</div>
      </div>

      <div class="layer-card">
        <div class="layer-top">
          <span class="badge-tag layer-infra">AWS / Cloud</span>
          <span style="font-size:12px;color:var(--text-dim);font-family:var(--font-mono);">{by_layer.get('infra', 0)} issues</span>
        </div>
        <div class="layer-score" style="color:{score_color(s.get('infra', 100))};">{s.get('infra', 100)}<span style="font-size:13px;color:var(--text-dim);">/100</span></div>
        <div class="track-bar"><div class="fill-bar" style="width:{s.get('infra', 100)}%;background:{score_color(s.get('infra', 100))};"></div></div>
        <div style="font-size:11.5px;color:var(--text-muted);">Lambda CPU throttle, RDS Proxy</div>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-box">
        <h4>Defect Severity Profile</h4>
        <div class="chart-canvas-wrap"><canvas id="chartSeverity"></canvas></div>
      </div>
      <div class="chart-box">
        <h4>Layer Distribution</h4>
        <div class="chart-canvas-wrap"><canvas id="chartLayer"></canvas></div>
      </div>
      <div class="chart-box">
        <h4>Projected Efficiency Improvements</h4>
        <div class="chart-canvas-wrap"><canvas id="chartProjected"></canvas></div>
      </div>
    </div>
  </section>

  <!-- TAB 2: DEFECT EXPLORER -->
  <section id="issues-tab" class="tab-panel">
    <div class="section-header">
      <h3>Defect Diagnostic Console with Code Patches</h3>
      <span style="font-size:12.5px;color:var(--text-dim);">Click any record to expand the source patch</span>
    </div>

    <div class="filter-bar">
      <div class="search-wrap">
        <span class="icon" style="width:14px;height:14px;color:var(--text-dim);"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>
        <input type="text" id="searchInput" placeholder="Search by title, rule ID, filename, or keyword..." onkeyup="filterIssuesTable()">
      </div>
      <div class="pill-group">
        <button class="pill-btn active" onclick="setSeverityFilter('all', this)">All ({total})</button>
        <button class="pill-btn" onclick="setSeverityFilter('critical', this)" style="color:var(--crimson);">Critical ({by_sev.get('critical', 0)})</button>
        <button class="pill-btn" onclick="setSeverityFilter('high', this)" style="color:var(--amber);">High ({by_sev.get('high', 0)})</button>
        <button class="pill-btn" onclick="setSeverityFilter('medium', this)">Medium ({by_sev.get('medium', 0)})</button>
      </div>
      <div class="pill-group">
        <button class="pill-btn active" onclick="setLayerFilter('all', this)">All Layers</button>
        <button class="pill-btn" onclick="setLayerFilter('frontend', this)">Frontend ({by_layer.get('frontend', 0)})</button>
        <button class="pill-btn" onclick="setLayerFilter('backend', this)">Backend ({by_layer.get('backend', 0)})</button>
        <button class="pill-btn" onclick="setLayerFilter('database', this)">Database ({by_layer.get('database', 0)})</button>
        <button class="pill-btn" onclick="setLayerFilter('infra', this)">Infra ({by_layer.get('infra', 0)})</button>
      </div>
    </div>

    <div class="table-shell">
      <table class="diag-table" id="issuesTable">
        <thead>
          <tr>
            <th width="80">Rule ID</th>
            <th>Issue Title & Source File</th>
            <th width="120">Severity</th>
            <th width="120">Layer</th>
            <th width="110">Impact / Effort</th>
            <th width="80">Rank</th>
            <th width="80">Action</th>
          </tr>
        </thead>
        <tbody id="issuesTableBody">
          {table_rows}
        </tbody>
      </table>
    </div>
  </section>

  <!-- TAB 3: FIX SIMULATOR -->
  <section id="simulator-tab" class="tab-panel">
    <div class="panel-box">
      <div class="sim-head">
        <div>
          <h3 style="font-size:18px;font-weight:800;letter-spacing:-0.4px;">Fix Simulator & Sprint ROI Planner</h3>
          <p style="font-size:13px;color:var(--text-muted);margin-top:4px;">
            Toggle planned fixes below to simulate live score improvement, estimated latency reduction, and sprint velocity.
          </p>
        </div>
        <div class="sim-chips">
          <div class="sim-chip">
            <div class="lbl">Baseline Score</div>
            <div class="val" style="color:{s_color};">{overall}</div>
          </div>
          <div class="sim-arrow">→</div>
          <div class="sim-chip">
            <div class="lbl">Simulated Rating</div>
            <div class="val" id="simScoreVal" style="color:var(--emerald);">{overall}</div>
          </div>
        </div>
      </div>

      <div class="sim-grid">
        {sim_checklist}
      </div>
    </div>
  </section>

  <!-- TAB 4: FILE HOTSPOTS -->
  <section id="files-tab" class="tab-panel">
    <div class="section-header">
      <h3>File Defect Density Heatmap</h3>
      <span style="font-size:12px;color:var(--text-dim);">Files with highest concentration of performance risks</span>
    </div>
    <div class="hotspot-grid">
      {file_cards}
    </div>
  </section>

  <!-- TAB 5: CI/CD GOVERNANCE -->
  <section id="cicd-tab" class="tab-panel">
    <div class="panel-box">
      <h3 style="font-size:18px;font-weight:800;margin-bottom:12px;letter-spacing:-0.4px;">Automated CI/CD Quality Gate Setup</h3>
      <p style="font-size:13.5px;color:var(--text-muted);line-height:1.6;margin-bottom:24px;">
        Integrate Performance Optimizer into your GitHub Actions, GitLab CI, or Jenkins pipeline to block performance regressions on pull requests.
      </p>

      <div class="diff-pane" style="margin-bottom:20px;">
        <div class="diff-pane-head good">
          <span class="head-tag">.github/workflows/perf-gate.yml</span>
          <button class="copy-chip" onclick="copySnippet(this)">Copy YAML</button>
        </div>
        <pre class="diff-code">name: Performance Gate
on: [pull_request]

jobs:
  performance-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Run Performance Optimizer Gate
        run: |
          python optimizer.py \
            --frontend ./frontend \
            --backend ./backend \
            --fail-on critical \
            --min-score 75 \
            --json \
            --markdown-summary pr_perf_comment.md
      
      - name: Post PR Comment
        uses: marocchino/sticky-pull-request-comment@v2
        if: always()
        with:
          path: pr_perf_comment.md</pre>
      </div>
    </div>
  </section>

</div>

<footer class="footer">
  <p>Performance Optimizer v2.5 • Zero SonarQube Bloat • {esc(tech)} • Scan: {esc(scan_time)} • {files_scanned} files analyzed</p>
</footer>

<script>
function switchTab(tabId, btn) {{
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const target = document.getElementById(tabId + '-tab');
  if (target) target.classList.add('active');
}}

let currentTheme = 'dark';
function toggleTheme() {{
  currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);
  const icon = document.getElementById('themeSvg');
  if (currentTheme === 'dark') {{
    icon.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/></svg>';
  }} else {{
    icon.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }}
}}

function toggleRow(rowId) {{
  const row = document.getElementById(rowId);
  if (row) {{
    row.classList.toggle('show');
  }}
}}

function copySnippet(btn) {{
  const code = btn.closest('.diff-pane').querySelector('pre').textContent;
  navigator.clipboard.writeText(code).then(() => {{
    const orig = btn.textContent;
    btn.textContent = 'Copied';
    setTimeout(() => btn.textContent = orig, 1500);
  }});
}}

let activeSev = 'all';
let activeLayer = 'all';

function setSeverityFilter(sev, btn) {{
  activeSev = sev;
  btn.parentElement.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filterIssuesTable();
}}

function setLayerFilter(layer, btn) {{
  activeLayer = layer;
  btn.parentElement.querySelectorAll('.pill-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  filterIssuesTable();
}}

function filterIssuesTable() {{
  const query = (document.getElementById('searchInput').value || '').toLowerCase();
  const rows = document.querySelectorAll('#issuesTableBody tr.main-row');

  rows.forEach(r => {{
    const sev = r.dataset.sev;
    const layer = r.dataset.layer;
    const search = r.dataset.search || '';
    const nextExpRow = r.nextElementSibling;

    const matchesSev = (activeSev === 'all' || sev === activeSev);
    const matchesLayer = (activeLayer === 'all' || layer === activeLayer);
    const matchesQuery = !query || search.includes(query) || r.textContent.toLowerCase().includes(query);

    if (matchesSev && matchesLayer && matchesQuery) {{
      r.style.display = '';
    }} else {{
      r.style.display = 'none';
      if (nextExpRow && nextExpRow.classList.contains('expanded-row')) {{
        nextExpRow.classList.remove('show');
      }}
    }}
  }});
}}

const baselineScore = {overall};
function recalculateSimScore() {{
  let score = baselineScore;
  const checkboxes = document.querySelectorAll('.sim-grid input[type="checkbox"]');
  checkboxes.forEach(cb => {{
    if (cb.checked) {{
      score += parseInt(cb.dataset.points || 5, 10);
    }}
  }});
  score = Math.min(100, score);
  const valEl = document.getElementById('simScoreVal');
  valEl.textContent = score;
  valEl.style.color = score >= 80 ? 'var(--emerald)' : score >= 60 ? 'var(--amber)' : 'var(--crimson)';
}}

function exportJSON() {{
  const data = {{
    meta: {json.dumps(self.meta)},
    scores: {json.dumps(self.scores)},
    issues: {json.dumps([i.to_dict() for i in self.issues])}
  }};
  const blob = new Blob([JSON.stringify(data, null, 2)], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'performance_report.json';
  a.click();
}}

window.addEventListener('DOMContentLoaded', () => {{
  new Chart(document.getElementById('chartSeverity'), {{
    type: 'doughnut',
    data: {{
      labels: ['Critical', 'High', 'Medium', 'Low'],
      datasets: [{{
        data: {sev_chart_data},
        backgroundColor: ['#f43f5e', '#f59e0b', '#6366f1', '#64748b'],
        borderWidth: 0
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'right', labels: {{ color: '#94a3b8', boxWidth: 10, font: {{ size: 11 }} }} }} }},
      cutout: '72%'
    }}
  }});

  new Chart(document.getElementById('chartLayer'), {{
    type: 'bar',
    data: {{
      labels: ['Frontend', 'Backend', 'Database', 'Infra'],
      datasets: [{{
        data: {layer_chart_data},
        backgroundColor: ['#6366f1', '#10b981', '#f59e0b', '#06b6d4'],
        borderRadius: 5,
        borderWidth: 0
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', font: {{ size: 11 }} }}, grid: {{ display: false }} }},
        y: {{ ticks: {{ color: '#64748b', font: {{ size: 11 }} }}, grid: {{ color: 'rgba(255,255,255,0.04)' }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('chartProjected'), {{
    type: 'bar',
    data: {{
      labels: ['API Latency', 'DB Queries', 'DOM Cycles', 'Heap Leaks', 'Bundle Size'],
      datasets: [
        {{ label: 'Current Overhead', data: [100, 100, 100, 100, 100], backgroundColor: 'rgba(244,63,94,0.3)', borderRadius: 4, borderWidth: 0 }},
        {{ label: 'After Remediations', data: [15, 8, 12, 0, 48], backgroundColor: 'rgba(16,185,129,0.75)', borderRadius: 4, borderWidth: 0 }}
      ]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ color: '#94a3b8', boxWidth: 10, font: {{ size: 11 }} }} }} }},
      scales: {{
        x: {{ ticks: {{ color: '#64748b', font: {{ size: 10 }} }}, grid: {{ display: false }} }},
        y: {{ ticks: {{ color: '#64748b', font: {{ size: 10 }} }}, grid: {{ color: 'rgba(255,255,255,0.04)' }} }}
      }}
    }}
  }});
}});
</script>
</body>
</html>'''
