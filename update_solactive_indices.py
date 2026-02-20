import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re

# Solactive index URLs
INDICES = {
    'BDRY': {
        'url': 'https://www.solactive.com/Indices/?index=DE000SLA4BY3',
        'output': 'solactive_bdry.csv'
    },
    'BWET': {
        'url': 'https://www.solactive.com/Indices/?index=DE000SL0HLG3',
        'output': 'solactive_bwet.csv'
    }
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def scrape_solactive_index(name, config):
    """Scrape Solactive index data"""
    try:
        print(f"\nProcessing {name}...")
        response = requests.get(config['url'], headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        data = {
            'Index': name,
            'Last_Updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Find CURRENT QUOTES section
        # Based on your screenshot, the data is in a section with class or structure containing "CURRENT QUOTES"
        
        # Try to find by text content
        current_quotes_section = None
        
        # Look for headings or sections containing "CURRENT QUOTES"
        for heading in soup.find_all(['h2', 'h3', 'h4', 'div', 'section']):
            if 'CURRENT QUOTES' in heading.get_text():
                current_quotes_section = heading
                break
        
        if current_quotes_section:
            # The data might be in a table or div structure after the heading
            # Look for the parent container
            parent = current_quotes_section.find_parent() or current_quotes_section
            
            # Extract all text and parse
            text = parent.get_text()
            
            # Parse Last quote (format: "19 Feb 2026): 2376.36" or similar)
            last_quote_match = re.search(r'Last quote\s*\(([^)]+)\):\s*([\d.,]+)', text)
            if last_quote_match:
                data['Last_Quote_Date'] = last_quote_match.group(1).strip()
                data['Last_Quote_Value'] = float(last_quote_match.group(2).replace(',', ''))
            
            # Parse Day range (format: "2376.36 / 2384.78")
            day_range_match = re.search(r'Day range:\s*([\d.,]+)\s*/\s*([\d.,]+)', text)
            if day_range_match:
                data['Day_Range_Low'] = float(day_range_match.group(1).replace(',', ''))
                data['Day_Range_High'] = float(day_range_match.group(2).replace(',', ''))
            
            # Parse Change abs./rel. (format: "-0.32 / -0.01%" or "191.58 / 7.43%")
            change_match = re.search(r'Change abs\./rel\.:\s*([-\d.,]+)\s*/\s*([-\d.,]+)%?', text)
            if change_match:
                data['Change_Abs'] = float(change_match.group(1).replace(',', ''))
                # Remove % sign if present and convert
                change_rel = change_match.group(2).replace('%', '')
                data['Change_Rel'] = float(change_rel)
            
            # Parse Year range (format: "1333.82 / 2384.78")
            year_range_match = re.search(r'Year range:\s*([\d.,]+)\s*/\s*([\d.,]+)', text)
            if year_range_match:
                data['Year_Range_Low'] = float(year_range_match.group(1).replace(',', ''))
                data['Year_Range_High'] = float(year_range_match.group(2).replace(',', ''))
        
        # Alternative: Look for specific divs or tables with class names
        if not data.get('Last_Quote_Value'):
            # Try to find by common class names or structure
            # Look for divs containing the specific labels
            labels = ['Last quote', 'Day range', 'Change abs./rel.', 'Year range']
            
            for label in labels:
                # Find elements containing the label text
                elements = soup.find_all(text=re.compile(label))
                for elem in elements:
                    parent = elem.parent
                    if parent:
                        # Get the next sibling or parent's text
                        full_text = parent.get_text()
                        print(f"  Found '{label}' in: {full_text[:100]}...")
        
        # Create DataFrame
        df = pd.DataFrame([data])
        
        # Save to CSV
        df.to_csv(config['output'], index=False)
        print(f"  ✓ Saved to {config['output']}")
        print(f"  Last Quote: {data.get('Last_Quote_Value', 'N/A')}")
        print(f"  Change: {data.get('Change_Abs', 'N/A')} / {data.get('Change_Rel', 'N/A')}%")
        
        return True
        
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print(f"Starting Solactive Indices Update")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    success_count = 0
    for name, config in INDICES.items():
        if scrape_solactive_index(name, config):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"Completed: {success_count}/{len(INDICES)} indices updated")
    
    if success_count < len(INDICES):
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
