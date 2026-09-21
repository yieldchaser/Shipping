#!/usr/bin/env python3
"""
scripts/export_corpus_audit_pdf.py
==================================
Converts docs/maritime_document_corpus_audit.md to a publication-quality PDF
using python-markdown, custom executive styling, and Playwright Chromium print-to-PDF.
"""

import os
import sys
import re
from pathlib import Path
import markdown
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "maritime_document_corpus_audit.md"
PDF_PATH = REPO_ROOT / "docs" / "maritime_document_corpus_audit.pdf"
ARTIFACT_DIR = Path(r"C:\Users\Dell\.gemini\antigravity\brain\b43c34cd-0857-475d-92ff-5a9e0356f6bc")

def build_styled_html(md_content: str) -> str:
    # Pre-process alerts like > [!NOTE] into blockquote divs
    def replace_alert(match):
        alert_type = match.group(1).upper()
        content = match.group(2)
        return f'<div class="alert alert-{alert_type.lower()}"><div class="alert-title">{alert_type}</div><div class="alert-body">{content}</div></div>'

    processed_md = re.sub(
        r'>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*\n((?:>.*(?:\n|$))*)',
        lambda m: replace_alert(m),
        md_content
    )
    # Clean up remaining > in alert body
    lines = []
    in_alert = False
    for line in processed_md.splitlines():
        if '<div class="alert ' in line:
            in_alert = True
            lines.append(line)
        elif in_alert and '</div></div>' in line:
            clean = re.sub(r'^>\s*', '', line)
            lines.append(clean)
            in_alert = False
        elif in_alert:
            clean = re.sub(r'^>\s*', '', line)
            lines.append(clean)
        else:
            lines.append(line)
    processed_md = "\n".join(lines)

    html_body = markdown.markdown(
        processed_md,
        extensions=["tables", "fenced_code", "toc"]
    )

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Maritime Document & Multimodal Intelligence Corpus Audit</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  document.addEventListener("DOMContentLoaded", function() {{
    mermaid.initialize({{
      startOnLoad: true,
      theme: 'neutral',
      flowchart: {{ useMaxWidth: true, htmlLabels: true, curve: 'basis' }}
    }});
  }});
</script>
<style>
  @page {{
    size: A4;
    margin: 18mm 14mm 18mm 14mm;
    @bottom-right {{
      content: counter(page);
    }}
  }}

  *, *:before, *:after {{
    box-sizing: border-box;
  }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.5;
    color: #1a202c;
    background: #fff;
    margin: 0;
    padding: 0;
  }}

  h1 {{
    font-size: 18pt;
    font-weight: 800;
    color: #0f172a;
    border-bottom: 2px solid #0284c7;
    padding-bottom: 6px;
    margin-top: 0;
    margin-bottom: 8px;
    letter-spacing: -0.02em;
  }}

  h2 {{
    font-size: 13pt;
    font-weight: 700;
    color: #1e293b;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 4px;
    margin-top: 20px;
    margin-bottom: 10px;
    page-break-after: avoid;
  }}

  h3 {{
    font-size: 10.5pt;
    font-weight: 700;
    color: #334155;
    margin-top: 14px;
    margin-bottom: 6px;
    page-break-after: avoid;
  }}

  p, ul, ol {{
    margin-top: 4px;
    margin-bottom: 8px;
  }}

  ul, ol {{
    padding-left: 20px;
  }}

  li {{
    margin-bottom: 3px;
  }}

  code {{
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
    font-size: 8.5pt;
    background: #f1f5f9;
    padding: 1px 4px;
    border-radius: 3px;
    color: #0369a1;
  }}

  pre {{
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
    font-size: 8pt;
    line-height: 1.35;
    background: #0f172a;
    color: #f8fafc;
    padding: 10px 12px;
    border-radius: 6px;
    overflow-x: auto;
    margin: 8px 0;
    page-break-inside: avoid;
  }}

  pre code {{
    background: transparent;
    color: inherit;
    padding: 0;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
    font-size: 8.5pt;
    page-break-inside: avoid;
  }}

  th, td {{
    border: 1px solid #cbd5e1;
    padding: 5px 7px;
    text-align: left;
    vertical-align: top;
  }}

  th {{
    background: #f8fafc;
    font-weight: 700;
    color: #0f172a;
    border-bottom: 2px solid #94a3b8;
  }}

  tr:nth-child(even) {{
    background: #f8fafc;
  }}

  hr {{
    border: 0;
    height: 1px;
    background: #e2e8f0;
    margin: 16px 0;
  }}

  .alert {{
    border-left: 4px solid #0284c7;
    background: #f0f9ff;
    padding: 8px 12px;
    margin: 10px 0;
    border-radius: 0 4px 4px 0;
    page-break-inside: avoid;
  }}

  .alert-title {{
    font-weight: 700;
    font-size: 8.5pt;
    color: #0369a1;
    text-transform: uppercase;
    margin-bottom: 2px;
    letter-spacing: 0.05em;
  }}

  .alert-body {{
    font-size: 9pt;
    color: #0c4a6e;
  }}

  .header-tag {{
    font-size: 8pt;
    color: #64748b;
    margin-bottom: 12px;
  }}

  .mermaid {{
    text-align: center;
    margin: 12px 0;
    page-break-inside: avoid;
  }}
</style>
</head>
<body>
{html_body}
</body>
</html>
"""
    return full_html

def convert_md_to_pdf():
    if not DOC_PATH.exists():
        print(f"Error: {DOC_PATH} does not exist.")
        sys.exit(1)

    print(f"Reading markdown from: {DOC_PATH}")
    md_content = DOC_PATH.read_text(encoding="utf-8")

    html_content = build_styled_html(md_content)
    tmp_html = REPO_ROOT / "docs" / "_temp_audit_preview.html"
    tmp_html.write_text(html_content, encoding="utf-8")
    print(f"Generated HTML preview: {tmp_html}")

    print("Launching Playwright to render PDF...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Load local HTML file
        page.goto(f"file:///{tmp_html.as_posix()}", wait_until="networkidle", timeout=60000)
        
        # Allow Mermaid diagrams extra rendering time if needed
        page.wait_for_timeout(2000)

        header_template = """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 7pt; color: #94a3b8; width: 100%; padding: 0 14mm; display: flex; justify-content: space-between;">
            <span>Global Maritime Document & Multimodal Corpus Audit</span>
            <span>September 2026 · Confidential & Proprietary</span>
        </div>
        """

        footer_template = """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 7pt; color: #94a3b8; width: 100%; padding: 0 14mm; display: flex; justify-content: space-between;">
            <span>Repository: Shipping</span>
            <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
        </div>
        """

        print(f"Printing PDF to: {PDF_PATH}")
        page.pdf(
            path=str(PDF_PATH),
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template=header_template,
            footer_template=footer_template,
            margin={
                "top": "16mm",
                "bottom": "16mm",
                "left": "14mm",
                "right": "14mm"
            }
        )
        browser.close()

    if tmp_html.exists():
        tmp_html.unlink()

    # Also copy to artifact directory for easy download/viewing
    if ARTIFACT_DIR.exists():
        artifact_pdf = ARTIFACT_DIR / "maritime_document_corpus_audit.pdf"
        artifact_pdf.write_bytes(PDF_PATH.read_bytes())
        print(f"Saved artifact copy to: {artifact_pdf}")

    pdf_size_mb = PDF_PATH.stat().st_size / (1024 * 1024)
    print(f"\n[SUCCESS] PDF generated successfully! ({pdf_size_mb:.2f} MB)")
    print(f"Path: {PDF_PATH}")

if __name__ == "__main__":
    convert_md_to_pdf()
