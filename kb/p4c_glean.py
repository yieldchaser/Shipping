"""P4c gleaning pass - owner decision 2: a free second Ultrafast pass over every packed call.

DESIGN NOTE (plan §7.2-§7.4 + C1 owner reply, 2026-02-19)
Recall, not precision, is P4c's weak spot: the chosen free extractor scored recall 0.5362 on the
adjudicated gold set against glm-5.3's 0.8333 (P4b bake-off). The owner approved a *free* recall
pass: run the same extractor again over the same pack, but tell it what the first answer already
returned and ask only for what it missed. Same STATIC_PROMPT, same tool schema, same packing, same
temperature, same max_tokens - the only difference is an appended `<first_pass_records>` block plus
a `<glean_instruction>` tail in the user turn, so every sentence-id / quote / number rule is
unchanged and the existing gate applies verbatim. The pass runs under its own pass name
(`p4c_glean`), which means its raws live in a separate namespace and a resumed run never confuses
the two. Merging happens later (`p4c_union.py`): gleaned records are unioned into the bulk stream and
deduped by signature, so a repeated fact costs nothing but a silently dropped fact is recovered.
Nothing is billed: the Ultrafast route is free.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import p4b_run as B  # noqa: E402
import p4c_gate as G  # noqa: E402
import p4c_run as PR  # noqa: E402
import runner as R  # noqa: E402
from extract_schema import STATIC_PROMPT, NUMBER_RE, parse_extraction  # noqa: E402

GLEAN_PASS = "p4c_glean"
BULK_PASS = PR.BULK_PASS
GLEAN_PACKS = PR.OUT / "packs_glean.jsonl"
MAX_LINES = 160   # bound the first-pass block; a packed call cannot exceed 6 blocks anyway

GLEAN_INSTRUCTION = (
    "You already read this document once. <first_pass_records> lists the records that first answer "
    "returned for exactly these chunks, and they are already stored. Do not return them again. "
    "Read the same numbered sentences again and return ONLY the facts the first answer missed: "
    "voyages, fixtures, sales, orders, demolitions, ownership / management / charter links, events, "
    "forecasts and new entity declarations that are present in the text but absent from that list. "
    "Every rule of the extraction task is unchanged - same chunk ids, same sentence ids, quote the "
    "sentences you used, print values exactly as the text prints them, and invent nothing. If "
    "nothing is missing, answer no_content=true with empty arrays."
)


def _nums(text: str) -> str:
    vals = NUMBER_RE.findall(str(text or ""))
    return ",".join(dict.fromkeys(vals))


def _attrs(attrs) -> str:
    out = []
    for a in attrs or []:
        if isinstance(a, dict):
            key, val = a.get("key"), a.get("value_as_printed")
        else:  # parsed pydantic Attr from a stored raw
            key, val = getattr(a, "key", ""), getattr(a, "value_as_printed", "")
        out.append(f"{key}={val}")
    return ",".join(out)


def first_pass_lines(pack: dict, model: str, mode: str) -> list[str]:
    """Compact 'already extracted' lines from the bulk raw of this pack; [] if absent/unparseable."""
    try:
        path = G.raw_for(BULK_PASS, model, mode, pack)
        text, _usage = G.read_raw(path)
    except OSError:
        return []
    if not text or not text.strip():
        return []
    ext, _err = parse_extraction(text)
    if ext is None:
        return []
    lines: list[str] = []
    for f in ext.state_facts:
        nums = _nums(" ".join([f.valid_from_printed, f.valid_to_printed,
                               _attrs(f.attrs_printed)]))
        lines.append(f"{f.chunk} {f.sids} state_fact {f.type} {f.src} -> {f.dst} "
                     f"attrs=[{_attrs(f.attrs_printed)}] from={f.valid_from_printed!r} "
                     f"to={f.valid_to_printed!r} nums={nums}")
    for e in ext.events:
        roles = ",".join(f"{r.role}:{r.entity}" for r in (e.roles or []))
        nums = _nums(" ".join([e.summary, e.when_printed, e.magnitude_printed]))
        lines.append(f"{e.chunk} {e.sids} event {e.type} {e.summary!r} roles=[{roles}] "
                     f"when={e.when_printed!r} mag={e.magnitude_printed!r} nums={nums}")
    for c in ext.claims:
        nums = _nums(c.horizon_printed)
        lines.append(f"{c.chunk} {c.sids} claim {c.kind} subjects=[{','.join(c.subjects or [])}] "
                     f"dir={c.direction} horizon={c.horizon_printed!r} nums={nums}")
    for n in ext.new_entities:
        lines.append(f"{n.chunk} {n.sids} new_entity {n.type} {n.name!r} id={n.id}")
    return lines[:MAX_LINES]


def glean_messages(pack: dict, lines: list[str]) -> list[dict]:
    """System prompt byte-identical to the bulk pass; user turn gains the first-pass block."""
    base = B.user_prompt(pack["doc"], pack["blocks"], pack.get("known") or [])
    if lines:
        body = "\n".join(lines)
        tail = (f"<first_pass_records>\n{body}\n</first_pass_records>\n"
                f"<glean_instruction>{GLEAN_INSTRUCTION}</glean_instruction>")
    else:
        tail = ("<first_pass_records> none - the first answer returned nothing usable "
                "</first_pass_records>\n"
                f"<glean_instruction>{GLEAN_INSTRUCTION}</glean_instruction>")
    return [{"role": "system", "content": STATIC_PROMPT},
            {"role": "user", "content": base + "\n" + tail}]


def job_maker(bulk_model: str, bulk_mode: str):
    """Closure for `p4c_run.run_packs(job_maker=...)`: same job key, gleaning user turn."""

    def make(pass_name: str, model: str, mode: str, pack: dict) -> dict:
        job = B.make_job(pass_name, model, mode, pack)
        lines = first_pass_lines(pack, bulk_model, bulk_mode)
        job["messages"] = glean_messages(pack, lines)
        job["meta"] = dict(job.get("meta") or {}, glean_of=BULK_PASS, first_pass_records=len(lines))
        return job

    return make


def cmd_prepare(args) -> int:
    """Write the gleaning pack list: every pack whose bulk raw parsed into a usable first answer.

    Packs the bulk pass never stored (call errors) have nothing to glean from, so they are skipped
    here and reported - they stay in the rule-6 ladder, not in this pass.
    """
    bulk_model = args.bulk_model or args.model
    bulk_mode = PR.load_modes().get(bulk_model)
    if not bulk_mode:
        raise SystemExit(f"no transport mode for the bulk model {bulk_model}")
    packs_path = Path(args.packs) if args.packs else PR.PACKS
    out = Path(args.out_packs)
    out.parent.mkdir(parents=True, exist_ok=True)
    packs = chunks = skipped = 0
    tmp = out.with_suffix(out.suffix + ".tmp")
    with packs_path.open("r", encoding="utf-8") as src, tmp.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            pack = json.loads(line)
            packs += 1
            if not first_pass_lines(pack, bulk_model, bulk_mode):
                skipped += 1
                continue
            dst.write(line if line.endswith("\n") else line + "\n")
            chunks += len(pack.get("chunk_ids") or [])
    tmp.replace(out)
    print(json.dumps({"packs_scanned": packs, "packs_written": packs - skipped,
                      "packs_skipped": skipped, "chunks": chunks, "out": str(out)}, indent=2))
    return 0


def cmd_run(args) -> int:
    model = args.model
    mode = PR.load_modes().get(model)
    if not mode:
        raise SystemExit(f"no transport mode for {model}: rerun the P4c transport preflight")
    bulk_model = args.bulk_model or model
    bulk_mode = PR.load_modes().get(bulk_model)
    if not bulk_mode:
        raise SystemExit(f"no transport mode for the bulk model {bulk_model}")
    cap = args.cap if args.cap is not None else max(0.0, B.PIPELINE_CAP - R.spent())
    packs = Path(args.packs) if args.packs else PR.PACKS
    st = PR.run_packs(GLEAN_PASS, model, cap, packs_path=packs, limit=args.limit,
                      shard=args.shard, job_maker=job_maker(bulk_model, bulk_mode))
    print(json.dumps({k: st[k] for k in ("pass", "model", "mode", "packs", "packs_skipped",
                                         "chunks", "chunks_skipped", "cost_usd", "wall_s")},
                     indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--prepare", action="store_true",
                    help="write --out-packs: the packs whose bulk raw yields a first-pass list")
    ap.add_argument("--model", default="DeepSeek-V4.1-Flash")
    ap.add_argument("--bulk-model", default=None, help="model whose raws seed <first_pass_records>")
    ap.add_argument("--packs", default=None)
    ap.add_argument("--out-packs", default=str(GLEAN_PACKS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=PR.SHARD)
    ap.add_argument("--cap", type=float, default=None)
    args = ap.parse_args(argv)
    if args.prepare:
        return cmd_prepare(args)
    if args.run:
        return cmd_run(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
