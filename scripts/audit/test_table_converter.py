"""
Test layout table unpacking vs data table conversion
"""

from bs4 import BeautifulSoup

def process_table(table):
    # Check if layout table
    nested_tables = table.find_all('table')
    classes = ' '.join(table.get('class', []))
    if nested_tables or any(c in classes for c in ['nl-container', 'row-content', 'social-table']):
        # It is a layout container! Extract content elements
        lines = []
        for elem in table.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'img']):
            # Skip if inside another child we will encounter or already processed
            if elem.name.startswith('h'):
                txt = elem.get_text(strip=True)
                if txt:
                    lvl = '#' * int(elem.name[1])
                    lines.append(f"\n{lvl} {txt}\n")
            elif elem.name == 'p':
                txt = elem.get_text(strip=True)
                if txt:
                    lines.append(f"{txt}\n")
            elif elem.name == 'li':
                txt = elem.get_text(strip=True)
                if txt:
                    lines.append(f"- {txt}")
        # Deduplicate consecutive identical lines
        deduped = []
        for l in lines:
            if not deduped or l != deduped[-1]:
                deduped.append(l)
        return '\n'.join(deduped), False
    else:
        # Genuine data table!
        rows = table.find_all('tr')
        table_lines = []
        table_data = []
        for r_idx, row in enumerate(rows):
            cols = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
            if cols and any(cols):
                table_lines.append("| " + " | ".join(cols) + " |")
                table_data.append(cols)
                if r_idx == 0:
                    table_lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
        return '\n'.join(table_lines), table_data

def main():
    print("Testing newsletter unpacking:")
    soup_nl = BeautifulSoup(open('corpus/07-signal/html/february-2025-newsletter.html', encoding='utf-8').read(), 'html.parser')
    nl_table = soup_nl.find('table', class_='nl-container')
    if nl_table:
        md, is_data = process_table(nl_table)
        print("Is data table:", is_data)
        print("First 500 chars of extracted markdown:")
        print(md[:500])

    print("\nTesting data table conversion on dry-week-02-2025:")
    soup_dry = BeautifulSoup(open('corpus/07-signal/html/dry-week-02-2025.html', encoding='utf-8').read(), 'html.parser')
    tables = soup_dry.find_all('table')
    print("Tables found in dry-week-02-2025:", len(tables))
    for t in tables:
        md, is_data = process_table(t)
        print("Is data table:", bool(is_data))
        print("Markdown table:")
        print(md)

if __name__ == '__main__':
    main()
