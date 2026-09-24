"""Calibrate the glyph-cipher detector against KNOWN-CIPHERED and KNOWN-CLEAN pages.

The first detector was WRONG. It flagged any span that was punctuation-dense and had
no lowercase, so it fired on ordinary table headers like "± (%)" and "± ($)" - which
have no lowercase and are ~50% punctuation. That produced a 32.9% "paid surface" for
advanced_shipping on a page that renders perfectly (verified by eye). A broken check
condemns correct work, so the instrument gets calibrated before its readings are used.

Calibration set:
  CIPHERED (must be detected): banchero pages whose values were proven ciphered -
      LlamaParse recovered them 13/13 where the text layer read `!"#$#%&`.
  CLEAN (must NOT be detected): advanced_shipping p1 (verified by eye this session),
      agora pages (scan said 0%), plus generic prose/heading spans.

A detector ships only if it scores 100% on both sets.
"""
import glob
import pymupdf

# --- candidate rules -------------------------------------------------------

def rule_old(text):
    """Original: punctuation-dense + no lowercase. Known to over-fire."""
    CIPHER = set('!"#$%&()*')
    t = text.strip()
    if len(t) < 4:
        return False
    ratio = sum(1 for c in t if c in CIPHER) / len(t)
    return ratio > 0.35 and not any(c.islower() for c in t)


def rule_new(text):
    """Cipher signature: an unbroken symbol run with several strong markers.

    Key discriminators learned from the false positives:
      * normal headers contain SPACES ("± (%)"); cipher runs do not
      * normal headers carry few strong markers ("± (%)" has one);
        cipher runs carry several (!"#$&* appear constantly)
      * cipher runs are longer than a short unit label
    """
    STRONG = set('!"#$&*')
    t = text.strip()
    if len(t) < 6:
        return False
    if any(c.isspace() for c in t):
        return False
    return sum(1 for c in t if c in STRONG) >= 2


def spans(page):
    out = []
    for blk in page.get_text('dict')['blocks']:
        for ln in blk.get('lines', []):
            for sp in ln['spans']:
                if sp['text'].strip():
                    out.append(sp['text'])
    return out


def page_hits(page, rule):
    return [t for t in spans(page) if rule(t)]


def evaluate(name, pdf, pages, expect_cipher, rule):
    d = pymupdf.open(pdf)
    tp = fp = 0
    detail = []
    for pno in pages:
        if pno >= d.page_count:
            continue
        hits = page_hits(d[pno], rule)
        got = bool(hits)
        if expect_cipher:
            if got:
                tp += 1
            else:
                detail.append(f'    MISS page {pno+1} (expected cipher, none found)')
        else:
            if got:
                fp += 1
                detail.append(f'    FALSE POSITIVE page {pno+1}: {hits[:3]}')
    d.close()
    verdict = 'OK' if ((tp == len(pages) if expect_cipher else fp == 0)) else 'FAIL'
    print(f'  [{verdict}] {name}: {"detected" if expect_cipher else "clean-check"} '
          f'tp={tp} fp={fp} over {len(pages)} pages')
    for line in detail[:6]:
        print(line)
    return verdict == 'OK'


def main():
    print('=' * 88)
    print('DETECTOR CALIBRATION')
    print('=' * 88)

    banch = sorted(glob.glob('corpus/01-brokers/banchero_costa/2026/*W03*.pdf'))
    adv = sorted(glob.glob('corpus/01-brokers/advanced_shipping/2024/*W03*.pdf'))
    agora = sorted(glob.glob('corpus/01-brokers/agora/*/*.pdf'))

    print('\n--- KNOWN-CIPHERED: banchero 2026 W03 (LlamaParse proved it) ---')
    if banch:
        evaluate('banchero W03 (old rule)', banch[0], [7, 8], True, rule_old)
        evaluate('banchero W03 (new rule)', banch[0], [7, 8], True, rule_new)
    else:
        print('  (banchero W03 pdf not found)')

    print('\n--- KNOWN-CLEAN: advanced_shipping 2024 W03 (verified by eye) ---')
    if adv:
        evaluate('adv W03 (old rule)', adv[0], list(range(0, 8)), False, rule_old)
        evaluate('adv W03 (new rule)', adv[0], list(range(0, 8)), False, rule_new)

    print('\n--- KNOWN-CLEAN: agora (scan reported 0%) ---')
    if agora:
        picks = [agora[0], agora[len(agora)//2], agora[-1]]
        d_all = []
        for p in picks:
            dd = pymupdf.open(p)
            d_all.extend([p, list(range(dd.page_count))])
            dd.close()
        # evaluate a few pages of each
        for i, p in enumerate(picks[:2]):
            evaluate(f'agora[{i}] (new rule)', p, list(range(0, 6)), False, rule_new)


if __name__ == '__main__':
    main()
