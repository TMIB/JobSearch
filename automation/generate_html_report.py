#!/usr/bin/env python3
"""
Generates an HTML report from evaluated_leads.json and resume_report.json.
Called by run_search.sh after the pipeline completes.
"""

import json
import os
import glob
from datetime import datetime

PROJECT_DIR = os.environ.get("PROJECT_DIR", "/Users/YOURNAME/code/jobs")
TMP_DIR = os.path.join(PROJECT_DIR, "automation", "tmp")
LEADS_DIR = os.path.join(PROJECT_DIR, "leads")

def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def find_local_files(company, leads_dir):
    """Find listing txt, resume html, fit analysis, and PDF for a company folder."""
    # Try various folder name formats
    candidates = []
    for d in os.listdir(leads_dir):
        if not os.path.isdir(os.path.join(leads_dir, d)):
            continue
        # Match by lowercase comparison
        if company.lower().replace(" ", "").replace("&", "and").replace("'", "") in d.lower().replace("_", "").replace(" ", ""):
            candidates.append(d)

    if not candidates:
        return None

    folder = candidates[0]
    full = os.path.join(leads_dir, folder)

    txts = glob.glob(os.path.join(full, "*.txt"))
    resumes = glob.glob(os.path.join(full, "resume_*.html"))
    pdfs = glob.glob(os.path.join(full, "YOUR NAME - Resume.pdf"))
    fit = os.path.join(full, "fit_analysis.md")

    return {
        "folder": folder,
        "txt": os.path.basename(txts[0]) if txts else None,
        "resume": os.path.basename(resumes[0]) if resumes else None,
        "pdf": "YOUR NAME - Resume.pdf" if pdfs else None,
        "fit": "fit_analysis.md" if os.path.exists(fit) else None,
    }

def score_class(score):
    if score >= 0.85:
        return "score-high"
    elif score >= 0.65:
        return "score-med"
    return "score-low"

def escape(s):
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def location_tag(loc):
    if not loc:
        return ""
    loc_lower = loc.lower()
    if any(x in loc_lower for x in ["boulder", "denver", "colorado", "arvada", "lakewood", "front range", "co "]):
        return f'<span class="tag colorado">{escape(loc)}</span>'
    if any(x in loc_lower for x in ["remote", "anywhere", "work from"]):
        return f'<span class="tag remote">{escape(loc)}</span>'
    if any(x in loc_lower for x in ["on-site", "hybrid", "in-office"]):
        return f'<span class="tag onsite">{escape(loc)}</span>'
    return f'<span class="tag location">{escape(loc)}</span>'

def local_links_html(company, leads_dir):
    files = find_local_files(company, leads_dir)
    if not files:
        return ""

    base = f"file://{leads_dir}/{files['folder']}"
    links = []
    if files["txt"]:
        links.append(f'<a href="{base}/{files["txt"]}">📄 Listing</a>')
    if files["resume"]:
        links.append(f'<a href="{base}/{files["resume"]}">📝 Resume</a>')
    if files["fit"]:
        links.append(f'<a href="{base}/fit_analysis.md">📊 Fit Analysis</a>')
    if files["pdf"]:
        from urllib.parse import quote
        links.append(f'<a href="{base}/{quote(files["pdf"])}">📑 PDF</a>')

    if not links:
        return ""
    return f'<div class="local-links">{" ".join(links)}</div>'

def generate_html():
    evals = load_json(os.path.join(TMP_DIR, "evaluated_leads.json"), {"leads": []})
    resumes = load_json(os.path.join(TMP_DIR, "resume_report.json"), {"resumes_generated": 0})

    run_date = evals.get("run_date", datetime.now().strftime("%Y-%m-%d"))
    leads = evals.get("leads", [])

    resume_leads = [l for l in leads if l.get("action") == "generate_resume"]
    report_leads = [l for l in leads if l.get("action") == "report_only"]
    rejected = [l for l in leads if l.get("dealbreaker")]

    resume_leads.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    report_leads.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Search Report — {run_date}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px; line-height: 1.5; color: #1a1a1a;
    background: #f5f5f7; padding: 20px; max-width: 1100px; margin: 0 auto;
  }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  .subtitle {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
  .stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }}
  .stat-card {{
    background: white; border-radius: 10px; padding: 16px;
    text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .stat-card .number {{ font-size: 28px; font-weight: 700; }}
  .stat-card .label {{ font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
  .stat-card.highlight .number {{ color: #0071e3; }}
  .stat-card.warning .number {{ color: #ff9500; }}
  .section {{ margin-bottom: 24px; }}
  .section-header {{
    background: white; border-radius: 10px 10px 0 0; padding: 14px 20px;
    font-size: 16px; font-weight: 600; border-bottom: 1px solid #e5e5e5;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .section-header .count {{
    background: #e5e5e5; border-radius: 12px; padding: 2px 10px;
    font-size: 13px; font-weight: 500;
  }}
  .lead-card {{
    background: white; border-bottom: 1px solid #f0f0f0; padding: 16px 20px;
  }}
  .lead-card:last-child {{ border-radius: 0 0 10px 10px; border-bottom: none; }}
  .lead-header {{
    display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;
  }}
  .lead-title {{ font-weight: 600; font-size: 15px; }}
  .lead-company {{ color: #0071e3; }}
  .score-badge {{
    font-size: 13px; font-weight: 700; padding: 3px 10px; border-radius: 12px;
    white-space: nowrap; flex-shrink: 0; margin-left: 12px;
  }}
  .score-high {{ background: #d4edda; color: #155724; }}
  .score-med {{ background: #fff3cd; color: #856404; }}
  .score-low {{ background: #f8d7da; color: #721c24; }}
  .lead-meta {{
    display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px;
    color: #666; margin-bottom: 8px;
  }}
  .tag {{
    display: inline-block; background: #e8f0fe; color: #1a73e8;
    font-size: 11px; font-weight: 500; padding: 2px 8px; border-radius: 4px;
    text-transform: uppercase; letter-spacing: 0.3px;
  }}
  .tag.location {{ background: #e6f4ea; color: #137333; }}
  .tag.comp {{ background: #fef7e0; color: #b06000; }}
  .tag.remote {{ background: #d4edda; color: #155724; }}
  .tag.onsite {{ background: #f8d7da; color: #721c24; }}
  .tag.colorado {{ background: #d4edda; color: #0d5524; font-weight: 700; }}
  .tag.stale {{ background: #f8d7da; color: #721c24; }}
  .narrative {{ font-size: 13px; color: #444; font-style: italic; margin-top: 6px; }}
  .apply-link {{
    display: inline-block; margin-top: 8px; font-size: 13px;
    color: #0071e3; text-decoration: none;
  }}
  .apply-link:hover {{ text-decoration: underline; }}
  .local-links {{ display: flex; gap: 12px; margin-top: 6px; font-size: 12px; }}
  .local-links a {{
    color: #666; text-decoration: none; background: #f0f0f0;
    padding: 2px 8px; border-radius: 4px;
  }}
  .local-links a:hover {{ background: #e0e0e0; color: #333; }}
  details {{ margin-top: 8px; }}
  summary {{ font-size: 12px; color: #888; cursor: pointer; }}
  summary:hover {{ color: #555; }}
  .score-grid {{
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 6px; margin-top: 8px; font-size: 12px;
  }}
  .score-item {{ background: #f9f9f9; padding: 6px 10px; border-radius: 6px; }}
  .score-item .dim-name {{ color: #888; font-size: 11px; }}
  .score-item .dim-score {{ font-weight: 600; }}
  .score-item .dim-reason {{ color: #666; font-size: 11px; margin-top: 2px; }}
  .flag {{ font-size: 12px; margin-top: 4px; padding: 4px 8px; border-radius: 4px; }}
  .flag.warn {{ background: #fff3cd; color: #856404; }}
  .flag.good {{ background: #d4edda; color: #155724; }}
  .review-list {{ background: white; border-radius: 0 0 10px 10px; }}
  .review-item {{
    padding: 10px 20px; border-bottom: 1px solid #f0f0f0;
    display: flex; justify-content: space-between; align-items: center; font-size: 13px;
  }}
  .review-item:last-child {{ border-bottom: none; border-radius: 0 0 10px 10px; }}
  .review-item a {{ color: #0071e3; text-decoration: none; }}
  .review-item a:hover {{ text-decoration: underline; }}
  .review-item .ri-meta {{ color: #888; font-size: 12px; margin-left: 12px; white-space: nowrap; }}
  .rejection-list {{
    background: white; border-radius: 0 0 10px 10px;
    padding: 12px 20px; font-size: 13px; color: #666;
  }}
  .rejection-list li {{ margin-bottom: 4px; }}
  .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 30px; padding: 20px; }}
</style>
</head>
<body>

<h1>Daily Job Search Report</h1>
<div class="subtitle">{run_date} &middot; SerpAPI + Claude Pipeline</div>

<div class="stats">
  <div class="stat-card"><div class="number">{evals.get("total_evaluated", len(leads))}</div><div class="label">Evaluated</div></div>
  <div class="stat-card highlight"><div class="number">{len(resume_leads)}</div><div class="label">Resumes Generated</div></div>
  <div class="stat-card warning"><div class="number">{len(report_leads)}</div><div class="label">Worth Reviewing</div></div>
  <div class="stat-card"><div class="number">{len(rejected)}</div><div class="label">Rejected</div></div>
</div>
'''

    # Resume leads section
    if resume_leads:
        html += f'''<div class="section">
  <div class="section-header">New Leads — Resumes Generated<span class="count">{len(resume_leads)}</span></div>
'''
        for l in resume_leads:
            score = l.get("final_score", 0)
            company = l.get("company", "Unknown")
            title = l.get("title", "Unknown")
            loc = l.get("location", "")
            comp = l.get("compensation")
            category = l.get("category", "")
            narrative = l.get("narrative_angle", "")
            apply_url = l.get("application_url") or l.get("url", "")
            stale = l.get("stale_risk", "")
            scores = l.get("scores", {})
            reasoning = l.get("reasoning", {})

            dims = ["level_match", "role_category", "location_fit", "coding_interview_risk", "narrative_fit", "company_maturity"]
            dim_labels = ["Level", "Category", "Location", "Coding Risk", "Narrative", "Company"]

            html += f'''  <div class="lead-card">
    <div class="lead-header">
      <div class="lead-title"><span class="lead-company">{escape(company)}</span> — {escape(title)}</div>
      <span class="score-badge {score_class(score)}">{score:.2f}</span>
    </div>
    <div class="lead-meta">
      {location_tag(loc)}
'''
            if comp:
                html += f'      <span class="tag comp">{escape(comp)}</span>\n'
            if category:
                html += f'      <span class="tag">{escape(category)}</span>\n'
            if stale:
                html += f'      <span class="tag stale">Stale risk: {escape(stale)}</span>\n'
            html += '    </div>\n'

            if narrative:
                html += f'    <div class="narrative">{escape(narrative)}</div>\n'

            if apply_url:
                html += f'    <a class="apply-link" href="{escape(apply_url)}" target="_blank">Apply &rarr;</a>\n'

            html += local_links_html(company, LEADS_DIR) + '\n'

            # Score breakdown
            html += '    <details>\n      <summary>Score breakdown</summary>\n      <div class="score-grid">\n'
            for dim, label in zip(dims, dim_labels):
                s = scores.get(dim, 0)
                r = reasoning.get(dim, "")
                html += f'        <div class="score-item"><div class="dim-name">{label}</div><div class="dim-score">{s}</div><div class="dim-reason">{escape(str(r)[:150])}</div></div>\n'
            html += '      </div>\n    </details>\n'
            html += '  </div>\n\n'

        html += '</div>\n'

    # Worth reviewing section
    if report_leads:
        html += f'''<div class="section">
  <div class="section-header">Worth Reviewing — Below Resume Threshold<span class="count">{len(report_leads)}</span></div>
  <div class="review-list">
'''
        for l in report_leads:
            score = l.get("final_score", 0)
            company = l.get("company", "Unknown")
            title = l.get("title", "Unknown")
            loc = l.get("location", "")
            apply_url = l.get("application_url") or l.get("url", "")
            level_r = (l.get("reasoning") or {}).get("level_match", "")

            html += f'    <div class="review-item"><div class="ri-title">'
            if apply_url:
                html += f'<a href="{escape(apply_url)}" target="_blank">'
            html += f'<strong>{escape(company)}</strong> — {escape(title)}'
            if apply_url:
                html += '</a>'
            if level_r:
                html += f' <span style="color:#888;font-size:11px">— {escape(str(level_r)[:100])}</span>'
            html += f'</div><div class="ri-meta">{score:.2f} &middot; {escape(loc)}</div></div>\n'

        html += '  </div>\n</div>\n'

    # Dealbreaker rejections
    if rejected:
        html += f'''<div class="section">
  <div class="section-header">Dealbreaker Rejections<span class="count">{len(rejected)}</span></div>
  <div class="rejection-list"><ul>
'''
        for l in rejected:
            company = l.get("company", "Unknown")
            title = l.get("title", "Unknown")
            db = l.get("dealbreaker", "unknown")
            html += f'    <li><strong>{escape(company)}</strong> — {escape(title)} — <em>{escape(db)}</em></li>\n'
        html += '  </ul></div>\n</div>\n'

    html += f'''<div class="footer">
  Generated by Job Search Pipeline &middot; {run_date} &middot; {evals.get("total_evaluated", len(leads))} listings evaluated via SerpAPI + Claude
</div>
</body>
</html>'''

    output_path = os.path.join(LEADS_DIR, "new_leads_report.html")
    with open(output_path, "w") as f:
        f.write(html)
    print(f"HTML report written to {output_path}")

if __name__ == "__main__":
    generate_html()
