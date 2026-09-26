import json
import requests

ENDPOINT = "https://pbrokerapp.hasura.app/v1/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://fearnpulse.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FearnpulseProbe/1.0",
}

# Date: 2026-09-09 (Week 37, matching the PDF we just read)
test_date = "2026-09-09"

q = f"""
query {{
  suezmax_nb: rate(where: {{meta: {{route_info_id: {{_eq: 151}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  aframax_nb: rate(where: {{meta: {{route_info_id: {{_eq: 18}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  product_nb: rate(where: {{meta: {{route_info_id: {{_eq: 135}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  newcastle_nb: rate(where: {{meta: {{route_info_id: {{_eq: 120}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  kamsarmax_nb: rate(where: {{meta: {{route_info_id: {{_eq: 90}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  ultramax_nb: rate(where: {{meta: {{route_info_id: {{_eq: 167}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  lng_nb: rate(where: {{meta: {{route_info_id: {{_eq: 97}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  
  cape_5y: rate(where: {{meta: {{route_info_id: {{_eq: 278}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  cape_10y: rate(where: {{meta: {{route_info_id: {{_eq: 268}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  suez_5y: rate(where: {{meta: {{route_info_id: {{_eq: 153}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  suez_10y: rate(where: {{meta: {{route_info_id: {{_eq: 152}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  afra_5y: rate(where: {{meta: {{route_info_id: {{_eq: 21}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
  afra_10y: rate(where: {{meta: {{route_info_id: {{_eq: 20}}}}, date: {{_eq: "{test_date}"}}}}) {{ rate }}
}}
"""

r = requests.post(ENDPOINT, json={"query": q}, headers=HEADERS).json()
print("=== HASURA RATES VS PDF VALUES (WEEK 37 / 2026-09-09) ===")
for k, v in r.get("data", {}).items():
    rates = v[0]["rate"] if v else None
    print(f"  {k:15}: ${rates}M")
