#!/usr/bin/env python3
"""
Restore missing and unformatted historical tables in Book 3:
The World's Key Industry - History and Economics of International Shipping
Tables restored:
- Table 3.1: Balance of payments of New England and Middle Colonies 1768-72
- Table 4.1: Sail and steamship share of tonnage entrances 1860-1910
- Table 4.2: Percentage steam participation by tonnage per region (reformatted to clean markdown)
- Table 8.1: UK-registered merchant fleet 1950-1995
- Table 10.1: New Zealand port labour productivity 1976-1988
- Table 11.1: Container throughputs of major Chinese ports 1995-2000
Maintains 100% byte-for-byte mirroring between corpus/ and knowledge/.
"""
from pathlib import Path

CORPUS_MD = Path("corpus/books/worlds_key_industry_harlaftis_tenold_valdaliso.md")
KNOWLEDGE_MD = Path("knowledge/docs/books/worlds_key_industry_harlaftis_tenold_valdaliso.md")

TABLE_3_1 = """
### Table 3.1 Balance of Payments of the New England and Middle Colonies, Average 1768–72

| Category / Destination | New England | Middle Colonies | Combined | % of Earnings |
|:---|---:|---:|---:|---:|
| **Imports** | | | | |
| Total Imports | 1054 | 1202 | 2256 | - |
| **Earnings: Commodity exports all destinations** | | | | |
| Exports to All Destinations | 477 | 559 | 1036 | 60% |
| *[Of which to West Indies]* | 303 | 244 | 548 | 32% |
| *[Of which to Britain]* | 87 | 75 | 162 | 9% |
| **Shipping earnings** | 327 | 177 | 504 | 29% |
| **Other invisibles** | 100 | 74 | 174 | 10% |
| **Total earnings** | 904 | 810 | 1714 | 100% |

*Source: Shepherd and Walton (1972), pp. 115, 128 and 134.*
"""

TABLE_4_1 = """
### Table 4.1 Sail and Steamship Vessels' Share of Total Tonnage Entrances with Cargo and in Ballast, 1860–1910

| Year | Sail % | Steam % |
|:---:|---:|---:|
| 1860 | 79.1% | 20.9% |
| 1870 | 66.2% | 33.8% |
| 1880 | 37.0% | 63.0% |
| 1890 | 17.2% | 82.8% |
| 1900 | 8.2% | 91.8% |
| 1910 | 2.9% | 97.1% |

*Sources: Calculated from Annual Statement of Trade and Navigation, 1861 and Annual Statement of the Navigation and Shipping of the United Kingdom, 1871, 1881, 1891, 1901 and 1911.*
"""

TABLE_8_1 = """
### Table 8.1 The UK-Registered Merchant Fleet 1950–95 (500+ Gross Registered Tonne Vessels)

| Year | Number of Vessels | Gross Registered Tonnes (GRT) (millions) | UK-Registered Fleet as Proportion of World Tonnage (% dwt) |
|:---:|---:|---:|---:|
| 1950 | 3,092 | 17,198 | - |
| 1955 | 3,041 | 18,208 | - |
| 1960 | 2,902 | 20,202 | - |
| 1965 | 2,401 | 29,382 | - |
| 1970 | 1,977 | 24,061 | 11.4% |
| 1975 | 1,682 | 31,489 | 9.7% |
| 1980 | 1,275 | 25,769 | 6.4% |
| 1985 | 693 | 12,208 | 3.2% |
| 1990 | 427 | 5,512 | 1.2% |
| 1995 | 365 | 5,761 | 1.0% |

*Note: Data 1950-1985 includes Crown Dependency vessels registered in the Isle of Man and Channel Islands.*  
*Sources: UK Department of Transport (2006) Transport Statistics, table 5.13; UNCTAD (2001) Review of Maritime Transport, table 16.*
"""

TABLE_10_1 = """
### Table 10.1 New Zealand Port Labour Productivity (All Ports), 1976–88

| Year | Tons of Cargo Handled | Total Paid Hours | Tons / Total Paid Hours |
|:---:|---:|---:|---:|
| 1976 | 33,321,305 | 13,481,350 | 2.47 |
| 1977 | 36,167,714 | 13,226,514 | 2.73 |
| 1978 | 34,076,157 | 12,263,487 | 2.78 |
| 1979 | 35,908,364 | 11,381,645 | 3.15 |
| 1980 | 37,760,888 | 10,981,663 | 3.44 |
| 1981 | 12,894,508 | 10,719,085 | 1.18 |
| 1982 | 13,738,491 | 10,339,971 | 1.33 |
| 1983 | 13,530,833 | 10,044,869 | 1.35 |
| 1984 | 16,153,652 | 9,830,442 | 1.64 |
| 1985 | 15,979,370 | 9,252,480 | 1.73 |
| 1986 | 14,916,180 | 9,217,018 | 1.62 |
| 1987 | 14,836,566 | 8,625,701 | 1.79 |
| 1988 | 15,877,493 | 7,599,078 | 2.09 |

*Source: Waterfront Industry Commission, Annual Reports, various years.*
"""

TABLE_11_1 = """
### Table 11.1 Container Throughputs of Major Chinese Ports in TEU, 1995–2000

| Port | 1995 | 1996 | 1997 | 1998 | 1999 | 2000 |
|:---|---:|---:|---:|---:|---:|---:|
| Shanghai | 1,526,500 | 1,971,000 | 2,064,000 | 3,060,000 | 4,216,000 | 5,612,000 |
| Shenzhen | 283,600 | 589,000 | 1,147,300 | 1,951,700 | 2,986,100 | 3,993,000 |
| Qingdao | 603,018 | 830,000 | 1,000,000 | 1,213,700 | 1,543,000 | 2,116,000 |
| Tianjin | 702,051 | 800,000 | 850,000 | 1,018,000 | 1,302,000 | 1,708,000 |
| Guangzhou | 250,000 | 558,000 | 600,000 | 846,600 | 1,120,000 | 1,427,000 |
| Xiamen | 329,000 | 400,168 | 450,000 | 654,000 | 848,000 | 1,085,000 |
| Dalian | 374,259 | 420,751 | 450,000 | 525,700 | 736,000 | 1,012,000 |
| Ningbo | 160,000 | 170,000 | 175,000 | 350,200 | 601,000 | 902,000 |
| **TOTAL** | **4,228,428** | **5,738,919** | **6,736,300** | **9,619,900** | **13,352,100** | **17,855,000** |

*Source: Shippers Today (2001) 'The co-development of the ports of Hong Kong and Shenzhen: a past review and future prospect at the millennium' (in Chinese).*
"""

def main():
    text = CORPUS_MD.read_text(encoding='utf-8')
    
    # 1. Insert Table 3.1
    anchor_3_1 = "victory in the American Revolutionary War. That said, however, nearly"
    if anchor_3_1 in text:
        text = text.replace(anchor_3_1, anchor_3_1 + "\n\n" + TABLE_3_1.strip() + "\n")
        print("Inserted Table 3.1")
        
    # 2. Insert Table 4.1
    anchor_4_1 = "was virtually irrelevant."
    if anchor_4_1 in text:
        text = text.replace(anchor_4_1, anchor_4_1 + "\n\n" + TABLE_4_1.strip() + "\n")
        print("Inserted Table 4.1")
        
    # 3. Format Table 4.2
    old_t42 = """Table 4.2 Percentage steam participation by tonnage per region of origin,
1855-1910
Percentage steam by tonnage, British and foreign vessels with cargo and in
ballast' entering UK ports
1855 1860 1870 1880 1890 1900 1910
N. Europe 4.4 10.2 24.0 40.4 61.5 78.3 91.8
W. Europe 30.9 31.4 43.0 78.3 90.6 94.2 97.7"""
    
    new_t42 = """### Table 4.2 Percentage Steam Participation by Tonnage per Region of Origin, 1855–1910

*Percentage steam by tonnage, British and foreign vessels 'with cargo and in ballast' entering UK ports:*

| Region of Origin | 1855 | 1860 | 1870 | 1880 | 1890 | 1900 | 1910 |
|:---|---:|---:|---:|---:|---:|---:|---:|
| N. Europe | 4.4% | 10.2% | 24.0% | 40.4% | 61.5% | 78.3% | 91.8% |
| W. Europe | 30.9% | 31.4% | 43.0% | 78.3% | 90.6% | 94.2% | 97.7% |"""
    
    if old_t42 in text:
        text = text.replace(old_t42, new_t42)
        print("Reformatted Table 4.2")
        
    # 4. Insert Table 8.1
    anchor_8_1 = "ment assistance toward the capital cost of acquiring a ship'.6"
    if anchor_8_1 in text:
        text = text.replace(anchor_8_1, anchor_8_1 + "\n\n" + TABLE_8_1.strip() + "\n")
        print("Inserted Table 8.1")
        
    # 5. Insert Table 10.1
    anchor_10_1 = "all but one year from 1972 until 1982.38 As Table 10.1 shows,"
    if anchor_10_1 in text:
        text = text.replace(anchor_10_1, anchor_10_1 + "\n\n" + TABLE_10_1.strip() + "\n")
        print("Inserted Table 10.1")
        
    # 6. Insert Table 11.1
    anchor_11_1 = "restricted to just being the hub of the PRD and southern China.13"
    if anchor_11_1 in text:
        text = text.replace(anchor_11_1, anchor_11_1 + "\n\n" + TABLE_11_1.strip() + "\n")
        print("Inserted Table 11.1")
        
    CORPUS_MD.write_text(text, encoding='utf-8')
    KNOWLEDGE_MD.write_text(text, encoding='utf-8')
    print("Book 3 tables updated successfully!")
    print(f"Corpus size: {CORPUS_MD.stat().st_size:,} bytes")
    print(f"Knowledge size: {KNOWLEDGE_MD.stat().st_size:,} bytes")
    print(f"Parity: {CORPUS_MD.stat().st_size == KNOWLEDGE_MD.stat().st_size}")

if __name__ == "__main__":
    main()
