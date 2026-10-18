"""Second, independent read of image tables: every number in an MD table must be confirmed by the source.

A number counts as confirmed when it is on the PDF text layer, or in Nace NDI Parse's reading of the PDF
(parse_mode "high", figures omitted, so charts are not turned into tables). Whatever is left is listed per MD
with its table row, for a look at the rendered page (scripts/verify/page_view.py side ... --grep ROW).

Nace output is cached per PDF under .reparse_staging/nace_second_read/ (keyed by file sha), so reruns are free.
Keys: ~/.nace/keys.env (NACE_API_KEY, NACE_API_KEY_2, ...), next key on 402. Cost: 2 credits/page.

    python scripts/qa/nace_second_read.py --source banchero_costa [--limit 5] [-j 6] [--no-nace] [--only LIST]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path("C:/Users/Dell/Github/Shipping")
CACHE = ROOT / ".reparse_staging" / "nace_second_read"
MD_ROOT = ROOT / "data" / "extracted" / "md"
NUM = re.compile(r"\d[\d.,]*\d|\d")
sys.path.insert(0, str(Path(__file__).parent))
from nace_crosscheck import keys as nace_keys  # noqa: E402


def norm(n: str) -> set[str]:
    """3.285 = 3,285 = 3285; 24.0 = 24; trailing % / sign ignored."""
    n = n.strip(".,")
    out = {n, re.sub(r"[.,]", "", n)}
    for s in (n.replace(",", ""), n.replace(".", "").replace(",", "."), n.replace(",", ".")):
        try:
            out.add(repr(round(float(s), 4)))
        except ValueError:
            pass
    return out


def pool(text: str) -> set[str]:
    return {k for n in NUM.findall(text) for k in norm(n)}


def source_pdf(md_text: str) -> Path | None:
    m = re.search(r'^source_file:\s*"?([^"\r\n]+\.pdf)', md_text, re.M)
    if not m:
        return None
    for base in (MAIN, ROOT):
        if (base / m.group(1)).exists():
            return base / m.group(1)
    return None


def nace_read(pdf: Path) -> str:
    sha = hashlib.sha1(pdf.read_bytes()).hexdigest()[:16]
    cp = CACHE / f"{sha}.json"
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))["markdown"]
    from nace_sdk import NaceClient
    n_pages = len(pymupdf.open(pdf))
    tries = 0
    for k in nace_keys():
        while True:
            try:
                with NaceClient(api_key=k) as c:
                    up = c.documents.upload(str(pdf), path="second_read/" + pdf.name, on_conflict="new_version")
                    src = {"type": "workspace_file", "workspace_id": up.workspace_id, "file_id": up.file_id}
                    job = c.documents.parse(src, page_ranges=[{"start": 1, "end": n_pages}], parse_mode="high",
                                            output={"formats": ["markdown"], "table_format": "html",
                                                    "include_page_markers": True},
                                            figures={"mode": "omit"}, wait_seconds=60)
                    t0 = time.time()
                    while job.status not in ("succeeded", "failed", "cancelled") and time.time() - t0 < 1800:
                        time.sleep(10)
                        job = c.jobs.get(job.job_id)
                    if job.status != "succeeded":
                        raise RuntimeError(f"nace job {job.job_id} {job.status}: {getattr(job, 'error', None)}")
                    md = job.result["document"]["markdown"]
                    CACHE.mkdir(parents=True, exist_ok=True)
                    cp.write_text(json.dumps({"pdf": pdf.name, "markdown": md, "job_id": job.job_id},
                                             ensure_ascii=False), encoding="utf-8")
                    return md
            except Exception as e:  # noqa: BLE001 - next key on no credit, retry transient, re-raise the rest
                s = str(e)
                if "402" in s or "insufficient_credit" in s.lower():
                    break
                if any(t in s for t in ("503", "502", "504", "429", "timed out", "not confirmed")) and tries < 6:
                    tries += 1
                    time.sleep(15 * tries)
                    continue
                raise
    raise RuntimeError("all Nace keys are out of credit")


def check(md: Path, use_nace: bool) -> dict:
    text = md.read_text(encoding="utf-8", errors="replace")
    pdf = source_pdf(text)
    row = {"md": md.relative_to(ROOT).as_posix(), "table_nums": 0, "layer_ok": 0, "nace_ok": 0, "unconfirmed": 0,
           "rows": "", "error": ""}
    if not pdf:
        row["error"] = "no pdf"
        return row
    try:
        layer = set()
        with pymupdf.open(pdf) as doc:
            for pg in doc:
                layer |= pool(pg.get_text())
        nace = None
        bad_rows = []
        for ln in text.splitlines():
            if not ln.lstrip().startswith("|") or re.match(r"^\|[\s:|-]+\|?$", ln):
                continue
            miss = []
            for n in NUM.findall(ln):
                if len(re.sub(r"[.,]", "", n)) < 2:
                    continue
                row["table_nums"] += 1
                k = norm(n)
                if k & layer:
                    row["layer_ok"] += 1
                    continue
                if use_nace and nace is None:
                    nace = pool(nace_read(pdf))
                if nace is not None and k & nace:
                    row["nace_ok"] += 1
                    continue
                miss.append(n)
            if miss:
                row["unconfirmed"] += len(miss)
                bad_rows.append(ln.strip()[:160] + "  <<" + " ".join(miss))
        row["rows"] = "\n".join(bad_rows)
    except Exception as e:  # noqa: BLE001
        row["error"] = f"{type(e).__name__}: {e}"[:300]
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("-j", type=int, default=6)
    ap.add_argument("--no-nace", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--only", help="file listing the MD paths to check (e.g. those a --no-nace pass left unconfirmed)")
    a = ap.parse_args()
    mds = sorted((MD_ROOT / a.source).rglob("*.md"))
    if a.only:
        keep = {Path(x.strip()).name for x in Path(a.only).read_text(encoding="utf-8").splitlines() if x.strip()}
        mds = [m for m in mds if m.name in keep]
    mds = mds[: a.limit]
    out = Path(a.out or ROOT / ".reparse_staging" / f"second_read_{a.source}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["md", "table_nums", "layer_ok", "nace_ok", "unconfirmed", "rows", "error"]
    tot = dict.fromkeys(["table_nums", "layer_ok", "nace_ok", "unconfirmed"], 0)
    with out.open("w", newline="", encoding="utf-8") as f, ThreadPoolExecutor(a.j) as ex:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        for i, r in enumerate(ex.map(lambda m: check(m, not a.no_nace), mds), 1):
            w.writerow(r)
            f.flush()
            for k in tot:
                tot[k] += r[k]
            print(f"{i}/{len(mds)} {r['md'].rsplit('/', 1)[-1][:60]} nums={r['table_nums']} "
                  f"unconfirmed={r['unconfirmed']} {r['error'][:80]}", flush=True)
    print(out, tot)


if __name__ == "__main__":
    main()
