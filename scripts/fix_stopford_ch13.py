#!/usr/bin/env python3
"""
Fix Chapter 13 tables and layout in Maritime Economics 3rd Edition.
Addresses user screenshots 1 and 2:
1. Table 13.6: Principal world container routes, 2004
2. Table 13.7: Twenty largest container fleet operators 1980, 2001, 2005
3. Figures 13.3, 13.4, 13.5 embedded tables
4. Removal of running headers and healing of fractured sentences across page boundaries.
"""

import re
from pathlib import Path

STOPFORD_PATH = Path("corpus/books/maritime_economics_3rd_edition.md")
KNOWLEDGE_PATH = Path("knowledge/docs/books/maritime_economics_3rd_edition.md")

NEW_CH13_SECTION = """<!-- Page 550 -->

**Table 13.6** Principal world container routes, 2004, showing approximate trade volumes

| Route | Route No. | 1994 ('000 TEU p.a.) | 1994 (% total) | 2004 East / North bound ('000 TEU p.a.) | 2004 West / South bound ('000 TEU p.a.) | 2004 Total trade ('000 TEU) | 2004 (% total) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. East-West trades** | | | | | | | |
| Transpacific | 1 | 7,470 | 20% | 11,361 | 4,892 | 16,253 | 17% |
| Transatlantic | 2 | 3,030 | 8% | 2,473 | 3,228 | 5,701 | 6% |
| Europe-Far East | 3 | 4,895 | 13% | 3,538 | 7,510 | 11,048 | 12% |
| Europe-Mid East | 4 | 645 | 2% | 1,675 | 525 | 2,200 | 2% |
| North America-Mid East | 5 | 205 | 1% | 160 | 287 | 447 | 0% |
| Far East-Mid East | 6 | 255 | 1% | 300 | 1,300 | 1,600 | 2% |
| **Total East-West trades** | | **16,500** | **44%** | **19,507** | **17,742** | **37,249** | **39%** |
| **2. North-South trades** | | | | | | | |
| *Europe to:* | | | | | | | |
| Latin America | 7 | 1,150 | 3% | 2,046 | 799 | 2,845 | 3% |
| South Asia | 8 | 475 | 1% | 910 | 600 | 1,510 | 2% |
| Africa | 9 | 950 | 3% | 770 | 1,487 | 2,257 | 2% |
| Australasia | 10 | 400 | 1% | 256 | 343 | 599 | 1% |
| Total Europe | | 2,975 | 8% | 3,982 | 3,229 | 7,211 | 8% |
| *North America to:* | | | | | | | |
| Latin America | 11 | 2,000 | 5% | 2,627 | 1,526 | 4,153 | 4% |
| South Asia | 12 | 250 | 1% | 533 | 216 | 749 | 1% |
| Africa | 13 | 100 | 0% | 149 | 189 | 338 | 0% |
| Australasia | 14 | 275 | 1% | 203 | 252 | 455 | 0% |
| Total North America | | 2,625 | 7% | 3,512 | 2,183 | 5,695 | 6% |
| *Far East to:* | | | | | | | |
| Latin America | 15 | 725 | 2% | 1,100 | 850 | 1,950 | 2% |
| South Asia | 16 | 425 | 1% | 850 | 1,120 | 1,970 | 2% |
| Africa | 17 | 425 | 1% | 825 | 975 | 1,800 | 2% |
| Australasia | 18 | 875 | 2% | 785 | 800 | 1,585 | 2% |
| Total Far East | | 2,450 | 7% | 3,560 | 3,745 | 7,305 | 8% |
| **Total North-South Trades** | | **8,050** | **22%** | **11,054** | **9,157** | **20,211** | **21%** |
| **3. Intra-regional** | | | | | | | |
| Asia | 19 | 6,750 | 18% | - | - | 28,154 | 29% |
| Europe | 20 | 4,250 | 11% | - | - | 7,675 | 8% |
| North America | 21 | 1,250 | 3% | - | - | 339 | 0% |
| **Total intra regional** | | **12,250** | **33%** | - | - | **36,168** | **38%** |
| Other | 22 | 300 | 1% | - | - | 1,957 | 2% |
| **Total container trade** | | **37,100** | **100%** | - | - | **95,585** | **100%** |

*Source: Clarkson Research and various sources*

<!-- Page 551 -->

#### The transpacific trade

Containerization started in the Far East trade in December 1968 when Sea-Land introduced the container service from Seattle to Yokohama and the Japanese shipping companies introduced six 700/800 TEU container ships into a service between California and Japan. Now the biggest deep-sea liner route is the transpacific trade between North America and the Far East, with 16 million TEU of trade, representing 17% of the world total. The services operate between North American ports on the East Coast, the Gulf and the West Coast, to the industrial centres of Japan and the Far East, with some services extending to the Middle East. Some services to the USA Atlantic coast operate direct by water through the Panama Canal, but other containers to US East Coast are shipped under one bill of lading to a US West Coast port and then by rail to the East Coast destination, thus avoiding the Panama transit. On the rail leg containers may be double-stacked. There is a substantial cargo imbalance on this trade, and in 2004 eastbound exports (footnote 30) from the 10 major Asian economies to the USA were 11.4 million TEU, whilst the westbound exports were only 4.9 million TEU. This creates significant opportunities for westbound minor bulk cargoes of the sort we saw in the Port of Vancouver trade data in Table 13.4.

In 2004, about 18 operators were servicing the trade, including Maersk, Evergreen, CMA, Mediterranean Shipping Company (MSC), the Grand Alliance and the New World Alliance. An example of a round voyage is provided in Figure 13.3. The service calls at five ports in South East Asia and two on the US West Coast, covering about 16,500 miles. At a speed of 21.5 knots the sea time is 27 days, with an additional 8 days in port, giving a round journey time of 35 days. Port-to-port delivery times range from 10 to 18 days, depending on where the ports lie in the schedule. To provide weekly 'express' sailings in this trade requires a fleet of five ships, though some services might increase the number of port calls so as to operate to a six-week round voyage which can be operated by six ships. The 'all water' services to the US East Coast continue on through the Panama Canal, adding another 5,000 miles and requiring nine vessels, and delivery times are very wide, ranging from 10 to 36 days at the extreme ends of the service. Because of the long voyage time the transpacific trade uses the biggest ships, with many 'post-Panamax' vessels over 4,000 TEU on this service, though the East Coast services are limited to Panamax vessels.

**Figure 13.3** Typical transpacific loop using five ships

| Load | Discharge | Distance (nautical miles) | Sea days | Port days | Total days |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Sendai | Oakland | 4,800 | 9.3 | 1 | 10.3 |
| Oakland | Long Beach | 450 | 0.9 | 1 | 1.9 |
| Long Beach | Oakland | 450 | 0.9 | 1 | 1.9 |
| Oakland | Nagoya | 4,800 | 9.3 | 1 | 10.3 |
| Nagoya | Kobe | 450 | 0.9 | 0.5 | 1.4 |
| Kobe | Shanghai | 783 | 1.5 | 0.5 | 2.0 |
| Shanghai | Kobe | 783 | 1.5 | 1 | 2.5 |
| Kobe | Nagoya | 450 | 0.9 | 0.5 | 1.4 |
| Nagoya | Tokyo | 400 | 0.8 | 0.5 | 1.3 |
| Tokyo | Sendai | 600 | 1.2 | 1 | 2.2 |
| **Total** | | **13,966** | **27.1** | **8.0** | **35.1** |

*Average speed: 21.5 knots*

<!-- Page 552 -->

#### The North Atlantic trade

The North Atlantic was the first route containerized in the mid-1960s, as one might expect, since at that time it linked the two major industrial centres of the world, East Coast North America and western Europe. In 2004 it had a trade of 5.7 million TEU, accounting for 6% of world container trade (Table 13.6). There is a trade imbalance westbound, reflecting the greater volume of cargo to North America. In 2004, for example, there was 3.2 million TEU of cargo travelling west between Europe and the USA and only 2.5 million TEU in the opposite direction.

Geographically, the North Atlantic trade covers the major European ports of Göteborg, Hamburg, Bremerhaven, Antwerp, Rotterdam, Felixstowe and Le Havre, though there are some other smaller ports included on the itineraries of certain liner companies. At the North American end of the operation it is organized into two sections covering northern Europe to US Atlantic and northern Europe to the St Lawrence. The principal Canadian ports serviced are Montreal and Halifax, while in the US Boston, New York, Philadelphia, Baltimore, Hampton Roads, Wilmington and Charleston are all regular port calls. Some services extend into the US Gulf, particularly to Houston and Mobile. A typical service is shown in Figure 13.4. It calls at three ports in Europe and four in the USA. The round voyage distance is about 8,000 miles, which can be completed in 18 days at a speed of 19 knots. Allowing 7 days for port time and a sea margin of 2 days, the round trip takes about 28 days, which could be serviced using a fleet of four ships.

**Figure 13.4** Typical transatlantic loop using five ships

*US Gulf to Europe Service:*
*Transport time between ports in days*

| From/To | Antwerp | Southampton | Bremerhaven |
| :--- | :---: | :---: | :---: |
| Miami | 18 | 19 | 21 |
| Houston | 15 | 16 | 18 |
| Charleston | 11 | 12 | 14 |
| Norfolk | 9 | 10 | 12 |

*Europe to US Gulf Service:*
*Transport time between ports in days*

| From/To | Charleston | Miami | Houston | Norfolk |
| :--- | :---: | :---: | :---: | :---: |
| Bremerhaven | 10 | 12 | 15 | 21 |
| Southampton | 12 | 14 | 17 | 23 |
| Antwerp | 13 | 15 | 18 | 24 |

<!-- Page 553 -->

There were 25 carriers operating 37 service loops in 2004 employing 220 ships, an average of six ships per loop. The current conference, the Trans Atlantic Conference Agreement (TACA) operates between US ports, including the Gulf and Pacific, and northern Europe, including the UK and Ireland, Scandinavia and Baltic ports. In 2004 the TACA members provided 11 service strings covering 16 ports in Europe and 13 in the United States. Anyone can join this conference and there are no trade shares.

#### Western Europe to the Far East trade

This route covers the trade of northern Europe, stretching from Sweden down to St Nazaire in France, to the Far East, an enormous maritime area covering West Malaysia, Singapore, Thailand, Hong Kong, Philippines, Taiwan, South Korea, China and Japan. This was one of the first trades to be covered by a conference system, the Far East Freight Conference (FEFC), and in 2004 there were about 13 operators or consortia running about 400 ships on many different loops.

Three major operators in the Far East trade are the Grand Alliance, composed of NYK, Neptune Orient Lines and Hapag-Lloyd; the Global Alliance, consisting of MOL, OOCL, APL and MISC; and Maersk. The round-voyage time is over 60 days, requiring nine ships to provide a weekly sailing covering a full range of Asian ports, though a shorter service schedule using eight ships and fewer portcalls is often used. The major operators run separate weekly services direct to Japan and Korea, and to South East Asia. It is the large number of ships required to operate a regular service in this trade that necessitated the development of consortia. A typical round voyage (Figure 13.5) would involve calling at three European ports (e.g. Rotterdam, Southampton, and Hamburg), Singapore and eight or nine ports in South East Asia. The permutations are enormous, involving the option to stop off in the Middle East and the choice of which countries to visit in Asia.

#### Round-the-world services

A seemingly logical development was to fuse these three main liner routes into a single global service. In the early 1980s several operators took this step, of which the most important were Evergreen and United States Lines. Evergreen set up a service with 12 vessels in each direction around the world with a round trip of 80 days, providing a 10-day service frequency in each direction. This service was initially introduced with eight ships in September 1984, but it rapidly became apparent that the 10-day service compared unfavourably with the seven-day service operated by competitors, particularly on the North Atlantic. As a result, in 1985 the number of ships was increased to 11 in each direction, and then to 12, giving a weekly service with a round trip time of 77 days. The ships used on the service were G-class vessels of 2700 TEU which were then lengthened to 3428 TEU. Going westbound, after calling at the UK and north continent ports, vessels proceeded down the East Coast of North America through the Panama Canal to the US West Coast, Japan, the Far East and through the Suez Canal to the Mediterranean.

<!-- Page 554 -->

For some years DSR-Senator and Cho Yang ran a round-the-world service, but with the notable exception of Evergreen this method of operation attracted few operators and in the 1990s it became clear that the round-the-world service strategy faced two fundamental problems. First, the need to link services reduced flexibility over port calls, and balancing calls on the three routes added complexity. Second, the ships used on the arterial trades increased in size and the ships which could transit the Panama Canal became uncompetitive. The second problem will be removed when the development of the Panama Canal to handle bigger container-ships is completed.

#### The North-South liner routes

The North-South liner services cover the trade between the industrial centres of Europe, North America and the Far East and the developing countries of Latin America, Africa, Far East and Australasia. There is also an extensive network of services between the smaller economies, especially those in the Southern Hemisphere. These trades, which are listed in Table 13.6, have a very different character. Cargo volumes are much lower, with the many routes together accounting for only 21% of the container cargo volume in 2004. However, this understates the importance of these trades to the shipping business. With many more ports to visit and often less efficient port itineraries, they generate more business than the container volume suggests. Although most trades are now containerized, a considerable amount of break-bulk cargo still cannot be handled in containers, so the liner services are more varied. These trades are too extensive to review in detail, so we will concentrate on one example, the Europe to West Africa service.

**Figure 13.5** Service loop to Europe from Far East trade

*Transport time between ports in days*

| From/To | Rotterdam | Hamburg | Southampton |
| :--- | :---: | :---: | :---: |
| Jeddah | 8 | 11 | 14 |
| Port Kelang | 15 | 18 | 21 |
| Singapore | 16 | 19 | 22 |
| Ningbo | 22 | 25 | 28 |
| Shanghai | 22 | 25 | 28 |
| Pusan | 24 | 27 | 30 |
| Qingdao | 27 | 30 | 33 |
| Xingang | 29 | 32 | 35 |
| Dalian | 30 | 33 | 36 |

<!-- Page 555 -->

The Europe to West Africa trade operates between north-western Europe and the 18 countries of West Africa, stretching from Senegal down to Angola. Nigeria is comparatively rich, but many of the others are very poor with few ports and limited supporting transport infrastructure. European trade accounts for two-thirds of the seaborne traffic, with the remainder divided between the USA and a rapidly growing trade (footnote 31) to Asia. Southbound shipments include machinery, chemicals, transport equipment, iron and steel, machinery and various foodstuffs. The return cargo is principally composed of primary products and semi-manufactures such as cocoa, rubber, oilseeds, vegetable oil, cotton, petroleum products and non-ferrous metals. The volume of cargo southbound is higher than the volume northbound, which creates problems (footnote 32) fully utilizing the vessels.

In 2005 the main services were containerized, though ro-ros and MPP vessels continue to operate in the trade. These services tend to be more flexible than the deep-sea container services, varying the ships and services to meet the needs of the trade. For example, a typical service, shown in Figure 13.6, offers weekly container-ship sailings with less frequent break-bulk sailings. The ships load cargo in Europe at Felixstowe, Rotterdam, Antwerp, Hamburg and Le Havre. In West Africa the line offers shipment to virtually all major ports either direct or via a feeder system. The service in Figure 13.6 calls at Felixstowe, Antwerp and Le Havre in north-western Europe, whilst in West Africa the itinerary is Dakar, Abidjan, Lomé and Cotonou on the southbound leg, and Tema, Abidjan and Dakar on the northbound leg. To provide this service a fleet of five 1600 TEU containerships is used. Other services use break-bulk ships. For example, a service using six 660 TEU ro-ros offers sailings every 8 days, calling at 13 ports and carrying rolling stock and project cargo in addition to containers.

The imbalance of containerized cargo leaves the shipping line with empty containers to transport back to Europe, and strenuous efforts have been made to containerize return cargoes in order to utilize the container space on ships. On the West Africa to Europe leg the following commodities were containerized: coffee (bagged in containers), empty gas cylinders (returned for refilling), high-value veneers, ginger, cotton, and mail. Attempts to containerize cocoa were initially unsuccessful because the product sweats, while the large logs shipped from West Africa are not generally suitable for containerization. About two-thirds of the containers shipped out to West Africa thus travel back empty.

This is just one example of the North-South liner services. A sense of the way these services develop is given by the press release shown below:

*Launch of Africa Service*

Hapag-Lloyd is starting its new weekly service from Europe to South Africa in October 2006. The relevant organisation is already in place in South Africa. [The new service will not use] charter ships as originally planned, but after further studying the market, as a space charterer from Mediterranean Shipping Company (MSC), based in Geneva. As a result of the cooperation with MSC, we can offer our customers considerable service improvements with fixed day weekly sailings and refrigerated cargo capacity.

<!-- Page 556 -->

The South Africa Express service (SAX) will link the European ports [of] Felixstowe, Hamburg, Antwerp and Le Havre with Cape Town, Port Elizabeth and Durban. Transit time from Cape Town to Hamburg will be 18 days. The service will start with the first voyage from Felixstowe on Oct. 16th, the first north bound vessel will leave Durban on Oct. 29th.

Hapag-Lloyd has had its own organisation in South Africa with offices in Durban (footnote 33), Cape Town and Johannesburg since the beginning of July 2006.

**Figure 13.6** Typical North-South Liner service, Europe-West Africa Source: OTAL container services

<!-- Page 557 -->

#### Intraregional trades and feeder services

In addition to the deep-sea trades, the short-sea services are playing an increasingly important part in the business, especially for the distribution of containers brought into hubs such as Hong Kong, Singapore and Rotterdam. These have grown very rapidly as deep sea operators have moved to bigger ships and reduced their port calls, preferring to distribute cargo from base ports to out ports. Movement of cargoes between local ports is also growing rapidly in response to efforts by regional authorities, especially in Europe, to reduce congestion. Many of the short-sea trades use very small ships and voyages of only 3-4 days, but with the growth of cargo volumes a wide range of vessels of 1,500-2,000 TEU are being used in these trades and even some 3,000-4,000 TEU vessels.

#### The break-bulk liner services

In discussing the liner trades it is easy to forget that cargo does not fall neatly into general cargo and bulk and there are many borderline trades which do not fit easily into either system. For example, Tasman Orient Line provides transport for New Zealand's forestry exports. It uses thirteen 22,000 dwt MPP liners with a capacity of 350 containers and 10,000 dwt of break-bulk cargo, a speed of 16 knots and 25-35 tonne cranes. The cargoes they carry include containers, reefer containers, car parts, machinery, vehicles, steel products, pulp, paper, lumber, cars, earth-moving equipment and heavy lift cargoes up to 120 tonnes. The vessels operate between New Zealand and South and East Asia. Services like this tend to be very fluid, constantly adjusting to the cargo flow. This is just one of many small and highly specialized liner services which serve the borders of the liner trades.

### 13.6 THE LINER COMPANIES

The liner companies which operate the services we discussed in the previous section are the third element in the container market model shown in box 3 of Figure 13.1. They have to decide which services to operate, which ships to use and whether to buy their own ships, charter them in, or just buy space on another service. They must also market their services, negotiate service contracts and undertake all the administration involved in the provision of services and the invoicing and accounting. Unlike bulk shipping companies which have a relatively simple management structure in relation to their assets (typically two ships at sea for each person on shore), liner companies are generally more complex and the shore-staff ratio is closer to 40 persons per ship. There are currently about 250 companies offering liner services of one sort or another and they should be distinguished from the independent shipowners in box 4b of Figure 13.1 who invest in container-ships and charter them to liner companies. These companies do not offer liner services themselves, and have more in common with the bulk shipping companies discussed in Chapter 11. A list of the 20 largest liner companies is shown in Table 13.7.

<!-- Page 558 -->

**Table 13.7** Twenty largest container fleet operators 1980, 2001, 2005 (year end)

| Rank | 1980 Company | 1980 Ships | 1980 '000 TEU | 1980 Share (%) | 2001 Company | 2001 Ships | 2001 '000 TEU | 2001 Share (%) | 2005 Company | 2005 Ships | 2005 '000 TEU | 2005 Share (%) |
| :---: | :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: | :--- | :---: | :---: | :---: |
| 1 | Sea-Land | 63 | 70 | 9.6% | Maersk-SL + Safmarine | 297 | 694 | 9.4% | Maersk | 586 | 1,665 | 16.4% |
| 2 | Hapag Lloyd | 28 | 41 | 5.6% | P & O Nedlloyd | 138 | 344 | 4.6% | MSC | 276 | 784 | 7.7% |
| 3 | OCL | 16 | 31 | 4.3% | Evergreen Group | 129 | 325 | 4.4% | CMA-CGM | 242 | 508 | 5.0% |
| 4 | Maersk Line | 20 | 26 | 3.5% | Hanjin / Senator | 82 | 258 | 3.5% | Evergreen | 155 | 478 | 4.7% |
| 5 | M Line | 17 | 24 | 3.3% | Mediterranean Shg Co | 138 | 247 | 3.3% | Hapag-Lloyd | 131 | 412 | 4.1% |
| 6 | Evergreen Line | 22 | 24 | 3.2% | APL | 81 | 224 | 3.0% | China Shipping | 123 | 346 | 3.4% |
| 7 | OOCL | 17 | 23 | 3.1% | COSCO Container Lines | 113 | 206 | 2.8% | NOL/APL | 104 | 331 | 3.3% |
| 8 | Zim Container Line | - | 21 | 2.9% | NYK | 86 | 171 | 2.3% | Hanjin | 84 | 329 | 3.2% |
| 9 | US Line | 20 | 21 | 2.9% | CP Ships Group | 80 | 148 | 2.0% | COSCO | 126 | 322 | 3.2% |
| 10 | American President | 15 | 20 | 2.8% | CMA-CGM Group | 81 | 142 | 1.9% | NYK | 118 | 302 | 3.0% |
| 11 | Mitsui OSK | 16 | 20 | 2.7% | Mitsui-OSK Lines | 65 | 139 | 1.9% | Mitsui OSK | 80 | 241 | 2.4% |
| 12 | Farrell Lines | 13 | 16 | 2.3% | K Line | 62 | 136 | 1.8% | OOCL | 65 | 234 | 2.3% |
| 13 | Neptune Orient Lines | 11 | 15 | 2.0% | Zim | 75 | 132 | 1.8% | Sudamericana | 86 | 234 | 2.3% |
| 14 | Trans Freight Line | 17 | 14 | 1.9% | OOCL | 48 | 129 | 1.7% | K Line | 75 | 228 | 2.2% |
| 15 | CGM | 9 | 13 | 1.7% | Hapag-Lloyd Group | 32 | 116 | 1.6% | Zim | 85 | 201 | 2.0% |
| 16 | Yang Ming | 9 | 13 | 1.7% | Yang Ming Line | 45 | 113 | 1.5% | Yangming | 69 | 188 | 1.9% |
| 17 | Nedlloyd | 5 | 12 | 1.6% | China Shipping | 92 | 110 | 1.5% | Hamburg-Süd | 87 | 184 | 1.8% |
| 18 | Columbus Line | 13 | 11 | 1.5% | Hyundai | 32 | 106 | 1.4% | HMM | 39 | 148 | 1.5% |
| 19 | Safmarine | 5 | 11 | 1.5% | CSAV Group | 54 | 97 | 1.3% | PIL | 101 | 134 | 1.3% |
| 20 | Ben Line | 5 | 10 | 1.4% | Hamburg-Süd Group | 45 | 80 | 1% | Wan Hai | 68 | 114 | 1.1% |
| **Top 20** | | **348** | **437** | **60%** | | **1,775** | **3,917** | **53%** | | **2,700** | **7,387** | **73%** |
| **All Other Operators** | | **497** | **290** | **40%** | | **1,135** | **3,475** | **47%** | | **938** | **2,777** | **27%** |
| **World Fleet** | | **845** | **726** | **100%** | | **2,910** | **7,392** | **100%** | | **3,638** | **10,164** | **100%** |
| **Average market share top 20** | | | | **3.0%** | | | | **2.6%** | | | | **3.6%** |
| **Standard deviation top 20** | | | | **1.9%** | | | | **1.9%** | | | | **3.4%** |

*Source: Pearson and Farsey (1983, Table 9.1, p. 196), CRSL, Martin Stopford*

#### Liner company size

When containerization started, the high capital investment required resulted in consolidation of trades and many hundreds of small liner companies disappeared. However, following this initial period of change, the size profile of the container companies settled down. Table 13.7, which compares the market shares of the 20 largest container companies in 1980, 2001 and 2005, shows that between 1980 and 2001 the size profile hardly changed. In 1980 the biggest operator was Sea-Land with a market share of 9.6% and the other 19 big players had shares ranging from 1.4% to 5.6%, with an average share for the top 20 of 3%. By 2001 Maersk had become the biggest liner company, with a share of 9.4%, having taken over Sea-Land in the late 1990s. P&O Nedlloyd was second with a fleet share of 4.6% and at the bottom of the top 20 was Hamburg-Süd with a fleet share of 1%. In fact during this period the share of the top 20 companies fell from 60% to 53% so the business was not consolidating and the average company had a market share of only 2.6%.

<!-- Page 559 -->
"""

def main():
    content = STOPFORD_PATH.read_text(encoding="utf-8")
    
    start_marker = "TRANSPORT OF GENERAL CARGO\n\n<!-- Page 550 -->\n**Table 13.6**"
    end_marker = "<!-- Page 559 -->\nfor the top 20 of 3%. By 2001 Maersk had become the biggest liner company, with a share of 9.4%, having taken over Sea-Land in the late 1990s. P&O Nedlloyd was second with a fleet share of 4.6% and at the bottom of the top 20 was Hamburg-S"
    
    p1 = content.find(start_marker)
    p2 = content.find(end_marker)
    
    if p1 == -1 or p2 == -1:
        print(f"Error: markers not found (p1={p1}, p2={p2})")
        return
    
    # We want to replace from p1 to the end of the sentence on page 559
    # In old text, p2 points to the start of "<!-- Page 559 -->\nfor the top 20 of 3%..."
    # The sentence finishes at "...share of only 2.6%.\n"
    target_sentence_end = content.find("share of only 2.6%.\n", p2)
    if target_sentence_end == -1:
        print("Error: sentence end not found")
        return
    target_end = target_sentence_end + len("share of only 2.6%.\n")
    
    updated_content = content[:p1] + NEW_CH13_SECTION + content[target_end:]
    
    STOPFORD_PATH.write_text(updated_content, encoding="utf-8")
    KNOWLEDGE_PATH.write_text(updated_content, encoding="utf-8")
    print(f"Successfully updated {STOPFORD_PATH} and {KNOWLEDGE_PATH}")

if __name__ == "__main__":
    main()
