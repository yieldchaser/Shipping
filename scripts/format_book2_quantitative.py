#!/usr/bin/env python3
"""
scripts/format_book2_quantitative.py
Complete, clean formatter for Book 2:
Quantitative modelling of shipping freight rates: developments in the past 20 years
"""

import re
import subprocess
from pathlib import Path

def format_book2():
    p = Path("corpus/books/2022_quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.md")
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:corpus/books/2022_quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.md"],
            text=True,
            encoding="utf-8"
        )
    except Exception:
        raw = p.read_text(encoding="utf-8")

    # Preserve YAML frontmatter
    parts = raw.split("---", 2)
    fm = f"---{parts[1]}---\n"
    body = parts[2].lstrip("\r\n")

    # Clean out repeated publisher boilerplates and journal headers
    # Strip Summary block at top if it duplicates title/cite info
    body = re.sub(r"## Summary\s*\n.*?(?=\n## MARITIME|\n## Maritime|\n1\.|\Z)", "", body, flags=re.S)
    body = re.sub(r"## Maritime Policy & Management\s*\n.*?(?=\n## MARITIME|\n1\.|\Z)", "", body, flags=re.S)
    body = re.sub(r"## MARITIME POLICY & MANAGEMENT\s*\n", "", body)
    
    # Strip contact / copyright blocks
    body = re.sub(r"CONTACT Qing Liu[^\n]*\n[^\n]*\n© 2022 Informa UK Limited[^\n]*\n", "", body)
    body = re.sub(r"Full Terms & Conditions of access and use can be found at\s*\nhttps://[^\n]*\n", "", body)
    body = re.sub(r"Submit your article to this journal\s*\nView related articles\s*\nView Crossmark data\s*\n", "", body)

    # Clean Title, Authors, Affiliations and Abstract/Keywords block
    # Match the header block up to 1. Introduction
    header_pattern = (
        r"https://doi\.org/10\.1080/03088839\.2022\.2138595\s*\n"
        r"Quantitative modelling of shipping freight rates: developments in\s*\n"
        r"the past 20 years\s*\n"
        r"Luqi Kea, Qing Liu a, Adolf K\.Y\. Ng b,d and Wenming Shi c\s*\n"
        r"aFaculty of Business Administration.*?"
        r"ABSTRACT KEYWORDS\s*\n"
        r"(.*?)\s*\n"
        r"1\. Introduction"
    )
    header_match = re.search(header_pattern, body, re.S)
    if header_match:
        abstract_full = header_match.group(1).strip()
        # Separate abstract text from keywords
        # Abstract: "Understanding the determination mechanism... in this field."
        # Keywords: "Ocean shipping; freight rate; quantitative modelling; time series; cross-sectional dynamics; collaboration network"
        keywords = "Ocean shipping; freight rate; quantitative modelling; time series; cross-sectional dynamics; collaboration network"
        
        abstract_clean = (
            "Understanding the determination mechanism and dynamics of shipping freight rates has significant "
            "implications for practitioners, economists, and regulators of maritime transport. This paper systematically "
            "reviews the relevant papers on shipping freight rate published between 2000 and 2019. Specifically, it provides "
            "empirical insights including the major influencing factors of shipping freight rates and differences among "
            "the shipping sectors, and discusses the dominant methods and their applicability, strengths and weaknesses, "
            "and opportunities for new methods. Furthermore, the omissions and limitations in methods are explored to "
            "identify the research gaps and set a future research agenda. It is found that there is a strong focus on "
            "temporal dynamics with a wide range of modelling methods applied, while discussion on cross-sectional "
            "dynamics on how shipping freight rates are determined by vessel characteristics, contract terms, market "
            "competition, etc., is limited. Besides, the collaboration network analysis shows that more knowledge sharing "
            "and cross-discipline collaboration efforts can create potential for more inspired insights with advanced "
            "methods in this field."
        )
        
        clean_header = (
            "# Quantitative Modelling of Shipping Freight Rates: Developments in the Past 20 Years\n\n"
            "**Authors**: Luqi Ke, Qing Liu, Adolf K.Y. Ng, and Wenming Shi  \n"
            "**Journal**: *Maritime Policy & Management* (2022), DOI: 10.1080/03088839.2022.2138595  \n\n"
            "## Abstract\n\n"
            f"{abstract_clean}\n\n"
            f"**Keywords**: {keywords}\n\n"
            "---\n\n"
            "## 1. Introduction\n\n"
        )
        body = re.sub(header_pattern, clean_header, body, flags=re.S)

    # Strip running headers and heal cross-page sentences
    # 2 L. KE ET AL.
    body = re.sub(r"\n\s*2\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # 4 L. KE ET AL.
    body = re.sub(r"\n\s*4\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # 6 L. KE ET AL.
    body = re.sub(r"\n\s*6\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # 8 L. KE ET AL.
    body = re.sub(r"\n\s*8\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # 10 L. KE ET AL.
    body = re.sub(r"\n\s*10\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # 12 L. KE ET AL.
    body = re.sub(r"\n\s*12\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # 14 L. KE ET AL.
    body = re.sub(r"\n\s*14\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # 16 L. KE ET AL.
    body = re.sub(r"\n\s*16\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # 18 L. KE ET AL.
    body = re.sub(r"\n\s*18\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)
    # General running header pattern just in case
    body = re.sub(r"\n\s*\d+\s+L\.\s*KE\s+ET\s+AL\.\s*\n", "\n", body)

    # Heal split sentences
    # "...two-level market structure, that is,\nthe 'upper'..."
    body = re.sub(
        r"two-level market structure, that is,\s*\n\s*the ‘upper’",
        "two-level market structure, that is, the ‘upper’",
        body
    )
    # "...Furthermore, only\nfew studies used..."
    body = re.sub(
        r"Furthermore, only\s*\n\s*few studies used",
        "Furthermore, only few studies used",
        body
    )
    # "...while\ncontainer shipping carriers..."
    body = re.sub(
        r"solid or liquid forms organized based on each individual shipment, while\s*\n\s*container shipping carriers",
        "solid or liquid forms organized based on each individual shipment, while container shipping carriers",
        body
    )
    # "...issues in\nparameter estimation..."
    body = re.sub(
        r"issues in\s*\n\s*parameter estimation",
        "issues in parameter estimation",
        body
    )
    # "...Alizadeh,\nNomikos, and Kavussanos..."
    body = re.sub(
        r"for example, Alizadeh,\s*\n\s*Nomikos, and Kavussanos",
        "for example, Alizadeh, Nomikos, and Kavussanos",
        body
    )
    # "...despite its weaknesses in parameter\nestimation..."
    body = re.sub(
        r"despite its weaknesses in parameter\s*\n\s*estimation and interpretability",
        "despite its weaknesses in parameter estimation and interpretability",
        body
    )

    # Section headings promotion
    sections = [
        (r"(?:\n|^)2\.\s+Research method\s*\n", "\n\n## 2. Research Method\n\n"),
        (r"(?:\n|^)2\.1\.\s+Search methodology\s*\n", "\n\n### 2.1 Search Methodology\n\n"),
        (r"(?:\n|^)2\.2\.\s+Inclusion/exclusion criteria\s*\n", "\n\n### 2.2 Inclusion/Exclusion Criteria\n\n"),
        (r"(?:\n|^)2\.3\.\s+Basic overview and next steps towards in-depth analysis\s*\n", "\n\n### 2.3 Basic Overview and Next Steps Towards In-Depth Analysis\n\n"),
        (r"(?:\n|^)3\.\s+Research objectives and models\s*\n", "\n\n## 3. Research Objectives and Models\n\n"),
        (r"(?:\n|^)3\.1\.\s+Research objectives\s*\n", "\n\n### 3.1 Research Objectives\n\n"),
        (r"(?:\n|^)3\.2\.\s+Quantitative models\s*\n", "\n\n### 3.2 Quantitative Models\n\n"),
        (r"(?:\n|^)3\.2\.1\.\s+Overview of models\s*\n", "\n\n#### 3.2.1 Overview of Models\n\n"),
        (r"(?:\n|^)3\.2\.2\.\s+Models by research objectives\s*\n", "\n\n#### 3.2.2 Models by Research Objectives\n\n"),
        (r"(?:\n|^)4\.\s+Determination of shipping freight rates\s*\n", "\n\n## 4. Determination of Shipping Freight Rates\n\n"),
        (r"(?:\n|^)4\.1\.\s+Disparity across shipping sectors\s*\n", "\n\n### 4.1 Disparity Across Shipping Sectors\n\n"),
        (r"(?:\n|^)4\.2\.\s+Influence of vessel characteristics and contract terms\s*\n", "\n\n### 4.2 Influence of Vessel Characteristics and Contract Terms\n\n"),
        (r"(?:\n|^)5\.\s+Time series characteristics of shipping freight rates\s*\n", "\n\n## 5. Time Series Characteristics of Shipping Freight Rates\n\n"),
        (r"(?:\n|^)5\.1\.\s+Stationarity\s*\n", "\n\n### 5.1 Stationarity\n\n"),
        (r"(?:\n|^)5\.2\.\s+Seasonality and cycles\s*\n", "\n\n### 5.2 Seasonality and Cycles\n\n"),
        (r"(?:\n|^)5\.3\.\s+Volatility clustering\s*\n", "\n\n### 5.3 Volatility Clustering\n\n"),
        (r"(?:\n|^)6\.\s+Research collaborations\s*\n", "\n\n## 6. Research Collaborations\n\n"),
        (r"(?:\n|^)7\.\s+Conclusion\s*\n", "\n\n## 7. Conclusion\n\n"),
        (r"(?:\n|^)7\.1\.\s+Trends and achievements\s*\n", "\n\n### 7.1 Trends and Achievements\n\n"),
        (r"(?:\n|^)7\.2\.\s+Gaps and future directions\s*\n", "\n\n### 7.2 Gaps and Future Directions\n\n"),
        (r"(?:\n|^)Note\s*\n", "\n\n## Note\n\n"),
        (r"(?:\n|^)Acknowledgments\s*\n", "\n\n## Acknowledgments\n\n"),
        (r"(?:\n|^)Disclosure statement\s*\n", "\n\n## Disclosure Statement\n\n"),
        (r"(?:\n|^)Funding\s*\n", "\n\n## Funding\n\n"),
        (r"(?:\n|^)ORCID\s*\n", "\n\n## ORCID\n\n"),
        (r"(?:\n|^)References\s*\n", "\n\n## References\n\n"),
    ]
    for pattern, replacement in sections:
        body = re.sub(pattern, replacement, body)

    # Figures as clean blockquotes
    body = re.sub(
        r"Figure 1\.\s*Distribution of articles per year versus BDI[^\n]*\n",
        "\n> **Figure 1**: Distribution of articles per year versus BDI (Source of BDI: Clarksons Research 2020).\n\n",
        body
    )
    body = re.sub(
        r"Figure 2\.\s*Number of papers per research objectives\.\s*\n",
        "\n> **Figure 2**: Number of papers per research objectives.\n\n",
        body
    )
    body = re.sub(
        r"Figure 3\.\s*Co-authorship network[^\n]*\n",
        "\n> **Figure 3**: Co-authorship network (Nodes and edges are weighted according to the frequency of appearance).\n\n",
        body
    )
    body = re.sub(
        r"Figure 4\.\s*Institutional collaboration network[^\n]*\n",
        "\n> **Figure 4**: Institutional collaboration network (Nodes and edges are weighted according to the frequency of appearance).\n\n",
        body
    )

    # Table 1: Distribution of articles in journals
    table1_raw = (
        r"Table 1\. Distribution of articles in journals\.\s*\n"
        r"Journal Number of papers Percentage\s*\n"
        r"Maritime Economics & Logistics 26 15\.48%\s*\n"
        r"Maritime Policy & Management 25 14\.88%\s*\n"
        r"Transportation Research Part E: Logistics and Transportation Review 25 14\.88%\s*\n"
        r"The Asian Journal of Shipping and Logistics 8 4\.76%\s*\n"
        r"Journal of Transport Economics and Policy 6 3\.57%\s*\n"
        r"Physica A-Statistical Mechanics and Its Applications 6 3\.57%\s*\n"
        r"International Journal of Shipping and Transport Logistics 6 3\.57%\s*\n"
        r"Energy Economics 5 2\.98%\s*\n"
        r"Applied Economics 5 2\.98%\s*\n"
        r"International Journal of Transport Economics 5 2\.98%\s*\n"
        r"Transportation Research Part A: Policy and Practice 5 2\.98%\s*\n"
        r"Expert Systems with Applications 3 1\.79%\s*\n"
        r"Explorations in Economic History 2 1\.19%\s*\n"
        r"International Journal of Forecasting 2 1\.19%\s*\n"
        r"Economic Modelling 2 1\.19%\s*\n"
        r"Journal of Transport Geography 2 1\.19%\s*\n"
        r"Journal of Futures Markets 2 1\.19%\s*\n"
        r"Top 17 journals total 135 80\.36%\s*\n"
        r"Other 33 journals 33 19\.64%\s*\n"
    )
    table1_clean = (
        "### Table 1: Distribution of Articles in Journals\n\n"
        "| Journal | Number of Papers | Percentage |\n"
        "| :--- | :---: | :---: |\n"
        "| Maritime Economics & Logistics | 26 | 15.48% |\n"
        "| Maritime Policy & Management | 25 | 14.88% |\n"
        "| Transportation Research Part E: Logistics and Transportation Review | 25 | 14.88% |\n"
        "| The Asian Journal of Shipping and Logistics | 8 | 4.76% |\n"
        "| Journal of Transport Economics and Policy | 6 | 3.57% |\n"
        "| Physica A: Statistical Mechanics and Its Applications | 6 | 3.57% |\n"
        "| International Journal of Shipping and Transport Logistics | 6 | 3.57% |\n"
        "| Energy Economics | 5 | 2.98% |\n"
        "| Applied Economics | 5 | 2.98% |\n"
        "| International Journal of Transport Economics | 5 | 2.98% |\n"
        "| Transportation Research Part A: Policy and Practice | 5 | 2.98% |\n"
        "| Expert Systems with Applications | 3 | 1.79% |\n"
        "| Explorations in Economic History | 2 | 1.19% |\n"
        "| International Journal of Forecasting | 2 | 1.19% |\n"
        "| Economic Modelling | 2 | 1.19% |\n"
        "| Journal of Transport Geography | 2 | 1.19% |\n"
        "| Journal of Futures Markets | 2 | 1.19% |\n"
        "| **Top 17 journals total** | **135** | **80.36%** |\n"
        "| Other 33 journals | 33 | 19.64% |\n\n"
    )
    body = re.sub(table1_raw, table1_clean, body)

    # Table 2: Summary of common methods
    table2_pattern = (
        r"Table 2\. Summary of common methods\.\s*\n"
        r"Method First introduced in Number of papers.*?"
        r"Support vector machine \(SVM\) 1995 1\s*\n"
    )
    table2_clean = (
        "### Table 2: Summary of Common Quantitative Methods\n\n"
        "| Category | Method | First Introduced | Number of Papers |\n"
        "| :--- | :--- | :---: | :---: |\n"
        "| Classic Econometric Model | Linear Regressions | 1886 | 14 |\n"
        "| Classic Econometric Model | Autoregressive Moving Average (ARMA) | 1951 | 6 |\n"
        "| Classic Econometric Model | Autoregressive Integrated Moving Average (ARIMA) | 1970 | 15 |\n"
        "| Classic Econometric Model | ARCH-type | 1982 | 37 |\n"
        "| Classic Econometric Model | Vector Autoregression (VAR) | 1980 | 33 |\n"
        "| Classic Econometric Model | Vector Error Correction Model (VECM) | 1995 | 25 |\n"
        "| Classic Econometric Model | Structural Equation Model (SEM) | 1960s | 3 |\n"
        "| Theoretical Model | Equilibrium Model | 1870s | 8 |\n"
        "| Simulation | System Dynamics (SD) Simulation | 1958 | 5 |\n"
        "| Other Data-Driven Mathematical Approach | Empirical Mode Decomposition (EMD) | 1998 | 7 |\n"
        "| Other Data-Driven Mathematical Approach | Multifractal Detrended Fluctuation Analysis (MF-DFA) | 2002 | 5 |\n"
        "| Other Data-Driven Mathematical Approach | Rescaled Range Analysis | 1951 | 7 |\n"
        "| Other Data-Driven Mathematical Approach | Stochastic Differential Equation (SDE) | 1942 | 6 |\n"
        "| Other Data-Driven Mathematical Approach | Wavelet Transform | 1984 | 3 |\n"
        "| Machine Learning | Artificial Neural Network (ANN) | 1964 | 12 |\n"
        "| Machine Learning | Support Vector Machine (SVM) | 1995 | 1 |\n\n"
    )
    body = re.sub(table2_pattern, table2_clean, body, flags=re.S)

    # Table 3: Forecast performance comparisons among models
    # Clean up the note / description of Table 3
    table3_pattern = (
        r"Table 3\. Forecast performance comparisons among models\.\s*\n"
        r"Note: This table reports the forecast performance.*?"
        r"FNN, fuzzy\s*\nneural network\.\s*\n"
    )
    table3_clean = (
        "### Table 3: Forecast Performance Comparisons Among Models\n\n"
        "> **Note on Table 3**: This table reports the forecast performance of models evaluated across reviewed literature. "
        "Forecast error measurements include Mean Absolute Deviation (MAD), Mean Absolute Error (MAE), "
        "Mean Absolute Percentage Error (MAPE), Median Relative Absolute Error (MdRAE), Mean Error (ME), "
        "Mean Percentage Error (MPE), Mean Squared Error (MSE), Normalized Root Mean Squared Error (NRMSE), "
        "Root Mean Squared Error (RMSE), and Standard Deviation of Error (SDE).  \n"
        "> **Model Acronyms**: RW (Random Walk), EGARCH (Exponential GARCH), TGARCH (Threshold GARCH), "
        "APGARCH (Asymmetric Power ARCH), IGARCH (Integrated GARCH), CGARCH (Component GARCH), "
        "GJR-GARCH (Glosten-Jagannathan-Runkle GARCH), GARCH-M (GARCH-in-mean), ARIMARCH (Hybrid ARIMA + ARCH), "
        "BPNN (Back Propagation Neural Network), RBFNN (Radial Basis Function Neural Network), "
        "ELM (Extreme Learning Machine), DFN (Dynamic Fluctuation Network), AGA (Adaptive Genetic Algorithm), "
        "MNN (Modular Neural Network), GFNN (Generalized Feedforward Neural Network), "
        "PCANN (Principal Components Analysis Neural Network), SOFM (Self-Organizing Feature Map), "
        "MLP (Multi-Layer Perceptron), FTS (Fuzzy Time Series), FNN (Fuzzy Neural Network).\n\n"
    )
    body = re.sub(table3_pattern, table3_clean, body, flags=re.S)

    # Table 4: Summary of common factors
    table4_pattern = (
        r"Table 4\. Summary of common factors\.\s*\n"
        r"Frequency of factors.*?"
        r"Note: Only papers with multivariate models are counted in this table\.\s*\n"
    )
    table4_clean = (
        "### Table 4: Summary of Common Influencing Factors by Shipping Sector\n\n"
        "| Category | Variable | Dry Bulk (44 papers) | Tanker (26 papers) | Container (17 papers) |\n"
        "| :--- | :--- | :---: | :---: | :---: |\n"
        "| **Demand** | Seaborne trade volume | 5 (11.4%) | 6 (23.1%) | 8 (47.1%) |\n"
        "| | General trade volume | 4 (9.1%) | 2 (7.7%) | 1 (5.9%) |\n"
        "| | Transport distance | 1 (2.3%) | 1 (3.8%) | 6 (35.3%) |\n"
        "| | Commodity production | 4 (9.1%) | 3 (11.5%) | 0 (0.0%) |\n"
        "| | Commodity prices | 8 (18.2%) | 17 (65.4%) | 1 (5.9%) |\n"
        "| | Trade imbalance | 0 (0.0%) | 0 (0.0%) | 3 (17.6%) |\n"
        "| **Supply** | Fleet capacity | 14 (31.8%) | 4 (15.4%) | 5 (29.4%) |\n"
        "| | Number of ships | 1 (2.3%) | 3 (11.5%) | 1 (5.9%) |\n"
        "| | Ship order | 3 (6.8%) | 3 (11.5%) | 1 (5.9%) |\n"
        "| | Ship delivery / newbuild | 0 (0.0%) | 5 (19.2%) | 1 (5.9%) |\n"
        "| | Ship demolition | 1 (2.3%) | 7 (26.9%) | 1 (5.9%) |\n"
        "| | Maximum vessel size | 0 (0.0%) | 0 (0.0%) | 2 (11.8%) |\n"
        "| | Ship price | 6 (13.6%) | 4 (15.4%) | 1 (5.9%) |\n"
        "| | Ship age | 4 (9.1%) | 2 (7.7%) | 0 (0.0%) |\n"
        "| | Market competition | 0 (0.0%) | 1 (3.8%) | 4 (23.5%) |\n"
        "| | Port condition | 1 (2.3%) | 0 (0.0%) | 4 (23.5%) |\n"
        "| | Connectivity | 0 (0.0%) | 0 (0.0%) | 3 (17.6%) |\n"
        "| | Service frequency | 0 (0.0%) | 0 (0.0%) | 2 (11.8%) |\n"
        "| **Macroeconomic Indicators** | Oil price | 11 (25.0%) | 17 (65.4%) | 5 (29.4%) |\n"
        "| | Stock market indicator | 9 (20.5%) | 2 (7.7%) | 1 (5.9%) |\n"
        "| | GDP | 3 (6.8%) | 0 (0.0%) | 3 (17.6%) |\n"
        "| | Industrial production | 4 (9.1%) | 1 (3.8%) | 0 (0.0%) |\n"
        "| | Interest rate | 2 (4.5%) | 3 (11.5%) | 0 (0.0%) |\n"
        "| | Currency exchange rate | 4 (9.1%) | 0 (0.0%) | 0 (0.0%) |\n\n"
        "*Note: Only papers with multivariate models are counted in this table.*\n\n"
    )
    body = re.sub(table4_pattern, table4_clean, body, flags=re.S)

    # Format References
    if "## References" in body:
        pre_ref, ref_part = body.split("## References", 1)
        # Separate joined citations that lost newlines during PDF extraction
        joined_names = [
            "Chistè, C.",
            "Jane Jing, X.",
            "Koekebakker, S.",
            "Köhn, S.",
            "Márquez-Ramos, L.",
            "Nielsen, P.",
            "Población, J. 2017.",
            "Población, J., and G. Serna.",
            "Suárez-Alemán, A.",
            "Uyar, K.",
            "Wee, Bert",
        ]
        for name in joined_names:
            ref_part = ref_part.replace(f" {name}", f"\n{name}")

        # Split citations by newline followed by an author surname or institution
        c_pattern = r"\n(?=[^\W\d_][\w\s\-]+?,\s+[A-Z]\.|\bBaltic Exchange|\bClarksons Research|\bUNCTAD|\bWee, Bert)"
        raw_cites = [re.sub(r"\s+", " ", c).strip() for c in re.split(c_pattern, ref_part) if c.strip()]
        
        citations = []
        for c in raw_cites:
            c_clean = c.lstrip("- ").strip()
            if c_clean:
                citations.append(f"- {c_clean}")

        body = pre_ref.strip() + "\n\n## References\n\n" + "\n".join(citations) + "\n"

    # Clean whitespace
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Final document assembly
    doc = fm + "\n" + body + "\n"

    p.write_text(doc, encoding="utf-8")
    dest = Path("knowledge/docs/books/2022_quantitativemodellingofshippingfreightratesdevelopmentsinthepast20years.md")
    dest.write_text(doc, encoding="utf-8")
    print(f"Book 2 formatted successfully: {len(doc)} chars, {len(doc.splitlines())} lines written to {p} and {dest}")

if __name__ == "__main__":
    format_book2()
