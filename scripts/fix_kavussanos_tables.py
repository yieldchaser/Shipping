#!/usr/bin/env python3
"""
Format tables 4.1, 8.1, 8.2 in The International Handbook of Shipping Finance (Book 8).
- Converts raw text blocks into clean GFM pipe tables with delimiters.
- Strips OCR running headers and page numbers.
- Heals fractured paragraphs across page boundaries.
- Resolves 'fi ' ligature splits (fi nancing -> financing).
- Syncs 1:1 to corpus/books and knowledge/docs/books.
"""

from pathlib import Path

CORPUS_PATH = Path("corpus/books/the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md")
KNOWLEDGE_PATH = Path("knowledge/docs/books/the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md")

TABLE_4_1 = """**Table 4.1** Islamic financing terms

| Term | Description |
| :--- | :--- |
| *Beial urbun* | Acceptable only to Hanbali school of Islamic jurisprudence, an Islamic option. Islamic investor purchases goods on behalf of real purchaser and keeps 10% of real purchaser's deposit |
| *Beibi salam / beibisalif* | Forward financing transactions to provide working capital to buy raw materials. *Salam* identifies the goods. *Salif* refers to goods in generic terms. The goods must exist at time of sale. Does not apply to shipbuilding |
| *Gharar* | Uncertainty: excessive uncertainty, risk or ambiguous outcome |
| *Ijara* | Equivalent to leasing. Bank purchases asset and rents to third party |
| *Ijara irta* | Lease purchase |
| *Istisna* | Islamic institution places order to build ships and sells at an agreed price at an agreed date |
| *Joalah* | Simply a fee for rendering a service |
| *Mudaraba* | A silent partnership fund that participants subscribe to; the bank manages the investment (i.e. trustee finance). A percentage of profits go to investor-customers. Bank charges fees. Shares in funds can be bought and sold |
| *Muqarada* | Bonds issued to finance projects |
| *Murabaha* | Cost-plus method for project financings, which includes an honest declaration of cost |
| *Musharaka* | A full partnership that provides venture capital by establishing a special purpose company. Bank and customer are shareholders and share profits and losses (i.e. equity financing) |
| *Riba* | "Increase, growth" (i.e. interest) |"""

SECTION_8_2 = """**Table 8.1** The most important export credit agencies for the maritime, cruise and offshore shipping sectors

| Area | Country | Export credit agencies |
| :--- | :--- | :--- |
| ASIA | Korea | Korea Trade Insurance Corporation (K-SURE) |
| ASIA | Korea | The Export-import Bank of Korea (KEXIM) |
| ASIA | China | China Export & Credit Insurance Corporation (SINOSURE) |
| ASIA | China | Export-import Bank of China (CEXIM) |
| ASIA | Japan | Nippon Export and Investment Insurance (NEXI) |
| ASIA | Japan | Japan Bank for International Cooperation (JBIC) |
| EU | Germany | Euler Hermes Kreditversicherungs-AG (HERMES) |
| EU | Norway | Norwegian Guarantee Institute for Export Credits (GIEK) |
| EU | France | Compagnie française d'Assurance pour le commerce extérieur (COFACE) |
| EU | Italy | SACE S.p.A. Servizi Assicurativi del Commercio Estero (SACE) |
| AUSTRALIA | Australia | Export Finance and Insurance Corporation (EFIC) |

#### 8.2.2  ECAs' Role in Ship Finance

Prior to the financial crisis and in particular during the period from 2000 to 2008, the role of ECAs in ship finance was rather limited. During that period traditional debt financing sources were readily available (on a large scale and attractively priced) from international as well as local shipping banks to fund shipowners' newbuilding projects. These banks were however adversely affected by the unprecedented events in the financial markets in 2008 as well as by the severe correction in freight rates and asset values in shipping.

As a result of the financial and shipping crisis, a number of shipping banks were faced with big problems in their shipping portfolios and increased regulatory (Basel III) constraints, which forced them to either scale down their lending or leave the industry altogether. The credit squeeze left a big funding gap for the shipping community, especially for shipping projects involving newbuilding vessels, which were still under construction. ECAs were quick to step in, providing a significant part of the necessary funding, either by extending direct funding to the shipowners or by issuing ECA guarantees/policies (assigned to the commercial banks) insuring commercial and/or political risks, managing, thus, to close that funding gap and supporting in that way their local shipbuilding activity.

Overall, during the last couple of years, as the availability of bank lending became tighter, the shipowning community has increased its interest in export credit finance. ECAs were there to meet this increased demand, and we have witnessed an important increase in lending volumes, particularly from ECAs of important shipbuilding nations such as Korea and China. The strong growth of ECA-backed financing is evident through figures published by *Seatrade Asia Week*, (footnote 1) which showed that the Chinese Export Import Bank (CEXIM) committed USD 14 billion in loans to the shipping industry, up from USD 12 billion in 2012 and USD 11 billion in 2011.

Export credit finance is at present considered an important source of capital for the shipping industry, especially for expensive and capital intensive maritime projects. Under the present conditions, commercial banks would find it difficult to commit to such expensive projects, thus we are seeing ECAs playing an increasingly important role for such "high-value" projects in the cruise, offshore, LNG, LPG as well as in the traditional sectors. Some examples of publicly reported ECA transactions that have been concluded in the recent past are provided in Table 8.2.

**Table 8.2** Examples of publicly reported export credit agency transactions concluded in the maritime, cruise and the offshore shipping sectors

| Sector | Shipping company | Amount | Export credit agency | Newbuilding project |
| :--- | :--- | :---: | :--- | :--- |
| Cruise | Norwegian Cruise Line (footnote 3) | USD 0.91B | EULER HERMES | 2 × Cruise vessels |
| Offshore | Ocean Rig (footnote 4) | USD 1.35B | GIEK & KEXIM | 3 × Deepwater drillships |
| Cruise | Royal Caribbean (footnote 5) | EUR 0.89B | COFACE | 1 × Mega-cruise vessel |
| Shipping | Scorpio Bulkers (footnote 6) | USD 0.23B | CEXIM | 7 × Capesize vessels |
| LNG | Nigeria LNG Ltd (footnote 7) | USD 0.72B | KEXIM & KSURE | 6 × LNG vessels |
| Cruise | Star Cruises (footnote 8) | EUR 0.60B | EULER HERMES | 1 × Cruise vessel |
| LPG | Dorian LPG (footnote 9) | USD 0.50B | KEXIM & KSURE | 18 × VLGC vessels |

#### 8.2.3  ECA Ship Financing Structures

ECA involvement in maritime projects takes predominately two forms. The shipowner will either raise funding from international commercial banks, on the back of a guarantee or an insurance policy issued by an ECA, or he or she will raise the funding directly from the ECA. Under the first scheme, the "ECA-guaranteed" financing structure, the ECA promotes and facilitates the export of a maritime asset by issuing a guarantee/insurance product. Foreign commercial banks extend the necessary financing (a term loan facility) to the overseas buyer/importer of the maritime asset being constructed on the back of this ECA guarantee/insurance policy. Under this arrangement, the commercial bank is effectively assured that it will receive payment, by the ECA, in the event of a payment default by the shipowner (provided of course that the policy's conditions and requirements are met), whether connected to any insolvency event, any other commercial event or in connection with any political event. Since the guarantee/insurance cover is backed by the ECA's government, the commercial bank's guaranteed exposure is no longer considered and treated as a shipping risk but rather as a sovereign risk. K-SURE in Korea, SINOSURE in China and NEXI in Japan are common providers of such ECA-guaranteed financing schemes."""

def main():
    content = CORPUS_PATH.read_text(encoding="utf-8")
    
    # 1. Replace Table 4.1 block
    t4_start = content.find("**Table 4.1  Islamic fi nancing terms**")
    t4_end_target = "## 4 Shipbuilding Finance\n\n117\n\n#### 4.1.27  Equity Financing"
    t4_end = content.find(t4_end_target)
    
    if t4_start != -1 and t4_end != -1:
        end_idx = t4_end + len(t4_end_target)
        replacement_4 = TABLE_4_1 + "\n\n#### 4.1.27  Equity Financing"
        content = content[:t4_start] + replacement_4 + content[end_idx:]
        print("Replaced Table 4.1 successfully")
    else:
        print(f"Warning: Table 4.1 markers not found (start={t4_start}, end={t4_end})")

    # 2. Replace Section 8.2 block (Tables 8.1, 8.2 and healed text)
    # Target from start of Table 8.1 to end of Section 8.2.3 sovereign risk sentence
    t8_start = content.find("**Table 8.1  The most important export credit agencies for the maritime, cruise and off-**")
    target_end_str = "K-SURE in\nKorea, SINOSURE in China and NEXI in Japan are common providers of\nsuch ECA-guaranteed fi nancing schemes."
    t8_end = content.find(target_end_str)
    
    if t8_start != -1 and t8_end != -1:
        # Also include the preceding paragraph up to "evident through fi gures published"
        pre_para = "Overall, during the last couple of years, as the availability of bank lend-\ning became tighter, the shipowning community has increased its interest in\nexport credit fi nance. ECAs were there to meet this increased demand, and\nwe have witnessed an important increase in lending volumes, particularly\nfrom ECAs of important shipbuilding nations such as Korea and China. The\nstrong growth of ECA-backed fi nancing is evident through fi gures published\n\n"
        pre_idx = content.find(pre_para)
        
        slice_start = pre_idx if pre_idx != -1 else t8_start
        slice_end = t8_end + len(target_end_str)
        
        content = content[:slice_start] + SECTION_8_2 + content[slice_end:]
        print("Replaced Section 8.2 / Tables 8.1 and 8.2 successfully")
    else:
        print(f"Warning: Section 8.2 markers not found (start={t8_start}, end={t8_end})")
        
    CORPUS_PATH.write_text(content, encoding="utf-8")
    KNOWLEDGE_PATH.write_text(content, encoding="utf-8")
    print("Synchronized Book 8 files.")

if __name__ == "__main__":
    main()
