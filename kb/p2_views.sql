-- kb/p2_views.sql — P2 query views (docs/GRAPHRAG_BUILD_PLAN.md §3, views L199-210).
-- Idempotent: every statement is CREATE OR REPLACE VIEW. Run against kb/state/kb.duckdb
-- after p2_series.py and p2_transactions.py have exited 0. No LLM; pure relational projection.
-- Usage: duckdb.kb_state: python -c "import duckdb; duckdb.connect('kb/state/kb.duckdb').execute(open('kb/p2_views.sql').read())"

-- ---------------------------------------------------------------------------
-- v_rate — numeric rate/price observations (Layer A), joined to doc publisher.
-- route = the entity signature decoded from the series definition; publisher resolved
-- through observation.doc_id -> document.publisher_id, falling back to series.definition.source.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_rate AS
SELECT
    COALESCE(NULLIF(regexp_replace(COALESCE(s.definition->>'entity_signature',''), '\x1f', ' / ', 'g'), ''), s.name) AS route,
    o.period_from,
    o.period_to,
    o.value,
    o.unit,
    COALESCE(d.publisher_id, s.definition->>'source') AS publisher,
    o.doc_id,
    o.obs_id
FROM observation o
LEFT JOIN series s           ON s.series_id = o.series_id
LEFT JOIN document d         ON d.doc_id    = o.doc_id;

-- ---------------------------------------------------------------------------
-- v_series — generic: every series with unit/currency/basis/frequency/source.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_series AS
SELECT
    s.series_id,
    s.name,
    s.unit,
    s.currency,
    s.basis,
    s.frequency,
    s.source_csv,
    COALESCE(s.definition->>'source', s.source_csv) AS source,
    s.definition,
    (SELECT count(*) FROM observation o WHERE o.series_id = s.series_id) AS observation_count,
    (SELECT min(o.period_from) FROM observation o WHERE o.series_id = s.series_id) AS first_period,
    (SELECT max(o.period_to)  FROM observation o WHERE o.series_id = s.series_id) AS last_period
FROM series s;

-- ---------------------------------------------------------------------------
-- v_tc_assessment — time-charter assessment rows (TC TCE/day figures).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_tc_assessment AS
SELECT
    s.series_id,
    s.name,
    o.period_from,
    o.period_to,
    o.value,
    COALESCE(o.unit, s.unit) AS unit,
    COALESCE(d.publisher_id, s.definition->>'source') AS publisher,
    o.doc_id,
    o.obs_id
FROM observation o
LEFT JOIN series s   ON s.series_id = o.series_id
LEFT JOIN document d ON d.doc_id    = o.doc_id
WHERE (s.name ILIKE '%tce%' OR s.name ILIKE '%tc_%' OR s.name ILIKE '%time.charter%'
       OR lower(COALESCE(s.definition->>'measurement','')) LIKE '%tc%');

-- ---------------------------------------------------------------------------
-- v_fixture — one row per charter/fixture transaction (+ mention count).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_fixture AS
SELECT
    t.txn_id,
    t.vessel_id,
    t.counterparties,
    t.date_from,
    t.date_to,
    json_extract(t.terms, '$.price')         AS price,
    json_extract_string(t.terms, '$.price_unit') AS price_unit,
    json_extract_string(t.terms, '$.vessel.name') AS vessel_name,
    t.status,
    count(m.txn_id) AS mention_count
FROM transaction t
LEFT JOIN mention m ON m.txn_id = t.txn_id
WHERE t.kind = 'fixture'
GROUP BY t.txn_id, t.vessel_id, t.counterparties, t.date_from, t.date_to, t.terms, t.status;

-- ---------------------------------------------------------------------------
-- v_sale — one row per sale transaction (+ mention count).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_sale AS
SELECT
    t.txn_id,
    t.vessel_id,
    t.counterparties,
    t.date_from,
    t.date_to,
    json_extract(t.terms, '$.price')         AS price,
    json_extract_string(t.terms, '$.price_unit') AS price_unit,
    json_extract_string(t.terms, '$.vessel.name') AS vessel_name,
    t.status,
    count(m.txn_id) AS mention_count
FROM transaction t
LEFT JOIN mention m ON m.txn_id = t.txn_id
WHERE t.kind = 'sale'
GROUP BY t.txn_id, t.vessel_id, t.counterparties, t.date_from, t.date_to, t.terms, t.status;

-- ---------------------------------------------------------------------------
-- v_demolition — one row per demolition transaction (+ mention count).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_demolition AS
SELECT
    t.txn_id,
    t.vessel_id,
    t.counterparties,
    t.date_from,
    t.date_to,
    json_extract(t.terms, '$.price')         AS price,
    json_extract_string(t.terms, '$.price_unit') AS price_unit,
    json_extract_string(t.terms, '$.vessel.name') AS vessel_name,
    t.status,
    count(m.txn_id) AS mention_count
FROM transaction t
LEFT JOIN mention m ON m.txn_id = t.txn_id
WHERE t.kind = 'demolition'
GROUP BY t.txn_id, t.vessel_id, t.counterparties, t.date_from, t.date_to, t.terms, t.status;

-- ---------------------------------------------------------------------------
-- v_newbuilding — one row per newbuild order transaction (+ mention count).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_newbuilding AS
SELECT
    t.txn_id,
    t.vessel_id,
    t.counterparties,
    t.date_from,
    t.date_to,
    json_extract(t.terms, '$.price')         AS price,
    json_extract_string(t.terms, '$.price_unit') AS price_unit,
    json_extract_string(t.terms, '$.vessel.name') AS vessel_name,
    t.status,
    count(m.txn_id) AS mention_count
FROM transaction t
LEFT JOIN mention m ON m.txn_id = t.txn_id
WHERE t.kind = 'newbuild_order'
GROUP BY t.txn_id, t.vessel_id, t.counterparties, t.date_from, t.date_to, t.terms, t.status;

-- ---------------------------------------------------------------------------
-- v_company_fin — SEC XBRL company fundamentals.
-- Source rows: observation.series_id = 'sec:<TICKER>:<concept>', provenance='xbrl'.
-- concept + accn stored in the series definition (populated by the SEC loader).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_company_fin AS
SELECT
    regexp_extract(o.series_id, '^sec:([^:]+):', 1)                            AS ticker,
    o.period_from                                                              AS fiscal_period,
    regexp_extract(o.series_id, ':([^:]+)$', 1)                                AS concept,
    o.value,
    o.unit,
    COALESCE(s.definition->>'form', o.method)                                  AS form,
    COALESCE(s.definition->>'accn', o.method)                                  AS accn,
    o.doc_id,
    o.obs_id
FROM observation o
LEFT JOIN series s ON s.series_id = o.series_id
WHERE o.series_id LIKE 'sec:%' AND o.provenance = 'xbrl';

-- ---------------------------------------------------------------------------
-- v_commodity_flow — commodity-related rate/tonnage observations.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_commodity_flow AS
SELECT
    s.series_id,
    s.name,
    o.period_from,
    o.period_to,
    o.value,
    COALESCE(o.unit, s.unit) AS unit,
    o.doc_id,
    o.obs_id
FROM observation o
LEFT JOIN series s ON s.series_id = o.series_id
WHERE (s.name ILIKE '%iron_ore%' OR s.name ILIKE '%coal%' OR s.name ILIKE '%grain%'
       OR s.name ILIKE '%commodit%' OR s.name ILIKE '%flow%'
       OR s.name ILIKE '%c3%' OR s.name ILIKE '%c5%')
  AND lower(COALESCE(s.definition->>'source','')) <> 'baltic';

-- ---------------------------------------------------------------------------
-- v_gaps — known corpus gaps (both seeded §4.6 and any computed later).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_gaps AS
SELECT scope, key, gap_from, gap_to, reason, source
FROM corpus_known_gaps;
