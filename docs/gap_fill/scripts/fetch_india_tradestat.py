#!/usr/bin/env python3
"""
India monthly imports by HS code from the Dept of Commerce TradeStat portal (DGCI&S data).
Replaces UN Comtrade for the 'Urea / Fertiliser (India, HS 3102)' series: Comtrade has
value-only months; TradeStat has quantity (kg) for all of them.
Validated 2026-09-17: equals repo rows Apr-25, Jun-25, Jul-25, Apr-26, Jun-26.

Form quirks: in 'specific' mode the HS code field is `comval` and the commodity-level
select must NOT be sent (it is disabled). Quantity table has a UNIT column, the USD table
does not, so the current-month column is index 5 (qty) vs 4 (USD mn).
Latest month is flagged (F) = provisional.
"""
import html, http.cookiejar, re, sys, time, urllib.parse, urllib.request

URL = "https://tradestat.commerce.gov.in/meidb/commoditywise_import"


def _opener():
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]
    return op


def query(op, month, year, report_val, hs):
    page = op.open(URL, timeout=60).read().decode()
    token = re.search(r'name="_token" value="([^"]+)"', page)[1]
    data = dict(_token=token, imddMonth=str(month), imddYear=str(year), comlev="specific",
                comval=hs, imddReportVal=str(report_val), imddReportYear="2")
    body = op.open(urllib.request.Request(URL, data=urllib.parse.urlencode(data).encode(),
                                          headers={"Referer": URL}), timeout=120).read().decode()
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        cells = [html.unescape(re.sub("<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(cells) > 5 and cells[1] == hs:
            return cells
    return None


def month_row(year, month, hs="3102"):
    op = _opener()
    q = query(op, month, year, 2, hs); time.sleep(1)
    v = query(op, month, year, 1, hs)
    if not q or not v:
        return None
    kg = float(q[5].replace(",", ""))
    usd = float(v[4].replace(",", "")) * 1e6
    return dict(date=f"{year}-{month:02d}-01", metric_tonnes=round(kg / 1000, 2), value_usd=round(usd))


if __name__ == "__main__":
    y, m = int(sys.argv[1]), int(sys.argv[2])
    print(month_row(y, m))
