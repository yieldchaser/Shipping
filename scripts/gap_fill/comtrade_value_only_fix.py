"""
Drop-in replacement for the row-builder in fetch_minor_bulks.py / fetch_un_comtrade_bauxite.py.

Finding (2026-09-17): the "missing" minor-bulk months were NOT HTTP 429 drops.
UN Comtrade returns those months with primaryValue populated but netWgt/qty = null or 0
(e.g. India HS3102 2025-09: $883.6M, qty 0). The old code dropped them silently.

Also: India's Comtrade reporter code is 699 (not 356); the preview API accepts ONE period
per call; China HS2818 ends Dec-2024, China<-Guinea HS260600 ends Mar-2025,
Philippines HS2604 ends Sep-2025, Türkiye HS2523/7204 end Dec-2025 on Comtrade.
"""
import json, time, urllib.request

API = ("https://comtradeapi.un.org/public/v1/preview/C/M/HS?reporterCode={rep}&partnerCode={partner}"
       "&cmdCode={hs}&flowCode={flow}&period={period}")


def fetch_month(rep, hs, flow, period, partner=0, retries=4):
    url = API.format(rep=rep, partner=partner, hs=hs, flow=flow, period=period)
    for a in range(retries):
        try:
            d = json.load(urllib.request.urlopen(url, timeout=40))
            break
        except Exception:
            time.sleep(6 * (a + 1))
    else:
        return dict(period=period, status="fetch_failed", url=url)
    rows = [r for r in d.get("data", []) if r.get("motCode") in (0, None)
            and r.get("customsCode") in ("C00", None) and r.get("partner2Code") in (0, None)] or d.get("data", [])
    if not rows:
        return dict(period=period, status="not_reported", url=url)
    r = rows[0]
    kg = r.get("netWgt") or r.get("qty") or 0
    value = r.get("primaryValue")
    if kg and kg > 0:
        return dict(period=period, status="ok", metric_tonnes=kg / 1000, value_usd=value, url=url)
    # value-only month: keep it, flag it, let the builder decide whether to estimate
    return dict(period=period, status="value_only", metric_tonnes=None, value_usd=value, url=url)


def estimate_tonnes(value_usd, neighbour_unit_values):
    """value / mean unit value of up to 2 months either side. Always write estimate_flag=True."""
    uv = [u for u in neighbour_unit_values if u and u > 0]
    return (value_usd / (sum(uv) / len(uv))) if (value_usd and uv) else None
