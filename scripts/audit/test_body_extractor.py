"""
Inspect content extraction across all 511 Signal HTML files.
Test finding the true article body.
"""

import glob
import os
import re
from bs4 import BeautifulSoup

def get_best_body(soup):
    # Find all potential rich text divs
    candidates = []
    for div in soup.find_all('div'):
        classes = div.get('class', [])
        cl_str = ' '.join(classes)
        # Skip sidebar, footer, related items, navigation
        if any(skip in cl_str for skip in ['side-bar', 'fs-toc', 'newsroom-three_x', 'footer', 'nav', 'navigation', 'social']):
            continue
        if any(target in cl_str for target in ['w-richtext', 'newsroom-rich_texts', 'post-body', 'article-body']):
            txt = div.get_text(strip=True)
            candidates.append((len(txt), div))

    if not candidates:
        # Fallback to any div with significant text
        for div in soup.find_all('div'):
            classes = div.get('class', [])
            cl_str = ' '.join(classes)
            if any(skip in cl_str for skip in ['side-bar', 'fs-toc', 'newsroom-three_x', 'footer', 'nav', 'navigation', 'social', 'section-news-hero', 'newsroom_wrapper']):
                continue
            txt = div.get_text(strip=True)
            if len(txt) > 200:
                candidates.append((len(txt), div))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1], candidates[0][0]
    return None, 0

def main():
    html_files = sorted(glob.glob('corpus/07-signal/html/*.html'))
    stubs = []
    recovered = []
    good = []

    for h in html_files:
        slug = os.path.splitext(os.path.basename(h))[0]
        soup = BeautifulSoup(open(h, encoding='utf-8', errors='ignore').read(), 'html.parser')
        body_div, length = get_best_body(soup)

        if length < 200:
            stubs.append((slug, length))
        elif slug == 'signal-ocean-using-ai-to-bring-ship-management-into-the-21st-century':
            recovered.append((slug, length))
        else:
            good.append((slug, length))

    print(f"Total HTML files: {len(html_files)}")
    print(f"Good content articles (>200 chars): {len(good) + len(recovered)}")
    print(f"Recovered articles that had 'hide' class: {len(recovered)}")
    for r, l in recovered:
        print(f"  {r}: {l} chars")
    print(f"True stubs (<200 chars): {len(stubs)}")
    print(f"Sample stubs: {[s[0] for s in stubs[:5]]}")

if __name__ == '__main__':
    main()
