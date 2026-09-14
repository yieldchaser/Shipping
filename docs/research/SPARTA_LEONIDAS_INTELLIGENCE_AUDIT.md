# Sparta Commodities & Leonidas AI: Comprehensive Intelligence Dossier & Data Gap Audit

> **Date:** September 14, 2026  
> **Source Target:** `https://www.spartacommodities.com/leonidas/`  
> **Corporate Entity:** Sparta Commodities S.A. (Geneva, Switzerland)  
> **Entity Stage:** Venture-backed Scale-Up (\$42M Series B led by One Peak)  
> **Platform Category:** Oil & Commodities Trading Decision Engine  
> **Document Purpose:** Systematic architectural breakdown of Sparta's Leonidas AI, inventory of its data assets, and exhaustive gap analysis against the `yieldchaser/Shipping` repository.

---

## 1. Executive Summary: What is Leonidas AI?

**Sparta Commodities** was founded in 2020 by former physical oil traders (Felipe Elink Schuurman and Miles Moseley) with the objective of modernizing commodity trading desks and eliminating fragmented, error-prone manual spreadsheets ("Excel arb sheets").

On **September 7, 2026**, Sparta officially launched **Leonidas AI**, branded as the *"first decision-making engine for oil traders."*

Unlike generic foundation LLMs (ChatGPT, Claude, Gemini) that lack live market prices, proprietary forward curves, and trading math, **Leonidas AI is an agentic decision engine wired directly to Sparta's structured physical and financial market data**.

### Core Value Proposition
* **From "What Is" to "What It Means"**: Terminals (Bloomberg, LSEG) show historical or current prices; Leonidas evaluates whether a price move opens or shuts a physical trade route.
* **Stitching Curves, Freight, and Arbs**: It continuously computes delivered netback economics across global origin-destination corridors.
* **Automated Decision Alerts**: Triggers real-time alerts when market dislocations occur (e.g., *"Transatlantic diesel arb just flipped from shut to open"*).

---

## 2. Granular Breakdown: What Leonidas Covers Across Trading Desks

Leonidas is organized around five primary physical and derivative trading desks:

### 1. Crude Oil Desk
* **Instruments & Spreads**:
  * WTI Midland FOB Houston
  * WTI / Brent arbitrage spread
  * Brent / Dubai EFS (Exchange of Futures for Swaps)
  * Dated Brent vs prompt forward curve
* **Core Arbitrage Mechanics**:
  * Evaluates whether US Gulf Coast (USGC) crude clears **West** (to Europe/Rotterdam via Aframax) or **East** (to Asia/China via VLCC).
  * Continuously evaluates freight costs (VLCC TD3C vs Aframax TD25) against delivered refinery margins.

### 2. Distillates & Diesel Desk
* **Instruments & Spreads**:
  * NYMEX Heating Oil / ULSD
  * ICE Gasoil cracks
  * USGC diesel cash differentials
  * **HOGO Swap** (Heating Oil vs Gasoil spread)
* **Core Arbitrage Mechanics**:
  * Monitors the **transatlantic diesel arb** (US Gulf Coast $\rightarrow$ Europe).
  * Computes the landed netback on demand using HOGO conversion economics and clean tanker freight (TC14).

### 3. Gasoline Desk
* **Instruments & Spreads**:
  * Eurobob (EBOB) oxy / non-oxy barges (ARA)
  * RBOB / EBOB spread
  * Gasoline East/West spread
  * Gas/Naphtha blend economics
* **Core Arbitrage Mechanics**:
  * Tracks directional clearing: does the ARA gasoline barrel move **West to New York Harbor (NYH)** or **East to Pakistan / Arabian Gulf**?
  * Alerts desks when blending component economics (aromatics, alkylate, naphtha) flip.

### 4. Fuel Oil & Bunkers Desk
* **Instruments & Spreads**:
  * VLSFO (0.5% Sulphur) and HSFO (380 CST)
  * **Hi-5 Spread** (VLSFO minus HSFO)
  * Fuel oil cracks vs Brent
  * Rotterdam $\rightarrow$ Singapore East/West (E/W) arb
* **Core Arbitrage Mechanics**:
  * Tracks bunker demand across global hubs (Singapore, Rotterdam, Fujairah).
  * Calculates refinery coker/FCC economics and arbitrage viability between European supply and Asian bunker demand.

### 5. Freight Desk
* **Key Routes Tracked**:
  * **TD3C**: VLCC Middle East Gulf to China (Dirty)
  * **TD20**: Suezmax West Africa to UK-Continent (Dirty)
  * **TD25**: Aframax US Gulf to UK-Continent / cross-Med (Dirty)
  * **TC2**: Clean MR Continent to US Atlantic Coast (Clean)
  * **TC5**: Clean LR1 Middle East Gulf to Japan (Clean)
  * **TC14**: Clean MR US Gulf to Continent (Clean)
* **What Leonidas Does With Freight**:
  * Freight is treated as the **critical gatekeeper** of physical commodity flows.
  * Leonidas flags when a sudden Worldscale rate surge or vessel tonnage squeeze eliminates the profit margin on a commodity arbitrage before the trader fixes the vessel.

---

## 3. Exhaustive Data Audit: Does `yieldchaser/Shipping` Have This Data?

```
+====================================================================================+
|                                DATA COVERAGE AUDIT                                 |
+====================================================================================+
|  DOMAIN                          | SPARTA / LEONIDAS  | OUR PLATFORM   | STATUS    |
|----------------------------------+--------------------+----------------+-----------|
|  Dirty Tankers (VLCC, Suez, Afra)| TD3C, TD20, TD25   | Full Coverage  | PARITY    |
|  Clean Tankers (LR1, MR Routes)  | TC2, TC5, TC14     | Full Coverage  | PARITY    |
|  Bunker Fuels & Hi-5 Spreads     | Global Hubs, 12M   | 36M+ Rows, 12M | PARITY    |
|  Customs Crude & Cargo Flows     | USGC, ARA, AG      | EIA, Brazil    | OVERLAP   |
|  Dry Bulk & Raw Commodities      | NONE (0% Coverage) | World-Class    | OUR MOAT  |
|  Port Queues & Chokepoints       | Limited            | Deep Lineups   | OUR MOAT  |
|  Refined Product Paper Swaps     | EBOB, HOGO, Cracks | Minimal        | GAP       |
|  Live FOB Crude Differentials    | WTI Midland FOB    | Macro-level    | GAP       |
|  Automated Arb PnL Engine        | Live Calculator    | Manual Flow    | GAP       |
+====================================================================================+
```

### 1. Where We Have Full Parity or Superiority

#### A. Tanker Freight Rates (Dirty & Clean)
* **Our Files**:
  * `data/derived/tanker_forward_curves.csv`
  * `data/derived/tanker_forward_curves_history.csv`
  * `data/clarksons/gibson_tanker_rates_continuous_daily.csv`
  * `data/clarksons/fearnleys_benchmark_rates_continuous.csv`
* **Coverage**:
  * We track **VLCC TD3C, Suezmax TD20, Aframax TD25, Clean LR1 TC5, MR Triangulation (TC2 + TC14)**.
  * We model **Standard vs ECO vessel consumption differentials** across forward curves, which Sparta gates behind high enterprise subscription tiers.

#### B. Bunker Fuels & Hi-5 Spreads
* **Our Files**:
  * `data/bunkers/bunker_master_historical.csv` (36M+ historical lines)
  * `data/bunkers/bunker_forward_curves_12m.csv`
  * `data/bunkers/bunker_bix_macro_benchmarks.csv`
  * `data/bunkers/bunker_physical_sales_volumes.csv`
* **Coverage**:
  * We track VLSFO, HSFO (IFO 380), MGO, and Hi-5 spreads across Singapore, Rotterdam, Fujairah, Busan, Hong Kong, and Kaohsiung.
  * We have official MPA Singapore monthly delivery volumes, quarterly ARA sales, and Fujairah volumes.

---

### 2. Our Massive Moat (What We Have That Sparta Has 0% Of)

Sparta Commodities is **exclusively focused on liquid hydrocarbons (crude, refined oil products, clean/dirty tankers)**. They have **zero coverage** of the global dry bulk and industrial raw materials complex:

1. **Dry Bulk Freight Complex**:
   * Baltic Exchange Indices: BDI, BCI (Capesize), BPI (Panamax), BSI (Supramax), BHSI (Handysize).
   * SGX Dry Freight FFA settlement forward curves across all contract tenors.
   * ETF microstructures and daily basket holdings for **BDRY** and **BWET** (Amplify / Breakwave).
2. **Industrial Raw Materials & Agricultural Flows**:
   * **SGX Iron Ore Forward Term Structure**: Cleared curves for 62% Fe (FEF), 65% Carajás (M65F), and Platts Lump Premium (LPF) across 40 delivery months.
   * **Customs Trade Flows**: MDIC ComexStat Brazil iron ore, Australia Pilbara Port Hedland exports, Port of Newcastle thermal/met coal terminal exports, Guinea Conakry bauxite mirror shipments, USDA FAS export sales grain commitments.
3. **Physical Supply Chain Bottlenecks & Lineups**:
   * Live port lineups: Port Hedland, Tubarao, Newcastle, Ponta da Madeira.
   * Panama Canal Gatun Lake water levels, draft limits, and queue delays.
   * Global port stress matrix across 54 major dry and tanker terminals.

---

### 3. The Specific Gaps (What Sparta / Leonidas Has That We Don't)

If the goal is to match Sparta's refined products oil trading intelligence, here are our exact data gaps:

1. **Refined Product Paper Swaps & Intraday Cracks**:
   * We do not currently ingest:
     * **EBOB** gasoline barge paper swaps.
     * **HOGO** (Heating Oil vs ICE Gasoil) swap curves.
     * Naphtha cracks vs Brent.
     * Jet fuel regrade (Jet vs Gasoil).
2. **FOB Port Cash Differentials**:
   * While we track US EIA weekly PADD 3 crude exports, we do not have real-time physical assessments for **WTI Midland FOB Houston differential** over Cushing.
3. **The Automated Arbitrage Math Engine**:
   * Sparta's primary technical moat in Leonidas is the automated real-time physical arbitrage equation:
     $$\text{Arb Netback} = \text{Destination CIF} - \left(\text{Origin FOB} + \text{Freight Leg} + \text{Insurance/Loss} + \text{Canal Fees}\right)$$
   * Leonidas continuously calculates this delta across hundreds of permutations and pings the trader the moment $\text{Arb Netback} > \$0.00$.

---

## 4. Architectural Blueprint: How to Replicate "Leonidas" on Our Platform

We already possess the necessary foundational data (tanker freight rates, bunker prices, export customs series, and commodity forward curves). We can build an equivalent or superior **Automated Arbitrage & Trade Flow Engine**:

```mermaid
flowchart TD
    subgraph Data Layer
        FR[Tanker & Dry Freight Rates<br/>TD3C, TD20, TD25, C3, C5]
        BK[Bunker Fuel Spreads<br/>VLSFO, HSFO, MGO, Hi-5]
        CW[Cleared Forward Curves<br/>SGX Ore, Brent, Gasoil]
        FL[Trade Flows & Customs<br/>US EIA, MDIC, USDA FAS]
    end

    subgraph Arbitrage Engine
        MATH["Netback Calculation:<br/>Destination CIF - (Origin FOB + Freight + Bunkers + Canal)"]
        STATUS{"Is Margin > 0?"}
    end

    subgraph Decision Engine
        ALERT["Alert: Arb Window OPEN<br/>(Freight Gated)"]
        SHUT["Alert: Arb Window SHUT<br/>(Tonnage Squeeze)"]
        BRIEF["Daily Morning Briefing<br/>Corridor Netback Breakdown"]
    end

    Data Layer --> MATH
    MATH --> STATUS
    STATUS -- Yes --> ALERT
    STATUS -- No --> SHUT
    ALERT --> BRIEF
    SHUT --> BRIEF
```

### Recommended Implementation Steps:
1. **Define Core Arbitrage Corridors**:
   * **Crude**: USGC (Houston) $\rightarrow$ Rotterdam (Aframax TD25) vs USGC $\rightarrow$ Ningbo (VLCC TD3C).
   * **Dry Bulk Iron Ore**: Tubarao $\rightarrow$ Qingdao (C3 Capesize) vs Port Hedland $\rightarrow$ Qingdao (C5 Capesize).
   * **Grains**: US Gulf $\rightarrow$ China (S1C Supramax) vs Santos Brazil $\rightarrow$ China.
2. **Build the Automated Netback Calculator**:
   * Compute delivered landed cost in real time by subtracting freight and voyage bunker burn from destination delivered prices.
3. **Deploy Alerting & Narrative Synthesis**:
   * Add a "Trade Engine" card on our Signals and Cargo tabs that explicitly flags whether each route's arbitrage window is **OPEN**, **SHUT**, or **TIGHT**, with the exact freight rate that gates it.
