import requests
import pandas as pd
from datetime import datetime
import os
import re

# Direct download URLs (the # anchor triggers download)
ETF_SOURCES = {
    'bdry': {
        'url': 'https://amplifyetfs.com/bdry-holdings/',
        'output': 'bdry_holdings.csv'
    },
    'bwet': {
        'url': 'https://amplifyetfs.com/bwet-holdings/',
        'output': 'bwet_holdings.csv'
    }
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# Category priority order (lower number = higher priority)
CATEGORY_ORDER = {
    'capesize': 1,
    'panamax': 2,
    'supramax': 3,
    'cash': 4,
    'invesco': 5,
    'other': 99
}

# Month mapping for sorting
MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def categorize_holding(name):
    """Determine category priority based on holding name"""
    name_lower = name.lower()
    
    if 'capesize' in name_lower:
        return 'capesize', CATEGORY_ORDER['capesize']
    elif 'panamax' in name_lower:
        return 'panamax', CATEGORY_ORDER['panamax']
    elif 'supramax' in name_lower:
        return 'supramax', CATEGORY_ORDER['supramax']
    elif 'cash' in name_lower:
        return 'cash', CATEGORY_ORDER['cash']
    elif 'invesco' in name_lower:
        return 'invesco', CATEGORY_ORDER['invesco']
    else:
        return 'other', CATEGORY_ORDER['other']

def extract_month_year(name):
    """
    Extract month and year from holding name
    Returns: (month_num, year) or (99, 9999) for non-dated items
    """
    name_lower = name.lower()
    
    # Look for month abbreviation + year pattern (e.g., "Mar 26", "Feb 2026")
    month_pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-]?(\d{2,4})'
    match = re.search(month_pattern, name_lower)
    
    if match:
        month_abbr = match.group(1)
        year_str = match.group(2)
        
        month_num = MONTH_MAP.get(month_abbr, 99)
        
        # Handle 2-digit vs 4-digit year
        if len(year_str) == 2:
            year = 2000 + int(year_str)
        else:
            year = int(year_str)
            
        return month_num, year
    
    # For non-dated items (Cash, Invesco, etc.), return high values so they sort last
    return 99, 9999

def sort_holdings(df):
    """
    Sort holdings by:
    1. Category priority (Capesize → Panamax → Supramax → Cash → Invesco → Other)
    2. Within each category: by month/year (nearest first)
    """
    if df.empty:
        return df
    
    # Create sorting columns
    sort_data = []
    for idx, row in df.iterrows():
        name = str(row.get('Name', ''))
        category, cat_priority = categorize_holding(name)
        month, year = extract_month_year(name)
        
        sort_data.append({
            'index': idx,
            'cat_priority': cat_priority,
            'year': year,
            'month': month,
            'category': category
        })
    
    # Create sort dataframe
    sort_df = pd.DataFrame(sort_data)
    
    # Merge with original data
    df_with_sort = df.copy()
    df_with_sort['_sort_idx'] = range(len(df))
    df_with_sort = df_with_sort.merge(sort_df, left_on='_sort_idx', right_on='index', how='left')
    
    # Sort: category priority → year → month
    df_sorted = df_with_sort.sort_values(
        by=['cat_priority', 'year', 'month'],
        ascending=[True, True, True]
    )
    
    # Drop temporary columns
    df_sorted = df_sorted.drop(columns=['_sort_idx', 'index', 'cat_priority', 'year', 'month', 'category'], errors='ignore')
    
    return df_sorted

def download_and_convert(etf_code, config):
    """Download holdings Excel and convert to CSV"""
    try:
        print(f"\nProcessing {etf_code.upper()}...")
        
        # Step 1: Get the page to extract download link or data
        session = requests.Session()
        response = session.get(config['url'], headers=HEADERS, timeout=30)
        
        # Try CSV download first
        csv_url = config['url'].rstrip('/') + '?download=csv'
        csv_response = session.get(csv_url, headers=HEADERS, timeout=30)
        
        # Check if we got CSV data
        if 'text/csv' in csv_response.headers.get('Content-Type', '') or csv_response.text.startswith('Name,Ticker'):
            temp_file = f'{etf_code}_temp.csv'
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(csv_response.text)
            
            df = pd.read_csv(temp_file)
            os.remove(temp_file)
            
        else:
            # Fallback: Scrape the HTML table
            print(f"  CSV download not detected, scraping HTML table...")
            df = scrape_html_table(response.text, etf_code)
        
        if df.empty:
            print(f"  ERROR: No data found for {etf_code}")
            return False
            
        # Clean and standardize columns
        df = clean_dataframe(df, etf_code)
        
        # Apply custom sorting
        print(f"  Sorting holdings (Capesize → Panamax → Supramax → Cash/Invesco)...")
        df = sort_holdings(df)
        
        # Save to CSV (overwrite, no history)
        df.to_csv(config['output'], index=False)
        
        print(f"  ✓ Saved {len(df)} rows to {config['output']}")
        
        # Print summary by category
        print_summary(df)
        
        return True
        
    except Exception as e:
        print(f"  ERROR processing {etf_code}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def scrape_html_table(html_content, etf_code):
    """Fallback: Parse HTML table if CSV download fails"""
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    tables = soup.find_all('table')
    
    data = []
    for table in tables:
        rows = table.find_all('tr')
        if not rows:
            continue
            
        # Try to detect headers
        headers = []
        header_row = rows[0]
        for th in header_row.find_all(['th', 'td']):
            headers.append(th.text.strip().lower().replace(' ', '_'))
        
        # Map common header variations
        header_map = {
            'name': 'Name',
            'ticker': 'Ticker',
            'cusip': 'CUSIP',
            'lots': 'Lots',
            'market_value': 'Market_Value',
            '%_market_value': 'Weightings',
            'market value': 'Market_Value',
            '% market value': 'Weightings'
        }
        
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 6:
                continue
                
            row_data = {}
            for i, col in enumerate(cols):
                if i < len(headers):
                    key = header_map.get(headers[i], headers[i])
                    val = col.text.strip()
                    
                    # Clean numeric fields
                    if key in ['Lots', 'Market_Value', 'Weightings']:
                        val = val.replace(',', '').replace('$', '').replace('%', '')
                    
                    row_data[key] = val
            
            if row_data.get('Name'):
                data.append(row_data)
    
    return pd.DataFrame(data)

def clean_dataframe(df, etf_code):
    """Standardize column names and data types"""
    # Standardize column names
    column_mapping = {
        'name': 'Name',
        'ticker': 'Ticker',
        'cusip': 'CUSIP',
        'lots': 'Lots',
        'market value': 'Market_Value',
        'market_value': 'Market_Value',
        '% market value': 'Weightings',
        'weightings': 'Weightings',
        '%_market_value': 'Weightings'
    }
    
    # Rename columns if they exist
    df = df.rename(columns=lambda x: column_mapping.get(x.lower().replace(' ', '_'), x))
    
    # Add metadata
    df['ETF'] = etf_code.upper()
    df['Last_Updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['As_of_Date'] = datetime.now().strftime('%Y-%m-%d')
    
    # Ensure numeric columns
    numeric_cols = ['Lots', 'Market_Value', 'Weightings']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', '').str.replace('%', ''), errors='coerce')
    
    # Reorder columns for consistency
    preferred_order = ['ETF', 'As_of_Date', 'Name', 'Ticker', 'CUSIP', 'Lots', 'Market_Value', 'Weightings', 'Last_Updated']
    existing_cols = [c for c in preferred_order if c in df.columns]
    other_cols = [c for c in df.columns if c not in preferred_order]
    
    return df[existing_cols + other_cols]

def print_summary(df):
    """Print summary by category"""
    print(f"\n  Summary by Category:")
    print(f"  {'-'*50}")
    
    total_value = df['Market_Value'].sum()
    
    for category in ['capesize', 'panamax', 'supramax', 'cash', 'invesco', 'other']:
        cat_df = df[df['Name'].str.lower().str.contains(category, na=False)]
        if not cat_df.empty:
            cat_value = cat_df['Market_Value'].sum()
            cat_pct = (cat_value / total_value * 100) if total_value > 0 else 0
            print(f"  {category.capitalize():12} : ${cat_value:>15,.2f} ({cat_pct:5.2f}%) - {len(cat_df)} holdings")

def main():
    print(f"Starting ETF holdings update at {datetime.now()}")
    print("=" * 60)
    
    success_count = 0
    for etf_code, config in ETF_SOURCES.items():
        if download_and_convert(etf_code, config):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"Completed: {success_count}/{len(ETF_SOURCES)} ETFs updated")
    
    if success_count < len(ETF_SOURCES):
        print("WARNING: Some updates failed")

if __name__ == "__main__":
    main()
