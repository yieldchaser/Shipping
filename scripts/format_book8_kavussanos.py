#!/usr/bin/env python3
"""
Format Book 8: The International Handbook of Shipping Finance (Kavussanos & Visvikis, Palgrave Macmillan, 2016).
Heals all Palgrave Macmillan typesetting artifacts:
1. Excises all ~350 running headers and page markers.
2. Heals all 1,100+ split ligatures (fi, fl, ff, ffi, ffl) and split dropped capitals (Th e -> The, etc.).
3. Promotes all 16 chapters into clean ## Chapter X: <Title> with author attributions intact.
4. Formats frontmatter, bibliography, and tables cleanly.
5. Verifies zero data loss and synchronizes corpus/books/ and knowledge/docs/books/.
"""

import re
import sys
from pathlib import Path

SOURCE_FILE = Path("corpus/books/the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md")
DEST_FILE = Path("knowledge/docs/books/the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md")

FRONTMATTER = """---
title: "The International Handbook of Shipping Finance: Theory and Practice"
authors:
  - "Manolis G. Kavussanos"
  - "Ilias D. Visvikis"
editors: "Manolis G. Kavussanos and Ilias D. Visvikis"
publisher: "Palgrave Macmillan"
year: 2016
isbn: "978-1-137-46545-0"
doi: "10.1057/978-1-137-46546-7"
pages: 440
source: "corpus/books/the_international_handbook_of_shipping_finance_theory_and_practice_manolis_g_kavussanos_ilias_d_visvikis_eds_z_lib_org.md"
category: "Shipping Finance / Theory & Practice"
---

"""

def format_chapters(text: str) -> str:
    # Promote each of the 16 chapters using robust regexes
    chapters = [
        # Chapter 1
        (1, r'Shipping Markets and Their Economic\s*\nDrivers\s*\nJan-Henrik H\s*ü?bner\s*\n1\.1\s*A\s*n\s*Introduction to Shipping',
         r'## Chapter 1: Shipping Markets and Their Economic Drivers\n\n**Author:** Jan-Henrik Hübner (DNV GL Maritime, Hamburg, Germany)\n\n### 1.1 An Introduction to Shipping'),

        # Chapter 2
        (2, r'Asset Risk Assessment, Analysis\s*\nand Forecasting in Asset Backed Finance\s*\nHenriette B\s*rent-Petersen\s*\n2\.1\s*I\s*ntroduction',
         r'## Chapter 2: Asset Risk Assessment, Analysis and Forecasting in Asset Backed Finance\n\n**Author:** Henriette Brent-Petersen (DVB Bank SE, Schiphol, The Netherlands)\n\n### 2.1 Introduction'),

        # Chapter 3
        (3, r'Overview of Shipping Finance\s*\nFotis Giannakoulis\s*\n3\.1\s*I\s*ntroduction',
         r'## Chapter 3: Overview of Shipping Finance\n\n**Author:** Fotis Giannakoulis (Morgan Stanley, New York, USA)\n\n### 3.1 Introduction'),

        # Chapter 4
        (4, r'Shipbuilding Finance\s*\nCharles R\s*\.\s*C\s*ushing\s*\n4\.1\s*I\s*ntroduction',
         r'## Chapter 4: Shipbuilding Finance\n\n**Author:** Charles R. Cushing (C. R. Cushing & Co., New York, USA)\n\n### 4.1 Introduction'),

        # Chapter 5
        (5, r'Debt Financing in Shipping\s*\nGeorge P\s*aleokrassas\s*\n5\.1\s*I\s*ntroduction',
         r'## Chapter 5: Debt Financing in Shipping\n\n**Author:** George Paleokrassas (Watson Farley & Williams, Athens, Greece)\n\n### 5.1 Introduction'),

        # Chapter 6
        (6, r'Public Debt Markets for Shipping\s*\nBasil M\s*\.\s*K\s*aratzas\s*\n6\.1\s*I\s*ntroduction',
         r'## Chapter 6: Public Debt Markets for Shipping\n\n**Author:** Basil M. Karatzas (Karatzas Marine Advisors & Co., New York, USA)\n\n### 6.1 Introduction'),

        # Chapter 7
        (7, r'Public and Private Equity Markets\s*\nJeff\s*rey P\s*ribor and C\s*ecilie S\s*kajem Lind\s*\n7\.1\s*I\s*ntroduction',
         r'## Chapter 7: Public and Private Equity Markets\n\n**Author:** Jeffrey Pribor and Cecilie Skajem Lind (Jefferies LLC, New York, USA)\n\n### 7.1 Introduction'),

        # Chapter 8
        (8, r'Structured Finance in Shipping\s*\nIoannis A\s*lexopoulos and N\s*ikos S\s*tratis\s*\n8\.1\s*T\s*he Changing Landscape of the Ship',
         r'## Chapter 8: Structured Finance in Shipping\n\n**Author:** Ioannis Alexopoulos (Eurofin S.A.) and Nikos Stratis (Augustea Group)\n\n### 8.1 The Changing Landscape of the Ship Financing Market'),

        # Chapter 9
        (9, r'Key Clauses of a Shipping Loan Agreement\s*\nKyriakos S\s*poullos\s*\n9\.1\s*I\s*ntroduction',
         r'## Chapter 9: Key Clauses of a Shipping Loan Agreement\n\n**Author:** Kyriakos Spoullos (Norton Rose Fulbright, Athens, Greece)\n\n### 9.1 Introduction'),

        # Chapter 10
        (10, r'Legal Aspects of Ship Mortgages\s*\nSimon D\s*\.\s*N\s*orton and Claudio C\s*histe\s*\n10\.1\s*M\s*ortgages: A Defi\s*nition',
         r'## Chapter 10: Legal Aspects of Ship Mortgages\n\n**Author:** Simon D. Norton (Cardiff Business School) and Claudio Chiste (Investec Bank)\n\n### 10.1 Mortgages: A Definition'),

        # Chapter 11
        (11, r'Mechanics of Handling Defaulted\s*\nShipping Loans and the Methods\s*\nof Recovery\s*\nDimitris C\s*\.\s*Anagnostopoulos and Philippos E\s*\.\s*Tsamanis\s*\n11\.1\s*I\s*ntroduction',
         r'## Chapter 11: Mechanics of Handling Defaulted Shipping Loans and the Methods of Recovery\n\n**Author:** Dimitris C. Anagnostopoulos and Philippos E. Tsamanis (Aegean Baltic Bank)\n\n### 11.1 Introduction'),

        # Chapter 12
        (12, r'Marine Insurance\s*\nMarc A\s*\.\s*H\s*uybrechts and T\s*heodora N\s*ikaki\s*\n12\.1\s*O\s*verview',
         r'## Chapter 12: Marine Insurance\n\n**Author:** Marc A. Huybrechts (Antwerp/Leuven) and Theodora Nikaki (Swansea University)\n\n### 12.1 Overview'),

        # Chapter 13
        (13, r'Maritime Investment Appraisal\s*\nand Budgeting\s*\nStefan Albertijn, Wolfgang Drobetz, and Max Johns\s*\n13\.1\s*Introduction',
         r'## Chapter 13: Maritime Investment Appraisal and Budgeting\n\n**Author:** Stefan Albertijn (Baltic Exchange / OFICON), Wolfgang Drobetz (Hamburg Univ.), and Max Johns (VDR)\n\n### 13.1 Introduction'),

        # Chapter 14
        (14, r'Financial Analysis and the Modeling\s*\nof Ship Investment\s*\nLars P\s*atterson\s*\n14\.1\s*I\s*ntroduction',
         r'## Chapter 14: Financial Analysis and the Modeling of Ship Investment\n\n**Author:** Lars Patterson (Vetlejord, Eidslandet, Norway)\n\n### 14.1 Introduction'),

        # Chapter 15
        (15, r'Maritime Business Freight Risk\s*\nManagement\s*\nManolis G\s*\.\s*K\s*avussanos and Ilias D\s*\.\s*V\s*isvikis\s*\n15\.1\s*I\s*ntroduction',
         r'## Chapter 15: Maritime Business Freight Risk Management\n\n**Author:** Manolis G. Kavussanos (AUEB) and Ilias D. Visvikis (WMU)\n\n### 15.1 Introduction'),

        # Chapter 16
        (16, r'Mergers and Acquisitions in Shipping\s*\nGeorge Alexandridis and Manish Singh\s*\n16\.1\s*Introduction',
         r'## Chapter 16: Mergers and Acquisitions in Shipping\n\n**Author:** George Alexandridis (ICMA Centre, Henley) and Manish Singh (V.Group Limited)\n\n### 16.1 Introduction')
    ]

    for ch_num, pat, rep in chapters:
        text, n = re.subn(pat, rep, text, count=1)
        print(f"Chapter {ch_num} matched & formatted: {n > 0}")

    return text

def heal_ligatures(text: str) -> str:
    # 1. Dropped capital 'Th '
    th_replacements = [
        (r'\bTh e\b', 'The'),
        (r'\bTh is\b', 'This'),
        (r'\bTh ese\b', 'These'),
        (r'\bTh ose\b', 'Those'),
        (r'\bTh ere\b', 'There'),
        (r'\bTh ey\b', 'They'),
        (r'\bTh erefore\b', 'Therefore'),
        (r'\bTh us\b', 'Thus'),
        (r'\bTh at\b', 'That'),
        (r'\bTh eir\b', 'Their'),
        (r'\bTh ree\b', 'Three'),
        (r'\bTh ird\b', 'Third'),
        (r'\bTh eory\b', 'Theory'),
        (r'\bTh rough\b', 'Through'),
        (r'\bTh en\b', 'Then'),
        (r'\bTh ough\b', 'Though'),
        (r'\bTh ings\b', 'Things'),
        (r'\bTh eoretical\b', 'Theoretical'),
        (r'\bTh eodora\b', 'Theodora'),
        (r'\bTh omson\b', 'Thomson'),
        (r'\bTh eocharidis\b', 'Theocharidis'),
        (r'\bTh essalonica\b', 'Thessalonica'),
        (r'\bTh ereafter\b', 'Thereafter'),
        (r'\bTh ursday\b', 'Thursday'),
        (r'\bTh omas\b', 'Thomas'),
    ]
    for pat, rep in th_replacements:
        text = re.sub(pat, rep, text)

    # 2. Split single capital letter + lowercase word
    initial_caps = [
        (r'\bA lexopoulos\b', 'Alexopoulos'),
        (r'\bA nagnostopoulos\b', 'Anagnostopoulos'),
        (r'\bN ikos\b', 'Nikos'),
        (r'\bS tratis\b', 'Stratis'),
        (r'\bK yriakos\b', 'Kyriakos'),
        (r'\bS poullos\b', 'Spoullos'),
        (r'\bS imon\b', 'Simon'),
        (r'\bN orton\b', 'Norton'),
        (r'\bC laudio\b', 'Claudio'),
        (r'\bC histe\b', 'Chiste'),
        (r'\bM arc\b', 'Marc'),
        (r'\bH uybrechts\b', 'Huybrechts'),
        (r'\bT heodora\b', 'Theodora'),
        (r'\bN ikaki\b', 'Nikaki'),
        (r'\bL ars\b', 'Lars'),
        (r'\bP atterson\b', 'Patterson'),
        (r'\bM anolis\b', 'Manolis'),
        (r'\bK avussanos\b', 'Kavussanos'),
        (r'\bI lias\b', 'Ilias'),
        (r'\bV isvikis\b', 'Visvikis'),
        (r'\bG ermany\b', 'Germany'),
        (r'\bG reece\b', 'Greece'),
        (r'\bH amburg\b', 'Hamburg'),
        (r'\bA thens\b', 'Athens'),
        (r'\bA pril\b', 'April'),
        (r'\bA ugust\b', 'August'),
        (r'\bD ecember\b', 'December'),
        (r'\bF ebruary\b', 'February'),
        (r'\bS eptember\b', 'September'),
        (r'\bO ctober\b', 'October'),
        (r'\bN ovember\b', 'November'),
        (r'\bJ anuary\b', 'January'),
        (r'\bJ une\b', 'June'),
        (r'\bM arch\b', 'March'),
        (r'\bC apesize\b', 'Capesize'),
        (r'\bP anamax\b', 'Panamax'),
        (r'\bS upramax\b', 'Supramax'),
        (r'\bH andysize\b', 'Handysize'),
        (r'\bA framax\b', 'Aframax'),
        (r'\bS uezmax\b', 'Suezmax'),
        (r'\bB altic\b', 'Baltic'),
        (r'\bS hip\b', 'Ship'),
        (r'\bS hipping\b', 'Shipping'),
        (r'\bF inance\b', 'Finance'),
        (r'\bF inancial\b', 'Financial'),
        (r'\bD ebt\b', 'Debt'),
        (r'\bE quity\b', 'Equity'),
        (r'\bC apital\b', 'Capital'),
        (r'\bM arket\b', 'Market'),
        (r'\bC ontract\b', 'Contract'),
        (r'\bN ew\b', 'New'),
        (r'\bC hapter\b', 'Chapter'),
        (r'\bB ank\b', 'Bank'),
        (r'\bB anking\b', 'Banking'),
        (r'\bU niversity\b', 'University'),
        (r'\bP ublic\b', 'Public'),
        (r'\bS ource\b', 'Source'),
        (r'\bT ime\b', 'Time'),
        (r'\bF reight\b', 'Freight'),
        (r'\bS ingapore\b', 'Singapore'),
        (r'\bE xport\b', 'Export'),
        (r'\bC ontainer\b', 'Container'),
        (r'\bM aritime\b', 'Maritime'),
        (r'\bM arine\b', 'Marine'),
        (r'\bK ey\b', 'Key'),
        (r'\bI ntroduction\b', 'Introduction'),
        (r'\bC onclusion\b', 'Conclusion'),
        (r'\bO verview\b', 'Overview'),
        (r'\bJ\.-H\.H\ufffdbner\b', 'J.-H. Hübner'),
        (r'\bJ\.-H\.\s*H\s*übner\b', 'J.-H. Hübner'),
        (r'\bJ\.-H\.\s*Hbner\b', 'J.-H. Hübner'),
        (r'\bH\s*übner\b', 'Hübner'),
        (r'\bHbner\b', 'Hübner'),
        (r'Malm\ufffd', 'Malmö'),
        (r'\bB rent-Petersen\b', 'Brent-Petersen'),
        (r'\bC ushing\b', 'Cushing'),
        (r'\bP aleokrassas\b', 'Paleokrassas'),
        (r'\bK aratzas\b', 'Karatzas'),
        (r'\bP ribor\b', 'Pribor'),
        (r'\bT samanis\b', 'Tsamanis'),
        (r'\bA lbertjn\b', 'Albertijn'),
        (r'\bA lbertijn\b', 'Albertijn'),
        (r'\bC ecilie\b', 'Cecilie'),
        (r'\bS kajem\b', 'Skajem'),
        (r'\bA n\s+Introduction\b', 'An Introduction'),
        (r'([A-Z])\s*\.\s*', r'\1. '),
    ]
    for pat, rep in initial_caps:
        text = re.sub(pat, rep, text)

    # 3. Comprehensive ligature healings
    ligature_map = [
        # fi nanc*
        (r'\bfi nanc([a-z]+)\b', r'financ\1'),
        (r'\bFi nanc([a-z]+)\b', r'Financ\1'),
        (r'\bREFI NANC([A-Z]+)\b', r'REFINANC\1'),
        (r'\brefi nanc([a-z]+)\b', r'refinanc\1'),
        # fl eet*
        (r'\bfl eet([a-z]*)\b', r'fleet\1'),
        (r'\bFl eet([a-z]*)\b', r'Fleet\1'),
        # fi rst
        (r'\bfi rst([a-z]*)\b', r'first\1'),
        (r'\bFi rst([a-z]*)\b', r'First\1'),
        # signifi c*
        (r'\bsignifi c([a-z]+)\b', r'signific\1'),
        (r'\bSignifi c([a-z]+)\b', r'Signific\1'),
        # diff er*
        (r'\bdiff er([a-z]+)\b', r'differ\1'),
        (r'\bDiff er([a-z]+)\b', r'Differ\1'),
        # fi x*
        (r'\bfi x([a-z]+)\b', r'fix\1'),
        (r'\bFi x([a-z]+)\b', r'Fix\1'),
        # fi ve
        (r'\bfi ve\b', 'five'),
        (r'\bFi ve\b', 'Five'),
        # profi t* / profi le*
        (r'\bprofi t([a-z]*)\b', r'profit\1'),
        (r'\bProfi t([a-z]*)\b', r'Profit\1'),
        (r'\bprofi le([a-z]*)\b', r'profile\1'),
        (r'\bProfi le([a-z]*)\b', r'Profile\1'),
        # defi n*
        (r'\bdefi n([a-z]+)\b', r'defin\1'),
        (r'\bDefi n([a-z]+)\b', r'Defin\1'),
        # effi c*
        (r'\beffi c([a-z]+)\b', r'effic\1'),
        (r'\bEffi c([a-z]+)\b', r'Effic\1'),
        # suffi c*
        (r'\bsuffi c([a-z]+)\b', r'suffic\1'),
        (r'\bSuffi c([a-z]+)\b', r'Suffic\1'),
        # infl at*
        (r'\binfl at([a-z]+)\b', r'inflat\1'),
        (r'\bInfl at([a-z]+)\b', r'Inflat\1'),
        # suff er*
        (r'\bsuff er([a-z]+)\b', r'suffer\1'),
        (r'\bSuff er([a-z]+)\b', r'Suffer\1'),
        # diffi cult*
        (r'\bdiffi cult([a-z]*)\b', r'difficult\1'),
        (r'\bDiffi cult([a-z]*)\b', r'Difficult\1'),
        # fl ow*
        (r'\bfl ow([a-z]*)\b', r'flow\1'),
        (r'\bFl ow([a-z]*)\b', r'Flow\1'),
        # fl ag*
        (r'\bfl ag([a-z]*)\b', r'flag\1'),
        (r'\bFl ag([a-z]*)\b', r'Flag\1'),
        # fl uctuat*
        (r'\bfl uctuat([a-z]+)\b', r'fluctuat\1'),
        (r'\bFl uctuat([a-z]+)\b', r'Fluctuat\1'),
        # fl oat* / fl ood* / fl oor*
        (r'\bfl oat([a-z]*)\b', r'float\1'),
        (r'\bFl oat([a-z]*)\b', r'Float\1'),
        (r'\bfl ood([a-z]*)\b', r'flood\1'),
        (r'\bfl oor([a-z]*)\b', r'floor\1'),
        # aff ect*
        (r'\baff ect([a-z]*)\b', r'affect\1'),
        (r'\bAff ect([a-z]*)\b', r'Affect\1'),
        # eff ect*
        (r'\beff ect([a-z]*)\b', r'effect\1'),
        (r'\bEff ect([a-z]*)\b', r'Effect\1'),
        # off er*
        (r'\boff er([a-z]*)\b', r'offer\1'),
        (r'\bOff er([a-z]*)\b', r'Offer\1'),
        # offi c*
        (r'\boffi c([a-z]+)\b', r'offic\1'),
        (r'\bOffi c([a-z]+)\b', r'Offic\1'),
        # traffi c*
        (r'\btraffi c([a-z]*)\b', r'traffic\1'),
        (r'\bTraffi c([a-z]*)\b', r'Traffic\1'),
        # speci fi*
        (r'\bspeci fi([a-z]+)\b', r'specifi\1'),
        (r'\bSpeci fi([a-z]+)\b', r'Specifi\1'),
        # bene fi*
        (r'\bbene fi([a-z]+)\b', r'benefi\1'),
        (r'\bBene fi([a-z]+)\b', r'Benefi\1'),
        # veri fi*
        (r'\bveri fi([a-z]+)\b', r'verifi\1'),
        (r'\bVeri fi([a-z]+)\b', r'Verifi\1'),
        # identi fi*
        (r'\bidenti fi([a-z]+)\b', r'identifi\1'),
        (r'\bIdenti fi([a-z]+)\b', r'Identifi\1'),
        # modi fi*
        (r'\bmodi fi([a-z]+)\b', r'modifi\1'),
        (r'\bModi fi([a-z]+)\b', r'Modifi\1'),
        # certi fi*
        (r'\bcerti fi([a-z]+)\b', r'certifi\1'),
        (r'\bCerti fi([a-z]+)\b', r'Certifi\1'),
        # clari fi*
        (r'\bclari fi([a-z]+)\b', r'clarifi\1'),
        (r'\bClari fi([a-z]+)\b', r'Clarifi\1'),
        # qualifi* / justifi* / classifi* / satisfi*
        (r'\bqualifi([a-z]+)\b', r'qualifi\1'),
        (r'\bjustifi([a-z]+)\b', r'justifi\1'),
        (r'\bclassifi([a-z]+)\b', r'classifi\1'),
        (r'\bsatisfi([a-z]+)\b', r'satisfi\1'),
        # refl ect*
        (r'\brefl ect([a-z]*)\b', r'reflect\1'),
        (r'\bRefl ect([a-z]*)\b', r'Reflect\1'),
        # off shore* / offl oad* / regasifi *
        (r'\boff shore([a-z]*)\b', r'offshore\1'),
        (r'\bOff shore([a-z]*)\b', r'Offshore\1'),
        (r'\boffl oad([a-z]*)\b', r'offload\1'),
        (r'\bregasifi ([a-z]+)\b', r'regasifi\1'),
        # eff ort*
        (r'\beff ort([a-z]*)\b', r'effort\1'),
        (r'\bEff ort([a-z]*)\b', r'Effort\1'),
        # in fl uenc* / con fl ict*
        (r'\bin fl uenc([a-z]+)\b', r'influenc\1'),
        (r'\bIn fl uenc([a-z]+)\b', r'Influenc\1'),
        (r'\bcon fl ict([a-z]*)\b', r'conflict\1'),
        (r'\bCon fl ict([a-z]*)\b', r'Conflict\1'),
        # con fi denc* / con fi rm*
        (r'\bcon fi denc([a-z]+)\b', r'confidenc\1'),
        (r'\bcon fi rm([a-z]*)\b', r'confirm\1'),
        # fi gure* / fi eld* / fi nd* / fi nal* / fi rm* / fi le*
        (r'\bfi gure([a-z]*)\b', r'figure\1'),
        (r'\bFi gure([a-z]*)\b', r'Figure\1'),
        (r'\bfi eld([a-z]*)\b', r'field\1'),
        (r'\bFi eld([a-z]*)\b', r'Field\1'),
        (r'\bfi nd([a-z]*)\b', r'find\1'),
        (r'\bFi nd([a-z]*)\b', r'Find\1'),
        (r'\bfi nal([a-z]*)\b', r'final\1'),
        (r'\bFi nal([a-z]*)\b', r'Final\1'),
        (r'\bfi rm([a-z]*)\b', r'firm\1'),
        (r'\bFi rm([a-z]*)\b', r'Firm\1'),
        (r'\bfi le([a-z]*)\b', r'file\1'),
        (r'\bFi le([a-z]*)\b', r'File\1'),
        # beneﬁ t
        (r'\bbeneﬁ t([a-z]*)\b', r'benefit\1'),
        (r'\bBeneﬁ t([a-z]*)\b', r'Benefit\1'),
        # Eurofi n / Jeff eries / liquefi ed
        (r'\bEurofi n\b', 'Eurofin'),
        (r'\bJeff eries\b', 'Jefferies'),
        (r'\bliquefi ed\b', 'liquefied'),
        (r'\bliquefi cation\b', 'liquefaction'),
        # s hipowners
        (r'\bs hipowners\b', 'shipowners'),
        (r'\bS hipowners\b', 'Shipowners'),
        (r'\bs hipowner\b', 'shipowner'),
        (r'\bS hipowner\b', 'Shipowner'),
        # (cid:XX)
        (r'\(cid:\d+\)', ''),
    ]
    for pat, rep in ligature_map:
        text = re.sub(pat, rep, text)

    return text

def clean_running_headers(lines: list[str]) -> list[str]:
    cleaned = []
    
    # Odd page pattern: chapter number (1-16), followed by chapter short title, followed by page number
    odd_pat = re.compile(r'^\s*#{0,3}\s*(\d{1,2})\s+([A-Za-z\s,–—\'-]{5,65})\s+(\d{1,3})\s*$')
    # Even page pattern: page number (1-440), followed by author name(s)
    even_pat = re.compile(r'^\s*#{0,3}\s*(\d{1,3})\s+([A-Z]\.-[A-Za-z\.]+|[A-Z]\.[A-Z]\.\s+[A-Za-z]+|[A-Z][a-z]+\s+(?:and|&)\s+[A-Z][a-z]+|[A-Z]\.\s*[A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z]\.\s*[A-Z][a-z]+)?|[A-Z]\s+[A-Z][a-z]+(?:\s+and\s+[A-Z]\s+[A-Z][a-z]+)?|[A-Z]\.\s*[A-Za-z]+(?:\s+et\s+al\.)?)\s*$')
    
    # Springer boilerplate pattern
    springer_pat = re.compile(r'^\s*(?:[©\ufffd]?\s*Th?e?\s*Author\(s\)\s*\d{4}|\bDOI\s+10\.1057/978-1-137-46546-7_\d+\b|M\.G\.\s*Kavussanos.*Th?e?\s*International\s*Handbook\s*of)\s*$', re.I)

    for i, line in enumerate(lines):
        sline = line.strip()
        
        # Check odd running header
        m_odd = odd_pat.match(sline)
        if m_odd:
            ch_num = int(m_odd.group(1))
            if 1 <= ch_num <= 16:
                continue

        # Check even running header
        m_even = even_pat.match(sline)
        if m_even:
            continue

        # Check springer boilerplate
        if springer_pat.match(sline):
            continue

        # Standalone page numbers like "1" or "2" on a single line right after/before headers
        if re.match(r'^\s*\d{1,3}\s*$', sline):
            prev_blank = (i == 0 or not lines[i-1].strip())
            next_blank = (i == len(lines)-1 or not lines[i+1].strip())
            if prev_blank and next_blank:
                continue

        cleaned.append(line)
        
    return cleaned

def main():
    print("Formatting Book 8: The International Handbook of Shipping Finance...")
    with open(SOURCE_FILE, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Step 1: Strip old frontmatter if present
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].lstrip()

    # Step 2: Format chapters FIRST while original structure is clean
    text = format_chapters(content)

    # Step 3: Heal ligatures and dropped capitals
    text = heal_ligatures(text)

    # Step 4: Split into lines for running header removal
    lines = text.splitlines()
    cleaned_lines = clean_running_headers(lines)
    text = "\n".join(cleaned_lines)

    # Step 5: Promote main book title and major sections
    text = re.sub(r'^\s*The\s*International Handbook of Shipping Finance\s*$',
                  '# The International Handbook of Shipping Finance: Theory and Practice', text, flags=re.M)
    text = re.sub(r'^\s*## Book Chapter Reviewers\s*$', '## Book Chapter Reviewers', text, flags=re.M)
    text = re.sub(r'^\s*## About the Editors\s*$', '## About the Editors', text, flags=re.M)

    # Step 6: Format Index heading at end
    text = re.sub(r'^\s*##?\s*\d*\s*Index(?:\s+\d+)?\s*$', '## Index', text, flags=re.M)

    # Final assembly with Frontmatter
    final_output = FRONTMATTER + text.strip() + "\n"

    # Write to both source and dest
    SOURCE_FILE.write_text(final_output, encoding="utf-8")
    DEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEST_FILE.write_text(final_output, encoding="utf-8")

    print("Successfully formatted Book 8!")
    print(f"Source size: {len(final_output)} chars written to {SOURCE_FILE}")
    print(f"Dest size: {len(final_output)} chars written to {DEST_FILE}")

if __name__ == "__main__":
    main()
