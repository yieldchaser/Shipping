import json
import requests

ENDPOINT = "https://pbrokerapp.hasura.app/v1/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://fearnpulse.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FearnpulseProbe/1.0",
}

query = """
query InspectTypes {
  snp: __type(name: "snp_transaction") {
    fields { name }
  }
  rate: __type(name: "rate") {
    fields { name }
  }
  rate_meta: __type(name: "rate_meta") {
    fields { name }
  }
  report: __type(name: "report") {
    fields { name }
  }
}
"""

r = requests.post(ENDPOINT, json={"query": query}, headers=HEADERS, timeout=10)
data = r.json().get("data", {})

for k, v in data.items():
    fields = [f["name"] for f in v["fields"]]
    print(f"\n=== TABLE: {k} ({len(fields)} fields) ===")
    print(", ".join(fields))
