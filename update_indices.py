import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os

# Index mapping: URL code → filename
INDEXES = {
    'BDTI': 'dirtytanker_historical.csv',
    'BCTI': 'cleantanker_historical.csv',
    'BCI': 'cape_historical.csv',
    'BPI': 'panama_historical.csv',
    'BSI': 'suprama_historical.csv',
    'BDI': 'bdiy_historical.csv'
}

BASE_URL = "https://en.stockq.org/index/{}.php"  # Fixed: removed space

def scrape_index(code):
    """Scrape all data from stockq.org for one index"""
    url = BASE_URL.format(code)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        tables = soup.find_all('table')

        data = []
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 3:
                    date_text = cols[0].text.strip()
                    index_text = cols[1].text.strip().replace(',', '')
                    change_text = cols[2].text.strip()

                    try:
                        date = pd.to_datetime(date_text, format='%Y/%m/%d')
                        index_val = float(index_text)
                        if index_val <= 0:
                            continue  # skip zero/negative — sanity check
                        data.append({
                            'Date': date.strftime('%d-%m-%Y'),
                            'Index': index_val,
                            '% Change': change_text
                        })
                    except (ValueError, TypeError):
                        continue

        return pd.DataFrame(data)

    except Exception as e:
        print(f"Error scraping {code}: {e}")
        return pd.DataFrame()

def update_csv(filename, new_data):
    """Merge new data with existing CSV, deduplicate, sort correctly"""
    filepath = filename

    new_data = new_data.copy()
    new_data['Date_parsed'] = pd.to_datetime(new_data['Date'], format='%d-%m-%Y')

    if os.path.exists(filepath):
        existing = pd.read_csv(filepath)
        try:
            existing['Date_parsed'] = pd.to_datetime(existing['Date'], format='%d-%m-%Y')
        except Exception:
            existing['Date_parsed'] = pd.to_datetime(existing['Date'], dayfirst=True)

        combined = pd.concat([existing, new_data])
        combined = combined.drop_duplicates(subset=['Date_parsed'], keep='last')
    else:
        combined = new_data.copy()

    # Always sort by the parsed date column (correct chronological order)
    combined = combined.sort_values('Date_parsed')
    combined = combined.drop(columns=['Date_parsed'])

    combined.to_csv(filepath, index=False)
    print(f"{filename}: {len(new_data)} new rows, {len(combined)} total rows")

def main():
    print(f"Starting update at {datetime.now()}")
    
    for code, filename in INDEXES.items():
        print(f"\nProcessing {code}...")
        new_data = scrape_index(code)
        
        if not new_data.empty:
            update_csv(filename, new_data)
        else:
            print(f"No data scraped for {code}")
    
    print(f"\nCompleted at {datetime.now()}")

if __name__ == "__main__":
    main()
