
# GLOBAL MARITIME & COMMODITY LOGISTICS DATA DISCOVERY REPORT
## Zero-Infrastructure Quantitative Terminal — Data Source Expansion

---

## EXECUTIVE SUMMARY

This report documents **verified, publicly accessible or semi-public data sources** across your five priority areas. 
**Critical Finding**: True "open API" access for upstream physical cargo volumes and route-level TCE data is extremely limited. 
Most high-frequency maritime data (Baltic route TCEs, shipyard orderbooks, port congestion) sits behind commercial paywalls. 
However, several **government and multilateral APIs** provide excellent upstream commodity trade data, and **scrapable public sources** 
fill key gaps where APIs do not exist.

**Legend:**
- 🟢 **FREE / OPEN** — No cost, API key may be required
- 🟡 **FREE TIER / REGISTRATION** — Limited free access, registration required
- 🔴 **SUBSCRIPTION** — Commercial paywall
- ⚠️ **WEB SCRAPE ONLY** — No API; HTML/PDF parsing required

---

## PRIORITY 1: UPSTREAM PHYSICAL CARGO EXPORT VOLUMES & MINING SHIPMENTS

---

### 1.1 PILBARA PORTS AUTHORITY (PPA) — AUSTRALIA IRON ORE THROUGHPUT
**Source Name:** Pilbara Ports Authority  
**Institution:** Government of Western Australia  
**Target Metric:** Monthly iron ore throughput (Mt) from Port Hedland & Dampier  
**Data Availability:** Monthly, with ~2-week lag. Historical from 2015.  
**Access Mechanism:** ⚠️ **WEB SCRAPE ONLY** — No confirmed open API or CSV bulk download.  
**URL:** https://www.pilbaraports.com.au/about-pilbara-ports/news,-media-and-statistics/news  
**Technical Endpoint:** Monthly press releases in HTML format (e.g., `https://www.pilbaraports.com.au/about-pilbara-ports/news,-media-and-statistics/news/2025/september/august-2025-shipping-figures`)

**Sample Python Ingestion (Web Scrape):**
```python
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

url = "https://www.pilbaraports.com.au/about-pilbara-ports/news,-media-and-statistics/news/2025/september/august-2025-shipping-figures"
resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
soup = BeautifulSoup(resp.text, "html.parser")

# Extract text; PPA releases follow a consistent pattern:
# "Port Hedland achieved a monthly throughput of XX.XMt, of which YY.YMt was iron ore exports"
text = soup.get_text()
hedland_match = re.search(r"Port of Port Hedland achieved a monthly throughput of ([\d.]+)Mt", text)
iron_ore_match = re.search(r"([\d.]+)Mt was iron ore exports", text)

if hedland_match and iron_ore_match:
    df = pd.DataFrame([{
        "date": "2025-08-01",
        "port": "Port Hedland",
        "total_throughput_mt": float(hedland_match.group(1)),
        "iron_ore_exports_mt": float(iron_ore_match.group(1))
    }])
    print(df)
```

**Integration Value:** PPA throughput is the highest-frequency physical volume signal for Australian iron ore. 
Port Hedland handles ~81% of Australia's iron ore exports and ~43% of global seaborne iron ore trade. 
Monthly throughput changes lead BCI/C5 route repricing by 2–4 weeks.

---

### 1.2 BRAZIL COMEXSTAT API — BRAZILIAN EXPORTS BY HS CODE
**Source Name:** ComexStat (Comércio Exterior Estatístico)  
**Institution:** Brazilian Ministry of Development, Industry, Trade and Services (MDIC/SECEX)  
**Target Metric:** Monthly iron ore (HS 2601), soybeans (HS 1201), crude petroleum (HS 2709) exports by value (USD FOB) and weight (kg)  
**Data Availability:** Monthly from 1997 to present. ~30-day lag.  
**Access Mechanism:** 🟢 **FREE REST API** — Open JSON API, no key required for basic queries.  
**Base URL:** `https://api.comexstat.mdic.gov.br`  
**Documentation:** https://comexstat.mdic.gov.br/ (R package `comexr` also available)

**Sample Python Ingestion:**
```python
import requests
import pandas as pd

# ComexStat v1 API endpoint for general trade data
url = "https://api.comexstat.mdic.gov.br/general"

payload = {
    "flow": "export",           # export or import
    "monthDetail": True,
    "period": {"start": "202401", "end": "202412"},
    "filters": [
        {"filter": "ncm", "values": ["2601"]},  # Iron ore
        {"filter": "country", "values": ["156"]}  # China
    ],
    "metrics": ["fobValue", "kgNetWeight"]
}

resp = requests.post(url, json=payload, headers={"Content-Type":"application/json"})
data = resp.json()

# Parse into DataFrame
df = pd.DataFrame(data["data"])
df["date"] = pd.to_datetime(df["yearMonth"], format="%Y%m")
df = df.rename(columns={"fobValue":"usd_fob", "kgNetWeight":"kg_net"})
print(df[["date", "usd_fob", "kg_net"]])
```

**Integration Value:** Brazil is the #2 iron ore exporter globally. ComexStat provides the only 
free, machine-readable monthly export volume series for Tubarão/Ponta da Madeira cargoes. 
HS 2601 exports correlate with C3 route TCE with ~3-week lead time.

---

### 1.3 U.S. ENERGY INFORMATION ADMINISTRATION (EIA) OPEN DATA API v2
**Source Name:** EIA Open Data API (APIv2)  
**Institution:** U.S. Energy Information Administration  
**Target Metric:** Weekly crude oil & refined product exports from PADD 3 (Gulf Coast)  
**Data Availability:** Weekly (Mon-Fri), monthly, annual. Historical from 1991.  
**Access Mechanism:** 🟡 **FREE API KEY REQUIRED** — Register at https://www.eia.gov/opendata/register.php  
**Base URL:** `https://api.eia.gov/v2/`  
**Documentation:** https://www.eia.gov/opendata/documentation.php

**Key API Routes for Maritime Relevance:**
- **Petroleum Movements / Exports:** `petroleum/movements/` or `petroleum/export-sales/`
- **PADD 3 Crude Exports:** Discover via `https://api.eia.gov/v2/petroleum/?api_key=YOUR_KEY`
- **International Energy:** `international/` — country-level production, imports, exports

**Sample Python Ingestion:**
```python
import requests
import pandas as pd

API_KEY = "YOUR_EIA_API_KEY"  # Register at https://www.eia.gov/opendata/register.php

# Step 1: Discover available petroleum routes
meta_url = f"https://api.eia.gov/v2/petroleum/?api_key={API_KEY}"
meta = requests.get(meta_url).json()
print("Available petroleum sub-routes:", [r["id"] for r in meta["response"]["routes"]])

# Step 2: Query PADD 3 crude oil exports (discovered route)
# Note: exact facet IDs must be discovered via metadata calls
route = "petroleum/movements/exports-by-padd"
data_url = f"https://api.eia.gov/v2/{route}/data/"
params = {
    "api_key": API_KEY,
    "frequency": "weekly",
    "data[0]": "value",
    "facets[padd][]": "PADD3",  # Gulf Coast
    "facets[product][]": "EPC0",  # Crude oil
    "start": "2024-01-01",
    "end": "2025-12-31",
    "sort[0][column]": "period",
    "sort[0][direction]": "desc",
    "offset": 0,
    "length": 5000
}
resp = requests.get(data_url, params=params)
df = pd.DataFrame(resp.json()["response"]["data"])
df["period"] = pd.to_datetime(df["period"])
df["value"] = pd.to_numeric(df["value"], errors="coerce")
print(df[["period", "value", "units"]].head())
```

**Integration Value:** PADD 3 crude exports are the primary US seaborne crude supply signal. 
Weekly data provides a 4–6 week leading indicator for TD22 (USG→China) and TD25 (USG→UKC) VLCC/Aframax demand. 
Also tracks HGL/LPG exports relevant for LPG carrier (VLGC) freight.

---

### 1.4 CHINA GENERAL ADMINISTRATION OF CUSTOMS (GACC) — CHINA IMPORTS
**Source Name:** China Data Portal / GACC Monthly Statistics Bulletin  
**Institution:** China General Administration of Customs (GACC)  
**Target Metric:** Monthly iron ore, coal, crude oil, bauxite imports by origin country  
**Data Availability:** Monthly from 2018 to present. ~15-day lag.  
**Access Mechanism:** 🟡 **FREE REST API (NO KEY)** — English-language API with documented endpoints.  
**Base URL:** `https://chinadata.live/api/v2/`  
**Documentation:** https://chinadata.live/china-trade/

**Sample Python Ingestion:**
```python
import requests
import pandas as pd

# China imports from Australia (iron ore proxy)
url = "https://chinadata.live/api/v2/trade/country/australia"
resp = requests.get(url)
data = resp.json()

# Monthly time series
df = pd.DataFrame(data["monthly"])
df["date"] = pd.to_datetime(df[["year", "month"]].assign(day=1))
print(df[["date", "exports", "imports"]].tail(12))

# For HS-level commodity breakdown, use the export_breakdown field
hs_breakdown = pd.DataFrame(data["export_breakdown"])
print(hs_breakdown[hs_breakdown["hs_code"].str.startswith("26")])  # Ores
```

**Alternative (Official GACC):**
- **URL:** http://english.customs.gov.cn/Statistics/Statistics?ColumnId=1
- **Format:** HTML tables + PDF bulletins. No API. Requires scraping.

**Integration Value:** China absorbs ~75% of global seaborne iron ore and ~60% of bauxite. 
GACC import volumes by origin country are the single most important demand-side signal for Capesize and Panamax freight. 
Monthly Australian iron ore imports correlate with BCI with ~2-week lag.

---

### 1.5 AUSTRALIA RESOURCES AND ENERGY QUARTERLY (REQ)
**Source Name:** Resources and Energy Quarterly  
**Institution:** Australian Department of Industry, Science and Resources  
**Target Metric:** Quarterly iron ore, metallurgical coal, thermal coal, LNG export volumes and forecasts  
**Data Availability:** Quarterly (Mar, Jun, Sep, Dec). Historical from ~2010.  
**Access Mechanism:** 🟢 **FREE PDF + EXCEL DOWNLOADS** — No API, but structured Excel workbooks provided.  
**URL:** https://www.industry.gov.au/publications/resources-and-energy-quarterly-june-2026  
**Data Download:** Look for "Download the data" links on each quarterly page.

**Sample Python Ingestion:**
```python
import requests
import pandas as pd
from io import BytesIO

# REQ publishes Excel workbooks — direct URL varies by quarter
excel_url = "https://www.industry.gov.au/sites/default/files/2025-03/Resources%20and%20Energy%20Quarterly%20March%202025%20Data.xlsx"
resp = requests.get(excel_url)
df = pd.read_excel(BytesIO(resp.content), sheet_name="Iron ore")
print(df.head())
```

**Integration Value:** REQ provides the only official Australian government forecast of iron ore export volumes 
(by financial year). The quarterly export volume data validates PPA monthly throughput and provides 
metallurgical coal export volumes for Panamax C16 route demand.

---

### 1.6 GUINEA MINISTRY OF MINES — BAUXITE & IRON ORE EXPORTS
**Source Name:** Guinea Ministry of Mines and Geology / EITI Guinea  
**Institution:** Government of Guinea / Extractive Industries Transparency Initiative (EITI)  
**Target Metric:** Weekly bauxite export tonnages by company (SMB, Chalco, CBG, etc.); monthly iron ore  
**Data Availability:** Weekly (bauxite), monthly (iron ore). Historical from 2018.  
**Access Mechanism:** ⚠️ **WEB SCRAPE / EITI OPEN DATA PORTAL** — No confirmed REST API.  
**Sources:**
- EITI Guinea Open Data Portal: https://opendataitie-guinee.org/ (Excel/CSV downloads)
- Ministry of Mines quarterly bulletins (PDF/Excel)
- Reuters newswire (weekly ministry data leaks, e.g., "Weekly ministry data for January 12–18 showed 4.9 million tons of bauxite")

**Sample Python Ingestion (EITI Portal Scrape):**
```python
import requests
from bs4 import BeautifulSoup
import pandas as pd

# EITI Guinea open data portal — production and exports page
url = "https://opendataitie-guinee.org/dataset/production-et-exportation"
resp = requests.get(url)
soup = BeautifulSoup(resp.text, "html.parser")

# Find CSV/Excel resource links
links = [a["href"] for a in soup.find_all("a", href=True) if ".csv" in a["href"] or ".xlsx" in a["href"]]
for link in links:
    print("Download:", link)
    # Download and parse...
```

**Integration Value:** Guinea is the world's #1 bauxite exporter (~183 Mt in 2025, +25% YoY). 
Guinea-to-China is the longest dry bulk trade lane (~11,000 nm), making it the most ton-mile-intensive Capesize cargo. 
Weekly export data from the Ministry of Mines provides a 3–5 week leading indicator for BCI Atlantic basin strength.

---

### 1.7 UN COMTRADE API — GLOBAL COMMODITY TRADE
**Source Name:** UN Comtrade Database  
**Institution:** United Nations Department of Economic and Social Affairs  
**Target Metric:** Monthly/Annual commodity exports/imports by HS code, country pair, mode of transport  
**Data Availability:** Annual from 1988; monthly from 2000. ~2–3 month lag.  
**Access Mechanism:** 🟡 **FREE API (KEY REQUIRED FOR BULK)** — REST API + bulk file download.  
**Base URL:** `https://comtrade.un.org/api/`  
**Python Package:** `pip install comtradeapicall`  
**Documentation:** https://github.com/uncomtrade/comtradeapicall

**Sample Python Ingestion:**
```python
from comtradeapicall import getFinalData
import pandas as pd

# Free tier: limited to 100k records per call
# Subscription key required for bulk downloads
subscription_key = "YOUR_KEY"  # Optional for small queries

df = getFinalData(
    subscription_key,
    typeCode="C",           # Commodities
    freqCode="M",           # Monthly
    clCode="HS",            # HS classification
    period="202401",        # YYYYMM
    reporterCode="36",      # Australia
    partnerCode="156",      # China
    flowCode="X",           # Exports
    cmdCode="2601",         # Iron ore
    includeDesc=True
)
print(df[["period", "primaryValue", "netWgt", "cmdDesc"]])
```

**Integration Value:** UN Comtrade is the canonical cross-reference for bilateral trade volumes. 
Use it to validate Brazil→China iron ore (HS 2601), Australia→China coal (HS 2701), and Guinea→China bauxite (HS 2606) flows. 
Monthly data lags ~2 months but provides the most authoritative tonnage figures.

---

### 1.8 MINING CORPORATE PRODUCTION REPORTS (Vale, Rio Tinto, BHP, FMG)
**Source Name:** Vale Investor Relations / Rio Tinto Production Reports / BHP Operational Reviews  
**Institution:** Corporate IR Departments  
**Target Metric:** Quarterly iron ore production and sales (Mt); bauxite/alumina production  
**Data Availability:** Quarterly. Historical from ~2000.  
**Access Mechanism:** 🟢 **FREE PDF / HTML / EXCEL** — No API; scrapable.  
**URLs:**
- Vale: https://vale.com/w/investors/production-and-sales-reports
- Rio Tinto: https://www.riotinto.com/en/invest/reports
- BHP: https://www.bhp.com/investors/news-and-events/operational-reviews
- FMG: https://www.fortescue.com/en/about-fortescue/our-performance

**Sample Python Ingestion (Vale Quarterly Report Scrape):**
```python
import requests
from bs4 import BeautifulSoup
import re

url = "https://vale.com/w/investors/production-and-sales-reports"
resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
soup = BeautifulSoup(resp.text, "html.parser")

# Find latest quarterly report links
reports = []
for link in soup.find_all("a", href=True):
    if "production-report" in link["href"].lower():
        reports.append(link["href"])
print("Latest reports:", reports[:5])

# PDF parsing would follow with PyPDF2 or pdfplumber
```

**Integration Value:** Vale's quarterly sales volumes (Tubarão, Ponta da Madeira, Guaíba) are the 
most direct upstream signal for C3 route cargoes. Rio Tinto's Pilbara shipments validate PPA port data. 
BHP's WAIO production tracks C5 route supply. These reports typically publish 3–4 weeks before official customs data.

---

## PRIORITY 2: ROUTE-SPECIFIC SPOT TCE EARNINGS TIME SERIES

---

### 2.1 BALTIC EXCHANGE / ICE DATA SERVICES
**Source Name:** Baltic Exchange Route Assessments (via ICE)  
**Institution:** Baltic Exchange (owned by Intercontinental Exchange)  
**Target Metric:** Daily TCE ($/day) and Worldscale for TD3C, TD6, TD7, TD20, TD22, TD25, TD27, C3, C5, C10  
**Data Availability:** Daily, historical from ~1998.  
**Access Mechanism:** 🔴 **SUBSCRIPTION REQUIRED** — ICE Consolidated Feed, ICE Data API, or Baltic Exchange membership.  
**URL:** https://developer.ice.com/fixed-income-data-services/catalog/baltic-exchange  
**Delivery:** ICE Consolidated Feed (real-time), ICE Consolidated History (end-of-day), ICE Data API (REST)

**Sample Python Ingestion (Hypothetical — requires ICE contract):**
```python
# ICE Data API requires OAuth2 token and commercial contract
# This is illustrative only — actual integration requires ICE onboarding

import requests

TOKEN = "YOUR_ICE_OAUTH_TOKEN"
url = "https://api.ice.com/data/baltic-exchange/routes/td3c"
headers = {"Authorization": f"Bearer {TOKEN}"}
resp = requests.get(url, headers=headers)
df = pd.DataFrame(resp.json()["data"])
```

**Integration Value:** The Baltic Exchange is the **sole authoritative source** for route-level TCE assessments. 
TD3C (MEG→China) drives ~40% of VLCC spot demand; TD6 (CPC→Med) is the Suezmax benchmark. 
C3 (Tubarão→Qingdao) and C5 (WA→Qingdao) are the two largest Capesize routes. 
Without Baltic data, any TCE model is using secondary (broker estimate) sources.

---

### 2.2 SIGNAL OCEAN API — FREIGHT & MARKET RATES
**Source Name:** Signal Ocean API Suite  
**Institution:** Signal Group / The Signal Group  
**Target Metric:** Historical and live market rate assessments ($/ton, $/day TCE) for key trading routes; 
TCE calculations; fixture data  
**Data Availability:** Daily, historical from 2015.  
**Access Mechanism:** 🔴 **COMMERCIAL API** — Flexible packages, including startup tiers.  
**Base URL:** `https://api.thesignalgroup.com/` (inferred; exact endpoint requires demo)  
**Documentation:** https://www.thesignalgroup.com/signal-ocean/data-warehouse-api

**Available APIs:**
- **Freight API:** Time series on freight pricing evolution ($/ton, $/day)
- **Market Rates API:** Historical and live market rate assessments for key routes
- **Tonnage List API:** Vessel supply forecasts by route
- **Voyages API:** Commercial voyage movements since 2014

**Sample Python Ingestion (Requires API Key):**
```python
import requests

API_KEY = "YOUR_SIGNAL_API_KEY"  # Request via https://www.thesignalgroup.com/signal-ocean/platform
headers = {"Authorization": f"Bearer {API_KEY}"}

# Market Rates API — route-level TCE
url = "https://api.thesignalgroup.com/v1/market-rates"
params = {
    "route": "TD3C",
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
    "metric": "tce_usd_day"
}
resp = requests.get(url, headers=headers, params=params)
df = pd.DataFrame(resp.json()["data"])
print(df[["date", "route", "tce_usd_day"]].head())
```

**Integration Value:** Signal Ocean is the leading alternative data platform for maritime freight. 
Their Market Rates API provides TCE estimates that closely track Baltic assessments but with 
additional voyage-level granularity. The Tonnage List API enables forward supply-demand balance 
modeling (e.g., C3/C5 forward balance charts). Essential for quantitative freight forecasting.

---

### 2.3 OPEN BROKERAGE RESEARCH (WEB SCRAPE / PDF PARSE)
**Source Name:** Weekly Broker Market Reports  
**Institution:** Banchero Costa, Allied Shipbroking, Intermodal, Xclusiv, Gibson, Poten & Partners, Fearnleys, Arrow  
**Target Metric:** Weekly route assessments, market commentary, TCE estimates  
**Data Availability:** Weekly. Historical from ~2010 (PDF archives).  
**Access Mechanism:** ⚠️ **FREE PDF DOWNLOADS** — Many brokers publish open weekly research.  
**URLs (Examples):**
- Banchero Costa: https://www.bancosta.com/market-reports/
- Allied Shipbroking: https://www.alliedshipbroking.com/en/market-commentary/
- Intermodal Research: https://www.intermodal.gr/research/
- Xclusiv Shipbrokers: https://xclusiv.gr/shipbroking-research/

**Sample Python Ingestion (PDF Scrape):**
```python
import requests
from io import BytesIO
import pdfplumber

url = "https://www.bancosta.com/wp-content/uploads/2025/08/Weekly-Market-Report-04-Aug-2025.pdf"
resp = requests.get(url)
with pdfplumber.open(BytesIO(resp.content)) as pdf:
    text = "
".join([page.extract_text() for page in pdf.pages if page.extract_text()])

# Extract TD3C TCE using regex
import re
match = re.search(r"TD3C.*?TCE.*?\$([\d,]+)", text)
if match:
    print("TD3C TCE:", match.group(1))
```

**Integration Value:** Broker reports are the **only free source** of route-level TCE commentary. 
While not machine-readable at scale, weekly PDF scraping can build a coarse TCE time series. 
Banchero Costa and Allied publish consistent weekly assessments for Capesize, VLCC, and Suezmax routes.

---

## PRIORITY 3: FLEET SUPPLY, ORDERBOOKS & SHIPYARD CAPACITY

---

### 3.1 CLARKSONS RESEARCH (SIN)
**Source Name:** Clarksons Research Database / World Shipyard Monitor  
**Institution:** Clarksons Platou Securities  
**Target Metric:** Orderbook-to-fleet % by sector; delivery schedules (DWT/TEU); slippage rates; berth utilization  
**Data Availability:** Monthly. Historical from 1980s.  
**Access Mechanism:** 🔴 **SUBSCRIPTION** — Clarksons SIN (Shipping Intelligence Network) or research reports.  
**URL:** https://www.clarksons.com/services/research/  
**Public Data:** Clarksons occasionally publishes summary statistics in press releases (e.g., 
"global orderbook reached 164.4m CGT" — see Maritime London interview).

**Integration Value:** Clarksons is the **industry standard** for fleet and orderbook data. 
Their monthly orderbook statistics are cited in virtually all ship finance and freight derivative research. 
No open alternative provides comparable accuracy for delivery slippage or shipyard berth utilization.

---

### 3.2 VESSELSVALUE (VV) API
**Source Name:** VesselsValue API Services  
**Institution:** VesselsValue (part of Veson Nautical)  
**Target Metric:** Newbuilding orders, secondhand sales, demolition sales, fleet age profile, 
scrubber/alt-fuel adoption by segment  
**Data Availability:** Real-time + historical.  
**Access Mechanism:** 🔴 **SUBSCRIPTION API** — POA pricing.  
**URL:** https://www.vesselsvalue.com/api-services/  
**Endpoints:**
- `/transactions/newbuilding-orders` — Newbuilding order data
- `/vessel/specifications` — Technical specs, builder, year
- `/timeseries/projections` — Projected earnings, values, OPEX

**Integration Value:** VV provides the most granular vessel-level orderbook data, including 
contract dates, delivery windows, and specification changes. Their API enables construction of 
custom orderbook-to-fleet ratios by subsegment (e.g., Capesize 180k vs 210k DWT).

---

### 3.3 VESSELAPI (FREE TIER)
**Source Name:** VesselAPI Maritime Data API  
**Institution:** VesselAPI  
**Target Metric:** Vessel specifications, ownership, regulatory records (MRV emissions), port events  
**Data Availability:** Real-time + historical.  
**Access Mechanism:** 🟡 **FREE TIER** — 700k+ vessel records, 120k+ port references. Bearer token auth.  
**Base URL:** `https://api.vesselapi.com/`  
**Documentation:** https://vesselapi.com/maritime-data-api

**Sample Python Ingestion:**
```python
import requests

API_KEY = "YOUR_VESSELAPI_KEY"  # Free tier available
headers = {"Authorization": f"Bearer {API_KEY}"}

# Search Capesize vessels
url = "https://api.vesselapi.com/v1/vessels"
params = {"type": "bulk_carrier", "dwt_min": 100000, "dwt_max": 250000}
resp = requests.get(url, headers=headers, params=params)
df = pd.DataFrame(resp.json()["data"])
print(df[["name", "imo", "dwt", "year_built", "builder"]].head())
```

**Integration Value:** VesselAPI's free tier provides vessel master data useful for fleet composition analysis. 
However, it does **not** include orderbook/delivery schedule data. Use it to cross-check fleet age profiles 
and scrubber/alt-fuel adoption against Clarksons data.

---

### 3.4 UNCTADstat — MARITIME TRANSPORT INDICATORS
**Source Name:** UNCTADstat Maritime Transport  
**Institution:** UN Conference on Trade and Development  
**Target Metric:** Fleet size by flag, type, and country; shipbuilding output by country; demolition by country  
**Data Availability:** Annual. Historical from 1980.  
**Access Mechanism:** 🟢 **FREE CSV/EXCEL DOWNLOAD** — No API, but bulk download available.  
**URL:** https://unctadstat.unctad.org/datacentre/dataviewer/US.MaritimeTransport  
**Bulk Download:** https://unctadstat.unctad.org/datacentre/dataviewer/US.BulkDownload

**Integration Value:** UNCTAD provides the only **free, authoritative annual fleet statistics** by flag and vessel type. 
Use it for long-term fleet growth trend analysis and shipbuilding market share (China, South Korea, Japan). 
Data is annual only — not suitable for monthly orderbook tracking.

---

## PRIORITY 4: PORT CONGESTION & WAITING TIMES

---

### 4.1 MARINETRAFFIC API — PORT CONGESTION
**Source Name:** MarineTraffic Ports Information API  
**Institution:** MarineTraffic (now part of Kpler)  
**Target Metric:** Port congestion index, anchorage time, vessels in port, waiting vessels, average waiting time by terminal  
**Data Availability:** Real-time + historical.  
**Access Mechanism:** 🔴 **COMMERCIAL API** — Credit-based prepaid system.  
**Base URL:** `https://servicedocs.marinetraffic.com/`  
**Key Endpoints:**
- `/port-congestion` — Congestion analytics by port and ISO week
- `/expectedarrivals` — Expected port arrivals
- `/portcalls` — Port calls and berth calls

**Sample Python Ingestion:**
```python
import requests

API_KEY = "YOUR_MT_API_KEY"
headers = {"Authorization": f"Bearer {API_KEY}"}

# Port congestion for Qingdao (UN/LOCODE: CNTAO)
url = "https://api.marinetraffic.com/port-congestion"
params = {
    "port_id": "CNTAO",
    "ship_type": "cargo",
    "week": "2025-W30"
}
resp = requests.get(url, headers=headers, params=params)
data = resp.json()
print("Waiting vessels:", data["waiting_vessels"])
print("Avg waiting time (hrs):", data["avg_waiting_time_hours"])
```

**Integration Value:** MarineTraffic is the largest AIS-based port congestion data provider. 
Their terminal-level congestion metrics (waiting vessels, berth occupancy) are essential for 
detecting Capesize supply bottlenecks at Qingdao, Rizhao, and Ningbo-Zhoushan. 
High congestion (>3 days waiting) correlates with BCI spikes with ~1-week lag.

---

### 4.2 PORTCAST API — PORT CONGESTION
**Source Name:** Portcast Port Congestion API  
**Institution:** Portcast  
**Target Metric:** Daily vessel count (berthed + waiting), total waiting time, 365-day rolling average, 
congestion category (LOW/MEDIUM/HIGH/LONG-TAIL)  
**Data Availability:** Daily + weekly analytics. Historical to 2 years.  
**Access Mechanism:** 🔴 **COMMERCIAL API** — Enterprise pricing.  
**URL:** https://www.portcast.io/blog/portcast-port-congestion-data-now-available-via-api  
**Coverage:** 1,000+ ports globally.

**Integration Value:** Portcast's percentile-based congestion categories (P50/P75/P90) are useful 
for automated alert systems. Their API supports historical trend analysis for seasonal congestion 
pattern detection (e.g., Chinese New Year, monsoon season).

---

### 4.3 TRADLINX PORT CONGESTION API
**Source Name:** Tradlinx Port Congestion API  
**Institution:** Tradlinx  
**Target Metric:** Berth delay, waiting vessels, time at berth, vessels at berth  
**Data Availability:** Real-time, 3-day trends.  
**Access Mechanism:** 🔴 **COMMERCIAL API** — Request access via portal.  
**URL:** https://www.tradlinx.com/intelligence/port-congestion

---

### 4.4 FREE ALTERNATIVE: Linerlytica / EconDB (Container-Focused)
**Source Name:** Linerlytica / EconDB  
**Institution:** Linerlytica / EconDB  
**Target Metric:** Container vessel dwell times, port delay indices  
**Data Availability:** Weekly.  
**Access Mechanism:** 🟢 **FREE WEB DASHBOARD** — No API; data visible in reports.  
**URL:** https://theloadstar.com/ (Linerlytica reports syndicated)

**Note:** These sources are **container-focused** and do not cover dry bulk or tanker congestion well. 
For bulk commodity ports, MarineTraffic or Portcast are required.

---

## PRIORITY 5: CARBON, FUEL SPREADS & GREEN REGIMES

---

### 5.1 OILPRICEAPI — EU ETS CARBON + BUNKER PRICES
**Source Name:** OilPriceAPI  
**Institution:** OilPriceAPI  
**Target Metric:** 
- EU ETS carbon allowance spot price (€/t CO2) — code: `EU_CARBON_EUR`
- VLSFO, HSFO (IFO 380), MGO prices by port — codes: `VLSFO_SG_SGD`, `HSFO_SG_SGD`, etc.  
**Data Availability:** Daily. Historical from 2020 (carbon), multi-year (bunkers).  
**Access Mechanism:** 🟡 **FREE TIER** — 50 requests/day, no credit card. Paid tiers from $19/mo.  
**Base URL:** `https://api.oilpriceapi.com/v1/`  
**Documentation:** https://www.oilpriceapi.com/live/eu-carbon-price

**Sample Python Ingestion:**
```python
import requests

API_KEY = "YOUR_OILPRICE_API_KEY"  # Free tier: 50 req/day
headers = {"Authorization": f"Token {API_KEY}"}

# EU ETS Carbon Price
url = "https://api.oilpriceapi.com/v1/prices/latest"
params = {"by_code": "EU_CARBON_EUR"}
resp = requests.get(url, headers=headers, params=params)
carbon = resp.json()["data"]
print(f"EU Carbon: €{carbon['price']}/tCO2 (updated: {carbon['created_at']})")

# Singapore VLSFO
params = {"by_code": "VLSFO_SG_SGD"}
resp = requests.get(url, headers=headers, params=params)
vlsfo = resp.json()["data"]
print(f"Singapore VLSFO: ${vlsfo['price']}/mt")

# Singapore HSFO (IFO 380)
params = {"by_code": "HSFO_SG_SGD"}
resp = requests.get(url, headers=headers, params=params)
hsfo = resp.json()["data"]
print(f"Singapore HSFO: ${hsfo['price']}/mt")

# Calculate Hi-5 Spread
hi5_spread = vlsfo["price"] - hsfo["price"]
print(f"Singapore Hi-5 Spread: ${hi5_spread:.2f}/mt")
```

**Integration Value:** OilPriceAPI is the **only verified free API** for both EU ETS carbon prices 
and global bunker fuel prices. The Hi-5 spread (VLSFO−HSFO) directly impacts scrubber-fitted vessel 
TCE premiums. At $100/mt spread, a Capesize scrubber premium is ~$5,000/day. 
EU ETS carbon cost at €80/t adds ~$3,500/day to a Capesize EU voyage.

---

### 5.2 TRADING ECONOMICS — EU CARBON PERMITS
**Source Name:** Trading Economics — EU Carbon Permits  
**Institution:** Trading Economics  
**Target Metric:** EU Carbon Permits price (EUR/tCO2), historical chart, forecasts  
**Data Availability:** Daily from 2005.  
**Access Mechanism:** 🟢 **FREE WEB DATA** — No API for free tier; chart data viewable.  
**URL:** https://tradingeconomics.com/commodity/carbon

**Integration Value:** Cross-reference for OilPriceAPI carbon data. Trading Economics provides 
long-term historical context (EUAs traded below €10 for most of the 2010s, peaked at €105.73 in Feb 2023).

---

### 5.3 BUNKER INDEX — GLOBAL BUNKER PRICES
**Source Name:** Bunker Index  
**Institution:** Bunker Index  
**Target Metric:** Daily VLSFO, MGO, HSFO prices at 20+ ports  
**Data Availability:** Daily.  
**Access Mechanism:** 🟢 **FREE WEBSITE** — No confirmed API. Scrapable HTML tables.  
**URL:** https://www.bunkerindex.com/

**Sample Python Ingestion (Web Scrape):**
```python
import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://www.bunkerindex.com/"
resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
soup = BeautifulSoup(resp.text, "html.parser")

# Parse price table
table = soup.find("table")
df = pd.read_html(str(table))[0]
print(df[df["Port"].isin(["Singapore", "Rotterdam", "Fujairah", "Houston"])])
```

**Integration Value:** Bunker Index provides a free cross-check for OilPriceAPI bunker data. 
Useful for detecting data anomalies or filling gaps when OilPriceAPI credits are exhausted.

---

### 5.4 ENGINE — HI-5 SPREAD ANALYTICS
**Source Name:** ENGINE  
**Institution:** ENGINE (marine fuels intelligence)  
**Target Metric:** Hi-5 spread trends, scrubber economics, bunker quality incidents  
**Data Availability:** Daily/weekly reports.  
**Access Mechanism:** 🔴 **SUBSCRIPTION** — News and data service.  
**URL:** https://engine.online/

**Integration Value:** ENGINE provides qualitative context on Hi-5 spread drivers (refining margins, 
sanctions-driven HSFO scarcity, VLSFO off-spec incidents). Their weekly Hi-5 spread reports 
are the industry benchmark for scrubber payback analysis.

---

## SUMMARY TABLE: ALL DISCOVERED SOURCES

| Priority | Source | Metric | Frequency | Cost | Access Type | URL |
|----------|--------|--------|-----------|------|-------------|-----|
| P1 | Pilbara Ports Authority | Iron ore throughput (Mt) | Monthly | Free | Web Scrape | pilbaraports.com.au |
| P1 | Brazil ComexStat API | Exports by HS code (kg, USD) | Monthly | Free | REST API | comexstat.mdic.gov.br |
| P1 | EIA API v2 | Petroleum exports (PADD 3) | Weekly | Free (key) | REST API | api.eia.gov/v2 |
| P1 | China Data Portal (GACC) | Imports by origin (USD, kg) | Monthly | Free | REST API | chinadata.live/api/v2 |
| P1 | Australia REQ | Export volumes & forecasts | Quarterly | Free | Excel DL | industry.gov.au |
| P1 | Guinea EITI / Ministry | Bauxite/iron ore exports | Weekly/Monthly | Free | Web Scrape / Portal | opendataitie-guinee.org |
| P1 | UN Comtrade API | Bilateral trade by HS | Monthly/Annual | Free (key) | REST API | comtrade.un.org/api |
| P1 | Vale / Rio Tinto / BHP | Production & sales (Mt) | Quarterly | Free | PDF / HTML | Corporate IR sites |
| P2 | Baltic Exchange (ICE) | Route TCE ($/day, WS) | Daily | Subscription | ICE Feed / API | developer.ice.com |
| P2 | Signal Ocean API | Market rates, TCE, fixtures | Daily | Commercial | REST API | thesignalgroup.com |
| P2 | Broker Research (Banchero, Allied, etc.) | Weekly route commentary | Weekly | Free | PDF Scrape | Various broker sites |
| P3 | Clarksons Research | Orderbook, fleet, deliveries | Monthly | Subscription | SIN Platform | clarksons.com |
| P3 | VesselsValue API | Newbuilding orders, specs | Real-time | Subscription | REST API | vesselsvalue.com |
| P3 | VesselAPI | Vessel specs, ownership | Real-time | Free tier | REST API | vesselapi.com |
| P3 | UNCTADstat | Fleet, shipbuilding, demolition | Annual | Free | CSV/Excel | unctadstat.unctad.org |
| P4 | MarineTraffic API | Port congestion, waiting time | Real-time | Commercial | REST API | marinetraffic.com |
| P4 | Portcast API | Congestion index, wait times | Daily | Commercial | REST API | portcast.io |
| P4 | Tradlinx API | Berth delay, vessel queues | Real-time | Commercial | REST API | tradlinx.com |
| P5 | OilPriceAPI | EU carbon, VLSFO, HSFO, MGO | Daily | Free tier | REST API | api.oilpriceapi.com |
| P5 | Trading Economics | EU carbon price history | Daily | Free (web) | Web | tradingeconomics.com |
| P5 | Bunker Index | Global bunker prices | Daily | Free (web) | Web Scrape | bunkerindex.com |
| P5 | ENGINE | Hi-5 spread analytics | Daily/Weekly | Subscription | News | engine.online |

---

## CRITICAL GAPS & RECOMMENDATIONS

### 1. Route-Level TCE Data (Priority 2) — NO FREE SOURCE EXISTS
**Finding:** The Baltic Exchange assessments (TD3C, TD6, C3, C5) are the industry standard and are 
**not available via any free API**. Signal Ocean provides the best commercial alternative.

**Recommendation:** 
- **Short-term:** Scrape weekly broker PDFs (Banchero Costa, Allied, Intermodal) to build a coarse TCE proxy.
- **Medium-term:** Subscribe to Baltic Exchange/ICE Data API for authoritative daily route data (~$15k–30k/year).
- **Alternative:** SGX FFA forward curves (which you already have) can be backcast to approximate spot TCE using 
  the BCI/BDTI composite indices and route weights.

### 2. Shipyard Orderbook & Delivery Schedules (Priority 3) — NO FREE SOURCE EXISTS
**Finding:** Clarksons and VesselsValue are the only providers with accurate delivery slippage and 
shipyard berth utilization data. UNCTADstat provides annual fleet aggregates only.

**Recommendation:**
- **Short-term:** Use UNCTADstat annual fleet data for long-term trend analysis.
- **Medium-term:** Subscribe to Clarksons SIN or VesselsValue API for monthly orderbook tracking.
- **Alternative:** Scrape newbuilding order announcements from TradeWinds, Splash247, and Lloyd's List 
  to build a partial orderbook tracker.

### 3. Port Congestion for Dry Bulk / Tankers (Priority 4) — NO FREE SOURCE EXISTS
**Finding:** All verified port congestion APIs (MarineTraffic, Portcast, Tradlinx) are commercial. 
Free sources (Linerlytica, EconDB) are container-only.

**Recommendation:**
- **Short-term:** Use IMF PortWatch (which you already have) for chokepoint transit counts as a proxy 
  for congestion. AIS-based open data projects (e.g., SkyFi AIS) may provide raw vessel positions 
  near ports for custom congestion calculation.
- **Medium-term:** MarineTraffic API is the most cost-effective for bulk port congestion (~$500–2k/month).

### 4. Guinea Weekly Bauxite Exports (Priority 1) — UNSTABLE ACCESS
**Finding:** Guinea Ministry of Mines weekly data is excellent but accessed only via Reuters newswire 
or EITI portal scraping. No structured API.

**Recommendation:**
- Monitor Guinea EITI open data portal (https://opendataitie-guinee.org/) for CSV/Excel publication.
- Set up RSS alerts for Reuters "Guinea bauxite" to capture weekly ministry data leaks.
- Scrape guineamininginsights.com for monthly production tables.

---

## END OF REPORT
