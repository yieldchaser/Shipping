#!/usr/bin/env python3
"""
scripts/format_book7_kendall.py
Complete, clean formatter for Book 7:
The Business of Shipping (5th Edition) by Lane C. Kendall
"""

import re
import sys
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

def format_book7():
    p = Path("corpus/books/the_business_of_shipping_lane_c_kendall_auth_z_library.md")
    try:
        raw = subprocess.check_output(
            ["git", "show", f"HEAD:{p.as_posix()}"],
            text=True,
            encoding="utf-8"
        )
    except Exception:
        raw = p.read_text(encoding="utf-8")

    # 1. Separate YAML frontmatter
    parts = raw.split("---", 2)
    fm = f"---{parts[1]}---\n"
    body = parts[2].lstrip("\r\n")

    # Clean out duplicate Summary block
    body = re.sub(r"## Summary\s*\n.*?(?=\n## THE BUSINESS|\n## Preface|\Z)", "", body, flags=re.S)
    body = re.sub(r"## THE BUSINESS\s*\nOF SHIPPING\s*\nFifth Edition\s*\nby LANE C\. KENDALL\s*\nLondon\s*\nCHAPMAN AND HALL\s*\n", "", body)

    # 2. Excise all 216+ running headers matching THE BUSINESS OF SHIPPING with page numbers
    # e.g., "## 4 THE BUSINESS OF SHIPPING" or "## 346 THE BUS I N E S S 0 F S HIP PIN G"
    body = re.sub(
        r"(?:\n|^)\s*##\s*\d{1,4}\s+.*?(?:BUSINESS|BUSI|BUS|B US).*?(?:SHIPPING|SH I PPING|S HIP PIN G|SH IPPING)\s*(?=\r?\n)",
        "\n",
        body,
        flags=re.I
    )
    # Also clean running headers that lacked ##
    body = re.sub(
        r"(?:\n|^)\s*\d{1,4}\s+THE BUSINESS OF SHIPPING\s*(?=\r?\n)",
        "\n",
        body,
        flags=re.I
    )
    # Clean roman numeral running header from preface: "x THE BUSINESS OF SHIPPING"
    body = re.sub(r"\bx\s+THE BUSINESS OF SHIPPING\b", "", body)

    # 3. Excise odd-page running headers
    odd_titles = [
        "LINER SERVICE AND TRAMP SHIPPING",
        "TRAMP SHIPPING",
        "THE MANAGEMENT OF TRAMP SHIPPING",
        "CHARTERING AND TRAMP SHIP OPERATION",
        "CHARTERING",
        "ORGANIZATION OF A LINER-SERVICE COMPANY",
        "TERMINAL MANAGEMENT",
        "TERMINAL OPERATION",
        "THE STEVEDORE CONTRACT",
        "PROCUREMENT OF VESSEL STORES AND SUPPLIES",
        "PROCUREMENT OF VESSEL STORES",
        "CONTAINERIZATION: THE BEGINNING",
        "THE RAMIFICATIONS OF CONTAINERIZATION",
        "THE OCEAN BILL OF LADING",
        "HOW FREIGHT RATES ARE MADE",
        "THE TRAFFIC STUDY",
        "STEAMSHIP CONFERENCES",
        "THE LOGIC OF STEAMSHIP SCHEDULING",
        "SCHEDULING AND BUNKERING",
        "PLANNING FOR A NEW SHIP",
        "PASSENGER CRUISES",
        "INDUSTRIAL AND SPECIAL CARRIERS",
        "TANKER MANAGEMENT",
        "THE AMERICAN SHIPPING SUBSIDY SYSTEM",
        "THE BUSINESS OF SHIPPING",
    ]
    for t in odd_titles:
        body = re.sub(
            rf"(?:\n|^)\s*##\s*{re.escape(t)}\s+[0-9IVX]+\s*(?=\r?\n)",
            "\n",
            body,
            flags=re.I
        )
    # Organization chart vertical artifact in Chapter 5
    body = re.sub(r"(?:\n|^)\s*##\s*TNEMTRAPED\s*(?=\r?\n)", "\n", body)

    # 4. Heal broken drop capitals at beginning of Preface, Intro, and Chapters
    drop_caps = [
        # Preface
        (r"HIS VOL U M E has been written", "This volume has been written"),
        (r"ajoy-filled lifetime in associa\s*\n\s*tion", "a joy-filled lifetime in association"),
        # Introduction
        (r"SH\s*\n\s*I PS and the management", "Ships and the management"),
        (r"Ma\s*\n\s*gellan", "Magellan"),
        (r"\n<\s*\n\s*are the professionals", "\nare the professionals"),
        # Chapter 3
        (r"To\s*\n\s*PROVIDE timely and efficient", "To provide timely and efficient"),
        # Chapter 4
        (r"To\s*\n\s*MORE than one maritime", "To more than one maritime"),
        # Chapter 5
        (r"EVERY steamship company, regardless of nationali\s*\n\s*ty", "Every steamship company, regardless of nationality"),
        # Chapter 6
        (r"MARINE general cargo, break-bulk terminal\s*\n\s*exists", "A marine general cargo, break-bulk terminal exists"),
        # Chapter 7
        (r"GENERAL cargo break-bulk marine terminals are", "General cargo break-bulk marine terminals are"),
        # Chapter 8
        (r"AM 0 N G the documents", "Among the documents"),
        # Chapter 9
        (r"I\s*\n\s*TIS difficult to overemphasize", "It is difficult to overemphasize"),
        # Chapter 10
        (r"Ar\s*\n\s*R I L 26, 1956,", "April 26, 1956,"),
        # Chapter 11
        (r"ON\s*\n\s*C E the feasibility", "Once the feasibility"),
        # Chapter 12
        (r"As\s*\n\s*A device of commerce,", "As a device of commerce,"),
        # Chapter 13
        (r"AN\s*\n\s*AMAZING assortment", "An amazing assortment"),
        # Chapter 14
        (r"AM\s*\n\s*0 N G the responsibilities", "Among the responsibilities"),
        # Chapter 15
        (r"FRO\s*\n\s*Mthe early days", "From the early days"),
        # Chapter 16
        (r"To\s*\n\s*TH OSE who frequent", "To those who frequent"),
        # Chapter 17
        (r"ON\s*\n\s*C E the owner", "Once the owner"),
        # Chapter 18
        (r"I\s*\n\s*TIS almost an axiom", "It is almost an axiom"),
        # Chapter 19
        (r"VACATION CRUISES-defined as", "Vacation cruises - defined as"),
        # Chapter 20
        (r"IN\s*\n\s*C L U D ED in the thousands", "Included in the thousands"),
        # Chapter 21
        (r"RANGING in size from enormous", "Ranging in size from enormous"),
        # Chapter 22
        (r"INTERN ATION AL shipping involves", "International shipping involves"),
        # Chapter 23
        (r"IN\s*\n\s*acquainting the reader with the intricate story of the\s*\n\s*management ofa modern steamship comany,",
         "In acquainting the reader with the intricate story of the\nmanagement of a modern steamship company,"),
    ]
    for pat, repl in drop_caps:
        body = re.sub(pat, repl, body)

    # 5. Promote Chapters 1 through 23 and Major Front/End Matter
    chapters_map = [
        (1, "Liner Service and Tramp Shipping", r"##\s*CHAPTER\s*1\s*-\s*Liner Service and Tramp Shipping"),
        (2, "Tramp Shipping", r"##\s*CHAPTER\s*2\s*-\s*Tramp Shipping"),
        (3, "The Management of Tramp Shipping", r"##\s*CHAPTER\s*3\s*-\s*The Management of Tramp Shipping"),
        (4, "Chartering and Tramp Ship Operation", r"##\s*CHAPTER\s*4\s*-\s*Chartering\s*\n\s*and Tramp Ship Operation"),
        (5, "Organization of a Liner-Service Company", r"##\s*CHAPTER\s*5\s*-\s*Organization of\s*\n\s*A Liner-Service Company"),
        (6, "Terminal Management", r"##\s*CHAPTER\s*6\s*-\s*Terminal Management"),
        (7, "Terminal Operation", r"##\s*CHAPTER\s*7\s*-\s*Terminal Operation"),
        (8, "The Stevedore Contract", r"##\s*CHAPTER\s*8\s*-\s*The Stevedore Contract"),
        (9, "Procurement of Vessel Stores and Supplies", r"##\s*CHAPTER\s*9\s*-\s*Procurement of Vessel Stores and Supplies"),
        (10, "Containerization: The Beginning", r"##\s*CHAPTER\s*10\s*-\s*Containerization:\s*The Beginning"),
        (11, "The Ramifications of Containerization", r"##\s*CHAPTER\s*11\s*-\s*The Ramifications of Containerization"),
        (12, "The Ocean Bill of Lading", r"##\s*CHAPTER\s*12\s*-\s*The Ocean Bill ofL ading"),
        (13, "How Freight Rates Are Made", r"##\s*CHAPTER\s*13\s*-\s*How Freight Rates Are Made"),
        (14, "The Traffic Study", r"##\s*CHAPTER\s*14\s*-\s*The Traffic Study"),
        (15, "Steamship Conferences", r"##\s*CHAPTER\s*l?5\s*-\s*Steamship Conferences"),
        (16, "The Logic of Steamship Scheduling", r"##\s*CHAPTER\s*16\s*-\s*The Logic of Steamship Scheduling"),
        (17, "Scheduling and Bunkering", r"##\s*CHAPTER\s*17\s*-\s*Scheduling and Bunkering"),
        (18, "Planning for a New Ship", r"##\s*CHAPTER\s*18\s*-\s*PlanningforaNew Ship"),
        (19, "Passenger Cruises", r"##\s*CHAPTER\s*19\s*-\s*Passenger Cruises"),
        (20, "Industrial and Special Carriers", r"##\s*CHAPTER\s*20\s*-\s*Industrial and Special Carriers"),
        (21, "Tanker Management", r"##\s*CHAPTER\s*21\s*-\s*TankerA1anagement"),
        (22, "The American Shipping Subsidy System", r"##\s*CHAPTER\s*22\s*-\s*The American\s*\n\s*Shipping Subsidy System"),
        (23, "The Business of Shipping", r"##\s*CHAPTER\s*23\s*-\s*The Business of Shipping"),
    ]
    for num, title, pat in chapters_map:
        repl = f"\n\n---\n\n## Chapter {num}: {title}\n\n"
        body = re.sub(pat, repl, body)

    # 6. Format Dedication, Preface, Introduction, End Matter
    body = re.sub(r"##\s*Preface", "## Preface", body)
    body = re.sub(r"##\s*Introduction", "## Introduction", body)

    # 7. Format Chapter 1 Liner Service vs Tramp Shipping comparison table cleanly
    # Pattern to match the crammed lines 217-421 and replace with clean GFM table
    comp_pat = r"Liner Service Tramp Shipping\s*\n1\. Sailings are regular and re.*?10\. Passengers are not carried.*?made in the vessels' design\."
    
    clean_table = """### Comparison: Liner Service vs. Tramp Shipping

| No. | Liner Service | Tramp Shipping |
| :---: | :--- | :--- |
| **1** | Sailings are regular and repeated from and to designated ports on a trade route, at intervals established in response to the quantity of cargo generated along that route. True liner service is distinguished by the repetition of voyages and the consistent advertising of such voyages. Once the service is established, the operator must conform, within narrow time limits, to the published schedule. Although the frequency of sailings is related directly to the amount of business available, it is general practice to dispatch at least one ship each month. Vessels engaged in liner service may be owned or chartered; it is the regularity and repetitious nature of the operation, rather than the proprietorship, which is crucial. | Sailings are based on cargo commitments that vary with the vessel's employment, and are usually different for every voyage. There is no expected repetition of voyages as a normal part of tramp operation. Each trip is scheduled individually, subject to the requirements of the cargo to be carried and the particular route to be followed. In certain trades, such as oil and coal, owners often agree to make a number of repetitious voyages carrying the same commodity. These "consecutive voyages" are arranged expressly to fit the charterer's convenience, and do not establish a "liner service." |
| **2** | Liners are common (public) carriers, required by law to accept without discrimination between offerers any legal cargo which the ship is able to transport. Some liner operators stipulate the minimum quantity of cargo which must be presented by a single shipper; so long as the limitation is reasonable, this is permissible. Cargo usually is varied, and is called either "general" or "package." In container transportation, everything is packed into the large boxes before they are placed aboard ship. Operators accept small shipments for consolidation, i.e., packing into containers with other small lots until the boxes are filled. | Tramps are contract (private) carriers, and normally carry full shiploads of a single commodity, usually in bulk. In most cases, there is only one shipper, but two or more shippers of the same kind of cargo occasionally may use a single ship. |
| **3** | Goods carried in liner-service ships usually are of higher value than the cargo hauled in tramps, and are charged higher freight rates. The fact that common carriers accept less than shipload lots, nearly always in packages (including containers) requiring special care in stowage, also influences the establishment of liner rates. Handling ("stevedoring") charges always are included in the freight rate. Because of the variety of commodities loaded in every port of call, great care must be exercised by ship operators to assure delivery in good condition. Freight rates are identical for all shippers of a given item transported in the same ship. | Cargoes carried in tramps generally are those which can be transported in bulk ("homogeneous cargoes") and have low intrinsic value. Typical cargoes are coal, ores, grain, lumber, sugar, and phosphate rock. The cost of loading and unloading the ship in most cases is paid by the charterer, but this is subject to negotiation between shipowner and charterer. Freight rates for tramps reflect the fact that movements frequently are from a single port of loading to a single port of discharge, with minimum expense involved in the care of the cargo while in transit. |
| **4** | A liner-service company issues a standard (or uniform) contract of carriage or bill of lading. Regardless of the size of the shipment, or the number of different commodities or items comprising a given lot of cargo, the provisions of the contract apply equally to all shippers who use any one vessel. These provisions are not subject to negotiation, but are unilaterally imposed by the carrier. Only in very exceptional cases will a senior executive of the common carrier alter the terms of the bill of lading to accommodate an individual shipper. | The owner of a tramp ship must negotiate a separate contract for each employment of his vessel, and the terms of the charter-party vary from ship to ship, depending upon the bargaining abilities of owner and charterer, and the general trend of the market. The terms of the agreement are applicable only to the ship named in the charter party. Although the basic charter parties are printed and follow a set form, they may be changed in any manner desired by the contracting parties. Since the changes apply to a particular ship for a particular voyage or period of time, the alterations are not publicized widely. |
| **5** | Freight rates in the liner services are stabilized by setting identical charges for all shippers of the same item aboard a certain ship. Rates may vary, however, from one sailing to another, but increases are announced in advance. Rates are compiled into detailed listings ("freight tariffs") which are made available to shippers on demand. Frequently, two or more carriers serving a particular trade route form an association ("conference") intended to stabilize rates and regulate competition. Conference rates apply uniformly to all member lines, but are subject to review. (In the United States, the reviewing authority is the Federal Maritime Commission.) The necessity to conform to government regulations imposed upon common carriers tends to prevent the freight rates charged by liner-service operators from making sudden sharp changes. | Freight rates for tramps vary according to the supply of and demand for ships. The charterers' position is strong, and rates are low, when there are comparatively few cargoes being offered and many ships are competing for the business. The shipowners' position is strong, and rates are high, when there are many cargoes and a small number of vessels. Competition among owners is keen, and often a difference of five cents a ton on a shipload lot will determine which ship is chartered. Wide extremes in rates, and abrupt changes in the level of charter rates, are evident whenever there is a major event of international significance - the outbreak of a war, a major crop failure, widespread strikes in some country, for example. No freight tariffs are compiled by owners of tramp vessels, and no associations exist for the purpose of setting rates and stabilizing competition. Summaries of the freight market are published regularly and include quotations of the rates at which ships have been chartered. |
| **6** | Services - frequency of sailings and ports of call, as well as the capabilities of the ships themselves - are adjusted to meet the demands of shippers. Many liner operators arrange their schedules to meet minimum needs during the year, and then augment sailings when seasonal increases are experienced. Changes in liner service often are influenced as much by political and technological considerations as they are by economic factors. Drastic changes in established liner operations are infrequent; carriers' intentions, especially relating to withdrawals from the route, usually are well publicized in advance. This is essential to the dependability of the liner trade. | Rates and services are determined by negotiation between shipowner and charterer, and reflect the specific requirements of the contracting parties. Regular and repeated voyages on the same route are not part of tramp operation, and therefore no conferences exist. Supervision in the public interest by a regulatory authority is unnecessary; the natural working of the laws of supply and demand assure adequate control. |
| **7** | Liner-service vessels often reflect in their design the special requirements encountered in their employment. Refrigerated fruit and meat carriers, heavy-lift ships, roll-on/roll-off vessels, container ships, and break-bulk ships may be found on many routes, depending upon the demand for these specialized capabilities. Because more or less identical cargoes move in all the dry-cargo liners on a given trade route, many of the ships employed on that route, regardless of owner, are similar in capability. Containerships vary in their cruising speed and the number of containers they carry, but otherwise are very similar, wherever they are used. Since 1945, liner ships of all types have been growing in size and increasing in speed; inevitably the cost of their acquisition and operation has risen steeply. | Most tramp ships are intended for worldwide service, and are of moderate size and draft. Although used primarily to transport cargoes in bulk, many tramps have a single 'tween deck and sufficient equipment and speed to permit them to be chartered for use in the break-bulk liner trades. Additionally, many modern, very large carriers designed to transport a single commodity such as ore or coal, have been placed in tramp-type operation. Compared with vessels constructed for the liner trades, tramps still are simpler in design and less costly to construct. |
| **8** | Liner-service companies have a large and somewhat complex organization in the shore establishment, especially in the home office. Normally there are several divisions (i.e., traffic, operations, financial, and managerial) with an appropriate staff. Outport offices may duplicate this organization on a smaller scale. Liner-service operations entail contact with shippers, maintenance of an active cargo handling terminal, and processing a great amount of detail work inherent in general cargo service on a repetitious schedule. | Tramp owners usually have small staffs in the home office, with little division of functions. No traffic department is needed; charters are negotiated by telephone or cable, and face-to-face contact with charterers is unusual. Because agents are employed to service the ships in ports of call, and are paid on a fee basis for each task performed, there is no need for an operating department. If the size of the owner's fleet justifies the expense, home office personnel may include specialists to assure satisfactory performance of the ships. Stevedoring very rarely is the responsibility of the owner, and therefore no terminal department is included in the home office. |
| **9** | Procurement of cargo is the responsibility of the traffic department, which includes salesmen ("solicitors") to call on regular as well as prospective shippers. Advertising is extensive and continuous, and major efforts are made to disseminate information concerning the capabilities of the line. Arrival and departure times of ships are widely publicized. Shippers are assisted in the development of markets for their goods as a means of increasing cargo offerings. | Procurement of cargo is handled through brokers who represent the tramp shipowner in negotiations with other brokers representing cargo interests. There is no advertising, and no promotional activity. Ship movements normally appear only in the newspaper listings of vessels which have arrived or sailed. |
| **10** | Passengers sometimes are carried in cargo liners, but by international agreement the number is limited to twelve. | Passengers are not carried aboard tramp ships, and no provision for their accommodation is made in the vessels' design. |

> **Figure Captions**:
> - *California* (built 1962, break-bulk liner, 20 knots, 14,439 dwt) & *Menelaus* (built 1977, combo break-bulk/container, 18.2 knots, 21,242 dwt). *(Photos: Georgia Ports Authority)*
> - *Glenmoor* (built 1954, general-purpose tramp ship). *(Photo: Moor Line)*
> - Deck petty officer's quarters in a well-equipped British tramp. *(Photo: Moor Line)*"""

    body = re.sub(comp_pat, clean_table, body, flags=re.S)

    # 8. Blockquote standalone photo captions across the book
    body = re.sub(
        r"(?:\n|^)(Photo[s]?:\s*[^\n]+)",
        r"\n> *\1*\n",
        body
    )

    # 9. Clean excessive newlines
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Final document assembly
    doc = (
        fm + "\n"
        "# The Business of Shipping (5th Edition)\n\n"
        "**Author**: Lane C. Kendall  \n"
        "**Publisher**: Chapman & Hall (London)  \n\n"
        "## Summary\n\n"
        "Lane C. Kendall's *The Business of Shipping* provides a comprehensive analysis of the administrative "
        "and management principles governing the commercial maritime industry. Drawing on a lifetime of experience "
        "in steamship offices and maritime education, the author details the operational procedures, chartering, "
        "terminal management, containerization, conference systems, and vessel scheduling governing modern shipping enterprises.\n\n"
        "---\n\n"
        f"{body}\n"
    )

    p.write_text(doc, encoding="utf-8")
    dest = Path("knowledge/docs/books/the_business_of_shipping_lane_c_kendall_auth_z_library.md")
    dest.write_text(doc, encoding="utf-8")
    print(f"Book 7 formatted successfully: {len(doc)} chars, {len(doc.splitlines())} lines written to {p} and {dest}")

if __name__ == "__main__":
    format_book7()
