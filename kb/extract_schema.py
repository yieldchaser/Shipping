"""Layer C contract: closed ontology, static prompt, tool schema and pydantic models (plan §7.1-7.3).

One module so that the bake-off (P4b) and bulk extraction (P4c) send a byte-identical
`STATIC_PROMPT` with an identical tool definition: plan §7.2 demands the same prompt for every
candidate, and the ledger keys calls by `prompt_version` so a prompt edit invalidates the cache.

Nothing here calls a model. Pure data + pure functions, unit-tested in `kb/tests/test_p4b.py`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

PROMPT_VERSION = "extraction-v2"

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "data/reference/baltic_route_taxonomy.json"

# --- closed enums (plan §6.1) -------------------------------------------------------------
EDGE_TYPES = {
    "OWNS": [],
    "MANAGES": [],
    "OPERATES": [],
    "TIME_CHARTERED_TO": ["rate_usd_day", "period_months", "delivery", "redelivery"],
    "SOLD_TO": ["price", "date", "en_bloc"],
    "BUILT_BY": ["delivered"],
    "ORDERED_AT": ["price", "delivery", "units"],
    "DEMOLISHED_AT": ["country", "ldt", "price_usd_ldt"],
    "RENAMED": ["from", "to"],
    "FLAG": [],
    "SUBSIDIARY_OF": [],
    "LISTED_AS": ["exchange", "ticker"],
    "FINANCED_BY": ["lender", "amount", "type"],
    "FIXED": ["cargo", "qty", "load", "disch", "laycan", "rate"],
}
EVENT_TYPES = [
    "market_move", "port_congestion", "canal_disruption", "weather", "strike_labour",
    "sanction_policy", "regulation", "trade_policy", "production_guidance", "company_guidance",
    "accident_casualty", "newbuilding_wave", "demolition_wave", "other",
]
CLAIM_KINDS = ["forecast", "view", "causal"]
DIRECTIONS = ["up", "down", "flat", "mixed", "na"]
ENTITY_TYPES = ["vessel", "company", "port", "route", "index", "commodity", "country", "publisher", "person"]
COMPANY_ROLES = ["owner", "operator", "manager", "charterer", "shipyard", "broker", "miner", "trader", "bank", "lessor"]


def baltic_routes() -> list[tuple[str, str]]:
    """(code, description) for the 109 official Baltic routes, for the static prompt (plan §7.2)."""
    data = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    return [(r["code"], r["description"]) for _, r in sorted(data["routes"].items())]


def route_block() -> str:
    return "\n".join(f"{code} {desc}" for code, desc in baltic_routes())


EDGE_LIST = "\n".join(
    f"- {t}" + (f" attrs: {', '.join(a)}" if a else "") for t, a in EDGE_TYPES.items()
)

# --- pydantic output models (plan §7.3) ----------------------------------------------------
PrintedAttr = dict


class Attr(BaseModel):
    key: str
    value_as_printed: str


class StateFact(BaseModel):
    type: Literal[tuple(EDGE_TYPES)]  # type: ignore[valid-type]
    src: str
    dst: str
    attrs_printed: list[Attr] = Field(default_factory=list)
    valid_from_printed: str = ""
    valid_to_printed: str = ""
    chunk: str
    sids: list[int] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @field_validator("attrs_printed")
    @classmethod
    def _keys_allowed(cls, v: list[Attr], info):
        # allowed attr keys depend on the edge type; unknown keys are kept (scored as schema
        # failures by the gate) so the metric sees the model's error instead of hiding it.
        return v


class EventRole(BaseModel):
    role: str
    entity: str


class Event(BaseModel):
    type: Literal[tuple(EVENT_TYPES)]  # type: ignore[valid-type]
    summary: str
    roles: list[EventRole] = Field(default_factory=list)
    when_printed: str = ""
    magnitude_printed: str = ""
    chunk: str
    sids: list[int] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class Claim(BaseModel):
    kind: Literal[tuple(CLAIM_KINDS)]  # type: ignore[valid-type]
    subjects: list[str] = Field(default_factory=list)
    direction: Literal[tuple(DIRECTIONS)]  # type: ignore[valid-type]
    horizon_printed: str = ""
    chunk: str
    sids: list[int] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class NewEntity(BaseModel):
    id: str
    type: Literal[tuple(ENTITY_TYPES)]  # type: ignore[valid-type]
    name: str
    chunk: str
    sids: list[int] = Field(min_length=1)


class Extraction(BaseModel):
    no_content: bool
    state_facts: list[StateFact] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    new_entities: list[NewEntity] = Field(default_factory=list)


# --- tool schema (plan §7.3, strict where supported) ---------------------------------------
def _attr_schema() -> dict:
    return {
        "type": "object",
        "properties": {"key": {"type": "string"}, "value_as_printed": {"type": "string"}},
        "required": ["key", "value_as_printed"],
        "additionalProperties": False,
    }


def _common(chunk_ids: list[str]) -> dict:
    return {
        "chunk": {"type": "string", "enum": chunk_ids},
        "sids": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
        "confidence": {"type": "number"},
    }


def tool_schema(chunk_ids: list[str]) -> dict:
    """JSON schema for the `record_extraction` tool / `response_format=json_schema`."""
    sids = {"type": "array", "items": {"type": "integer"}, "minItems": 1}
    return {
        "type": "object",
        "properties": {
            "no_content": {"type": "boolean"},
            "state_facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": list(EDGE_TYPES)},
                        "src": {"type": "string"},
                        "dst": {"type": "string"},
                        "attrs_printed": {"type": "array", "items": _attr_schema()},
                        "valid_from_printed": {"type": "string"},
                        "valid_to_printed": {"type": "string"},
                        **_common(chunk_ids),
                    },
                    "required": ["type", "src", "dst", "attrs_printed", "valid_from_printed",
                                 "valid_to_printed", "chunk", "sids", "confidence"],
                    "additionalProperties": False,
                },
            },
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": EVENT_TYPES},
                        "summary": {"type": "string"},
                        "roles": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"role": {"type": "string"}, "entity": {"type": "string"}},
                                "required": ["role", "entity"],
                                "additionalProperties": False,
                            },
                        },
                        "when_printed": {"type": "string"},
                        "magnitude_printed": {"type": "string"},
                        **_common(chunk_ids),
                    },
                    "required": ["type", "summary", "roles", "when_printed", "magnitude_printed",
                                 "chunk", "sids", "confidence"],
                    "additionalProperties": False,
                },
            },
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": CLAIM_KINDS},
                        "subjects": {"type": "array", "items": {"type": "string"}},
                        "direction": {"type": "string", "enum": DIRECTIONS},
                        "horizon_printed": {"type": "string"},
                        **_common(chunk_ids),
                    },
                    "required": ["kind", "subjects", "direction", "horizon_printed", "chunk", "sids", "confidence"],
                    "additionalProperties": False,
                },
            },
            "new_entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string", "enum": ENTITY_TYPES},
                        "name": {"type": "string"},
                        "chunk": {"type": "string", "enum": chunk_ids},
                        "sids": sids,
                    },
                    "required": ["id", "type", "name", "chunk", "sids"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["no_content", "state_facts", "events", "claims", "new_entities"],
        "additionalProperties": False,
    }


FUNCTION = {
    "type": "function",
    "function": {
        "name": "record_extraction",
        "description": "Record the closed-ontology facts, events and claims printed in the chunk text.",
    },
}

# --- static prompt (byte-identical for every call; plan §7.2) ------------------------------
STATIC_PROMPT = f"""You extract structured records from shipping-market documents into a closed ontology.
Return ONLY a `record_extraction` tool call. Never prose. Never invent.

RULES
1. Record only what the text explicitly prints. If the text does not state it, do not record it.
2. Every record cites the numbered sentences `[n]` it comes from in `sids`. Prefer the single sentence
   that prints the evidence; use several only when the record needs them. `chunk` is copied exactly
   from the `id` attribute of the `<chunk>` block; `sids` are the `[n]` numbers inside that block.
3. Copy numbers, dates and units EXACTLY as printed ("USD 26 M", "WS 65", "usd 60,000 pd", "Q3 2025",
   "last week"). Never compute, convert, round or rewrite them. Code parses them. An attribute key must
   come from the edge's `attrs:` list below; a value that is not printed in the cited sentences makes
   the record fail and it will be dropped.
4. Entities: every entity reference (`src`, `dst`, role `entity`, claim `subjects`) must be either an
   id copied EXACTLY from `known_entities` (`E1`, `E2`, ...) or an `N#` id declared in `new_entities`.
   Never reference a name, a ticker or a guessed id directly. If the printed name is not in
   `known_entities`, emit a `new_entities` item with a short id ("N1", "N2", ...) whose `name` is the
   printed name verbatim and whose `sids` include the sentence that prints that name; record fields
   then use that `N#`. Never assign an id to something the text does not name. Names never imply
   identity: do not merge two names into one id.
5. One record per relation/event/claim. No duplicates, no restatements of the same sentence.
6. Tables of market levels are layer A: do not transcribe index or route tables. Do record a narrative
   statement that a rate/index moved, was fixed, or is expected to move.
7. `no_content: true` only when the text carries no state fact, event or claim (e.g. a disclaimer,
   contact block, or pure arithmetic/analysis with no printed fact). Otherwise `no_content: false`.
8. Confidence is your own 0..1 belief that the record is printed and correctly typed. Use <=0.5 when
   the sentence is ambiguous.

EDGE TYPES (state facts, with printed attributes)
{EDGE_LIST}

EVENT TYPES
{", ".join(EVENT_TYPES)}

CLAIM KINDS
forecast = an expectation with a horizon; view = a market assessment; causal = "X because Y"
DIRECTIONS
{", ".join(DIRECTIONS)}

ENTITY TYPES
{", ".join(ENTITY_TYPES)}
Company roles when used in a role: {", ".join(COMPANY_ROLES)}

BALTIC ROUTE CODES (use the `route` entity type and these codes only)
{route_block()}

FEW-SHOTS
Example A. Text: "[1] The 2015-built MV Aurora (IMO 9700001, 63,000 dwt) was sold to Greek owners
Nereus Shipping for USD 18.5 M." -> one state_fact type=SOLD_TO src=E1 dst=N1
attrs_printed=[{{"key":"price","value_as_printed":"USD 18.5 M"}}] sids=[1].
Example B. Text: "[1] Nereus Shipping has the vessel on a two-year charter at USD 14,500 pd, delivery
Shanghai, redelivery worldwide." -> state_fact type=TIME_CHARTERED_TO src=E1 dst=E2
attrs_printed rate_usd_day="USD 14,500 pd", period_months="two-year", delivery="Shanghai",
redelivery="worldwide" sids=[1].
Example C. Text: "[2] The unit was renamed Sea Pearl, having previously traded as Aurora." ->
state_fact type=RENAMED src=E1 dst=E1 attrs from="Aurora" to="Sea Pearl" sids=[2].
Example D. Text: "[1] Typhoon Gaemi closed the port of Kaohsiung for three days, with some 40 vessels
waiting." -> event type=port_congestion summary="Typhoon Gaemi closed Kaohsiung for three days"
when_printed="three days" magnitude_printed="40 vessels" sids=[1].
Example E. Text: "[1] We expect Capesize rates to fall in Q3 as Brazilian volumes ease." ->
claim kind=forecast direction=down horizon_printed="Q3" sids=[1].
Example F. Text: "[1] This report is for information purposes only and does not constitute advice." ->
no_content=true.
"""


# --- entity ids: short prompt ids in, canonical ids out (plan §6.2) --------------------------
EID_RE = re.compile(r"^E\d+$")
NID_RE = re.compile(r"^N\d+$")


def known_index(known: list[dict]) -> dict[str, dict]:
    """Prompt ids `E1..En` (plan §6.2) -> the chunk's known-entity rows, in prompt order."""
    return {f"E{i + 1}": k for i, k in enumerate(known or [])}


def _name_key(text: str) -> str:
    """Loose name key: casefold, drop quoting punctuation, collapse whitespace."""
    s = re.sub(r"[\"'“”‘’`]", "", str(text or "").casefold())
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").casefold()).strip("_") or "unnamed"


def canonical_entity_id(ref: str, type_: str, name: str) -> str:
    """Deterministic id for a model-declared new entity: `type:new:slug(name)`.

    Both references and candidates get the same id for the same printed name, so the bake-off can
    match a new entity across models even though each model invents its own `N#` handles."""
    return f"{type_}:new:{_slug(name)}"


def canonicalize(ext: Extraction, known: list[dict]) -> tuple[Extraction, dict[str, str], dict[str, str]]:
    """Rewrite every entity reference to a canonical registry id.

    Accepts (in this order): a prompt id `E#`, a real registry id copied from `known_entities`, a
    known entity's printed name, or a declared `N#`/new-entity handle. Returns
    `(extraction, new_ids, new_names)` where `new_ids` is {model handle -> canonical id} and
    `new_names` is {canonical id -> printed name}. Unknown references are left untouched so the gate
    drops the record instead of the code silently guessing.
    """
    idx = known_index(known)
    real_ids = {k["id"] for k in known or []}
    by_name = {}
    for k in known or []:
        by_name.setdefault(_name_key(k.get("name")), k["id"])

    new_ids: dict[str, str] = {}
    new_names: dict[str, str] = {}
    for ne in ext.new_entities:
        cid = canonical_entity_id(ne.id, ne.type, ne.name)
        new_ids[ne.id] = cid
        new_names[cid] = ne.name

    def fix(ref: str) -> str:
        ref = (ref or "").strip()
        if not ref:
            return ref
        if EID_RE.match(ref):
            return idx[ref]["id"] if ref in idx else ref
        if ref in real_ids:
            return ref
        if ref in new_ids:
            return new_ids[ref]
        hit = by_name.get(_name_key(ref))
        if hit:
            return hit
        return ref

    facts = [f.model_copy(update={"src": fix(f.src), "dst": fix(f.dst)}) for f in ext.state_facts]
    events = []
    for e in ext.events:
        roles = [r.model_copy(update={"entity": fix(r.entity)}) for r in e.roles]
        events.append(e.model_copy(update={"roles": roles}))
    claims = [c.model_copy(update={"subjects": [fix(s) for s in c.subjects]}) for c in ext.claims]
    nes = [ne.model_copy(update={"id": new_ids[ne.id], "type": ne.type}) for ne in ext.new_entities]
    out = ext.model_copy(update={"state_facts": facts, "events": events, "claims": claims,
                                 "new_entities": nes})
    return out, new_ids, new_names


# --- user prompt ---------------------------------------------------------------------------
def sentence_table(body: str, sentences: list[tuple[int, int, int]]) -> list[tuple[int, str]]:
    """[(sid, text)] cut by code from the chunk offsets (plan §6.2 D7); sentence 0 keeps the lead."""
    out = []
    for sid, start, end in sentences:
        text = (body or "")[start:end]
        out.append((sid, text.strip()))
    return out


def user_prompt(doc: dict, chunk_blocks: list[dict], known: list[dict]) -> str:
    """Build the user turn: <doc> meta, numbered sentences per `<chunk id="C#">`, then genes."""
    head = (f'<doc publisher="{doc.get("publisher")}" doc_type="{doc.get("doc_type")}" '
            f'date="{doc.get("published_at")}" heading="{doc.get("heading", "")}">')
    parts = [head]
    for block in chunk_blocks:
        lines = "\n".join(f"[{sid}] {text}" for sid, text in block["sentences"])
        parts.append(f'<chunk id="{block["cid"]}">\n{lines}\n</chunk>')
    if known:
        idx = known_index(known)
        ent = " ".join(f'{eid}|{k["type"]}|{k["name"]}|{k.get("key", "")}'.rstrip("|")
                       for eid, k in idx.items())
        parts.append(f"<known_entities> {ent} </known_entities>")
    else:
        parts.append("<known_entities> none </known_entities>")
    parts.append("</doc>")
    return "\n".join(parts)


def chunk_ids_schema(chunk_blocks: list[dict]) -> dict:
    return tool_schema([b["cid"] for b in chunk_blocks])


def parse_extraction(raw: str) -> tuple[Extraction | None, str | None]:
    """Validate a raw tool-call argument string. Returns (model, error)."""
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"json: {exc.msg}"
    if not isinstance(doc, dict):
        return None, "json: not an object"
    # tolerate a wrapped {"arguments": {...}} or {"extraction": {...}}
    for key in ("arguments", "extraction", "record_extraction"):
        if key in doc and isinstance(doc[key], dict):
            doc = doc[key]
            break
    try:
        return Extraction.model_validate(doc), None
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first["loc"])
        return None, f"schema: {loc}: {first['msg']}"


NUMBER_RE = re.compile(r"\d[\d,\./\-]*")


def printed_numbers(text: str) -> list[str]:
    """Numbers as printed (kept for the gate-3 substring test)."""
    return NUMBER_RE.findall(text or "")
