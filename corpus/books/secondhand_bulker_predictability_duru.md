---
title: "Predictability of Second-Hand Bulk Carriers with a Novel Hybrid Algorithm - Duru, Gulay, Girgin"
author: "Okan Duru, Emrah Gulay, Sinem Celik Girgin"
journal: "The Asian Journal of Shipping and Logistics"
year: 2021
accepted_date: "2021-07-21"
pages: 10
source: "corpus/books/secondhand_bulker_predictability_duru.md"
raw_pdf: "corpus/books/secondhand_bulker_predictability_duru.pdf"
category: "Maritime Economics / Econometric Forecasting / Asset Play / Machine Learning"
vessel_classes:
  - capesize
  - panamax
  - handymax
  - supramax
  - handysize
models_evaluated:
  - ARDL
  - EMD
  - ANN
  - ARIMA
  - Holt-Winters
  - ETS
  - TBATS
  - regARIMA
  - VAR
---

<!-- Page 2 -->

# journal homepage: www.elsevier.com/locate/ajsl

# The Asian Journal of Shipping and Logistics

# Contents lists available at ScienceDirect

# HOSTED BY
ELSEVIER

# The Asian Journal of Shipping and Logistics

# Predictability of second-hand bulk carriers with a novel hybrid algorithm

Okan Duru a, Emrah Gulay b, Sinem Celik Girgin c,∗

\( ^{a} \)  Research & Development, Ocean Dynamex Inc., Ottawa, ON, Canada

b Department of Econometrics, Dokuz Eylul University, Turkey

c Maritime and Logistics Management Department, University of Tasmania-Australian Maritime College, Launceston, Australia

# ARTICLE INFO

Article history:
Received 29 January 2021
Received in revised form 2 July 2021
Accepted 21 July 2021

Keywords:
Investment timing
Predictability
Lead-lag structure
Shipping Q index

# ABSTRACT

This paper investigates the predictability of the asset prices of commodity transport (i.e. dry bulk carriers) by testing the shipping Q index as a leading indicator. We employ a comprehensive back-testing procedure with a broad spectrum of benchmark simulations. The shipping Q index (an adaptation of Tobin's Q index) has been introduced to benchmark models to observe predictive gain and interpret predictability features. This study presents a novel hybrid model to forecast time series data. The forecasting ability of the proposed hybrid algorithm is compared to specific univariate time series models, dynamic models, nonlinear models, and widely used hybrid models in the literature. The findings document that not only the proposed hybrid model performs better than the other competitive models in terms of hold out sample forecasting, but also using the shipping Q index improves the forecast accuracy by remarkably reducing forecasting error.

© 2021 The Author. Production and hosting by Elsevier B.V. This is an open access article under the CC BY-NC-ND license (http://creativecommons.org/licenses/by-nc-nd/4.0/).

# 1. Introduction

Dry cargo ships are designed and operated in this supply chain for centuries. Based on the cargo capacity of ships, there are four major size groups namely Handysize (20k–45k dwt \( ^{1} \) ), Handymax (45k–60k dwt), Panamax \( ^{2} \)  (60k–90k dwt) and Capesize (90k + dwt, mostly 120k–150k). Two primary raw materials, iron ore and coal (both coking coal and steam coal) are usually carried on Capesize bulk carriers over 120k metric tons of parcel size. Investors in the shipping business need to allocate large amounts of capital on acquiring new and second-hand assets (i.e. ships) to employ in major commodity trades and gain revenue streams in operating income (based on freight rate). However, ships are not only cash-generating units through operating income, but their asset value may also cause gain/loss in oscillating ship markets. In this regard, the 'asset play' strategy (revenues on buy-sell spread) is an essential component of the portfolio management in the shipping corpora-

tions, and it is contingent upon the investment timing (i.e. temporal arbitrage) by its nature similar to conventional financial assets.

The revenue model of ship owning business has two major income streams: (1) Operating revenue from chartering operations and (2) impairment gains generated from changes in ship prices. The latter component of the revenue model can lead to a massive gain or loss due to the investment/divestment timing and the quality of asset value monitoring. Ship prices in the Capesize tonnage can be anywhere between USD 30–140 million considering the asset market of the last few decades, and asset prices may undergo intense volatility at the gain/loss of over USD 50 million. In June 2008, a large Capesize (120k + metric ton capacity) was sold at USD 140 million, and the same asset was priced at just USD 40 million in November 2008. An investment in June 2008 has lost USD 100 million through impairment in such a short period of time. That level of value has never returned back as of the data of this paper (January 2020). In this regard, asset value monitoring is now an essential part of portfolio management in ship investments. It is also a critical factor in the bank credit analysis as the ship mortgages which are usually monitored through the minimum security value covenant against asset value shortfall (Duru, 2018, p. Chapter 8) and financial auditors pay particular attention as a major source of impairment losses.

According to a study conducted at the Harvard Business School (Greenwood and Hanson, 2015), shipping asset prices are significantly predictable due to the mistiming of investments as the

* Corresponding author.

E-mail address: sinemcelikgirgin@utas.edu.au (S.C. Girgin).

\( ^{1} \)  Deadweight tonnage (dwt) refers to the carrying capacity including cargo, fuel, water or crew. Particularly in larger ship size, dwt is almost the cargo carrying capacity.

\( ^{2} \)  Literally it means the maximum size that can pass through Panama Canal.

https://doi.org/10.1016/j.ajsl.2021.07.002

2092-5212 © 2021 The Author. Production and hosting by Elsevier B.V. This is an open access article under the CC BY-NC-ND license (http://creativecommons.org/licenses/by-nc-nd/4.0/).

<!-- Page 3 -->

# Nomenclature

| \( \omega_{\zeta_{sARDL},k} \) | intrinsic mode functions of the residual obtained from the ARDL model which has the minimum Root Mean Square Error (RMSE) and Mean Absolute Error (MAE) in validation set |
| **---** | |
| \( \omega_{\zeta_m} \) | represents the vector of intrinsic mode functions of the residuals in training set |
| \( \omega_{\zeta_v} \) | represents the vector of intrinsic mode functions of the residuals in validation set |
| \( \xi'_{pARDL} \) | represents the shipping Q index from training set to be used in ARDL model's estimation |
| \( \xi_a \) | the shipping Q index |
| \( \zeta'_{eARDL} \) | residuals from the ARDL model |
| \( \zeta_m \) | represents the usage of training set in the algorithm |
| \( \zeta_t \) | represents the usage of test set in the algorithm |
| \( \zeta_\nu \) | represents the usage of validation set in the algorithm |
| \( h_1 \) | the number of hidden nodes in the first hidden layer |
| \( h_2 \) | the number of hidden nodes in the second hidden layer |
| k | the number of intrinsic mode functions of the residual |
| n | the length of training period |

notion of cobweb theory. The rigidity of the supply of shipping services is led by the period needed to build and deliver new cargo-carrying capacity to the fleet, and the time lag between the investor's decision and the realisation of the investment (delivery of ships) cause the cobweb structure. To support this argument, Celik Girgin et al. (2019) introduced an index, Shipping Q (SQ), to the literature to measure investment timing performance through market entry-exit decisions. This paper investigated the SQ index as a potential predictor of the asset prices of seaborne commodity carriers. Our theoretical proposition postulates that the SQ index can be utilised as a leading indicator of asset mispricing. Eventually, it can improve the predictive accuracy of future asset prices generated by forecasting models. An empirical study has been designed to observe the predictive gain in a spectrum of methodologies with the baseline benchmarks, excluding the leading indicator for comparative analysis. Empirical results validated the incremental improvements in predictive accuracy by the introduction of the leading indicator in a given set of predictive models for bulk carriers with various age and vessel profiles. It is also a prognostic outcome as machine learning, and empirical mode decomposition (EMD) usually outperform univariate benchmarks.

This paper investigated the SQ index in terms of investment timing in counter-cyclical asset play through parametric methodologies in predictive analytics. The significance of the index for bulk carriers was tested by incremental improvements in predictive accuracy comparing to benchmarks in post-sample test data. Empirical results validated the incremental improvements in predictive accuracy by the introduction of the SQ index in a given set of predictive models for bulk carriers with various age and vessel profiles.

# 2. Literature review

Forecasting models and their application to the financial and commodity markets are commonly found in the literature, whereas, studies on the predictability of the ship investment timing, either second-hand or new building, are relatively limited in the literature (Karlis et al., 2019). We briefly referred to exist-

ing studies on ship investment timing and broadly explained the benchmark methods in the forecasting literature.

# 2.1. Ship investment literature

In the maritime economics literature, the studies after the 1990s widely focus on ship investment decision-making processes and developing a more in-depth insight into the predictability of the market. Girgin et al. (2018) emphasized the recent literature investigates ship investment decision with various techniques and approaches. There are some seminal papers in the maritime literature, which would be referred to as the fundamental studies worked on investment modelling. For example, Dikos and Marcus (2003) worked on the valuation of second-hand dry bulks by utilising a model derived from the real options approach (ROA) to understand the second-hand ship investment decision process from 1976 to 2002. They elaborated the model to analyse second-hand vessels prices with the prices of new vessels and the charter rates. Their findings showed that second-hand ships prices comprise hidden asset play value. Following their study, Tsolakis et al. (2003) also studied the valuation of second-hand tankers and dry bulks over the period of 1960 and 2001 with the Error Correction Model. Along with Dikos and Marcus (2003), they emphasised a further insight about the pricing of second-hand vessels and stated that each vessel segment, based on their tonnage, corresponds to the market changes in a different way.

Some scholars contributed to the predictability of the shipping markets with investment timing studies. Alizadeh and Nomikos (2007) analysed the investment decision through the price to earnings ratio of the SH dry bulk ships. They mainly developed a cointegration approach to identify the investment and divestment timings. Merikas et al. (2008) elaborated a study to address decision-making in the second-hand tanker market directly and using a ratio (second-hand price to newbuilding price) to predict the market. Among these studies and in the literature, analysing the predictability of the shipping industry-specific index is a rare application.

More recently, strategic investment policies analysed by various models as the importance of investment timing and understanding the market dynamics to keep sustainable industrial growth. ROA applied to container shipping by Rau and Spinler (2016) to reveal optimal investment policies. Kou and Luo (2018) study also utilized the ROA approach to investigate the trigger rates (a certain level of freight rate) to optimize ship investments. The cyclical nature of the container shipping market studied by Jeon et al. (2020) with a novel method. They applied the system dynamics model, which was developed by Forrester (1958) for modelling and predicting industrial cycles, to reveal dynamic patterns of the container market.

From early literature to up-to-date, studies on ship investments expand from using static market price analysis to complex modelling to optimize ship investments. Recent studies scientifically proved the role of using advanced methods to interpret dynamic market data.

# 2.2. Forecasting literature

In this section, the forecasting literature part was divided into three folds. The first section reviewed the most common linear models. The second section discussed the forecasting performances of nonlinear forecasting models. The third section provided studies about the hybrid forecasting models in terms of out-of-sample forecasting performance.

2

<!-- Page 4 -->

Input:  \( \zeta_{m} \) ,  \( \zeta_{v} \) ,  \( \zeta_{t} \) ,  \( \xi_{a} \) ,  \( \xi_{pARDL}^{\prime} \) ,  \( \zeta_{\epsilon_{ARDL}}^{\prime} \) ,  \( \omega_{\zeta_{\epsilon_{ARDL}},k} \) , n, k,  \( h_{1} \) ,  \( h_{2} \) ;

1. Given:  \( \zeta_{m} \) ,  \( \zeta_{v} \) ,  \( \xi_{a} \) ,  \( \xi_{pARDL}^{\prime} \) ,  \( \zeta_{\epsilon_{ARDL}}^{\prime} \) 

2. For each  \( \xi_{a} \) ,  \( \xi_{pARDL}^{\prime} \)  do

 \( \xi_{aARDL} = [\xi_{a(1\times n)}] \) 

 \( \xi_{pARDL}^{\prime} = [\xi_{p(1\times n)}^{\prime}] \) 

 \( \zeta_{\epsilon_{ARDL}}^{\prime} = \xi_{aARDL} - \xi_{pARDL}^{\prime} \) 

end for

end for

3. For each  \( \xi_{a} \)  do

Compute  \( RMSE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},n} \)  &  \( MAE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},n} \) 

Find  \( min(RMSE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},n}) \)  &  \( min(MAE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},n}) \) 

end for

4. Save each  \( \zeta_{\epsilon_{ARDL}}^{\prime} \)  residual corresponding

 \( min(RMSE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},n}) \)  &  \( min(MAE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},n}) \) 

5. Compute  \( \omega_{\zeta_{\epsilon_{ARDL}},k} \)  based on each  \( \zeta_{\epsilon_{ARDL}}^{\prime} \) 

6. Create matrix for all possible combinations for the number of nodes in hidden layers

For each  \( h_{1} \)  do

For each  \( h_{2} \)  do

Run neural network model  \( \omega_{\zeta_{m},\zeta_{\epsilon_{ARDL}}^{\prime},k,h_{1},h_{2},\zeta_{\epsilon_{ARDL}}^{\prime},\zeta_{m}} \)  end

for

end for

7. Compute each  \( RMSE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},h_{1},h_{2}} \)  &  \( MAE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},h_{1},h_{2}} \) 

8. Save  \( min(RMSE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},h_{1},h_{2}}) \)  &  \( min(MAE_{\zeta_{v},\zeta_{\epsilon_{ARDL}}^{\prime},h_{1},h_{2}}) \)  to determine the optimum number of nodes in each hidden layer

9. Run neural network model  \( \omega_{(\zeta_m+\zeta_v),\zeta' _{\epsilon_{ARDL}},k,opt.h_1,opt.h_2,\zeta'_{\epsilon_{ARDL}},(\zeta_m+\zeta_v)} \) 

Output: Optimal model optimal  \( \zeta' _{\epsilon_{ARDL},\zeta_t} \)  with optimum  \( h_1 \)  and  \( h_2 \)

Fig. 1. The proposed hybrid algorithm.

# 2.2.1. Linear forecasting models

There are a number of different econometric models in the literature proposed by researchers to predict the future movement of freight rates. Among those, the ARIMA model by Box and Jenkins (1976), the VAR model by Sims (1980), VECM by Engle and Granger (1987) were widely used, linear forecasting models. Franses and Veenstra (1997) proposed the VAR model to forecast Bulk Dry Index (BDI). Cullinane and Khanna (1999) employed the ARIMA model to forecast the Baltic Freight Index (BFI) dataset. Batchelor et al. (2007) concluded that ARIMA and VAR models provide better forecast accuracy than the VECM model for the Baltic Panamax Index. Chen et al. (2012) performed four different models, such as VAR, VARX, ARIMA, and ARIMAX, in the dry bulk market. They showed that VAR and VARX models perform compared to the others.

# 2.2.2. Nonlinear forecasting models

If the price series is linear, the models in question could generate useful results in terms of forecasting. However, forecasting becomes a challenging task because of the existence of nonlinearity in bulk shipping price series. Thus, as an artificial intelligence model, neural networks (ANN) and support vector machines (SVM) have been widely applied successfully in the bulk shipping market (Li and Parsons, 1997) carried out the comparison of artificial neural networks (ANNs) and ARMA models. The findings of a comparative analysis of ANNs and ARMA models showed that the ANNs model outperformed the ARMA model. Lyridis et al. (2004) suggested a nonlinear modelling framework by using the ANNs model to forecast Very Large Crude Carriers (VLCC). Thalassinos et al. (2013) focused on the nonlinear analysis approach, such as False Nearest Neighbors (FNN), to forecast the BDI. Uyar and Ilhan (2016) forecasted annual freight rates by using a recurrent fuzzy neural network. They emphasised the superiority of their proposed approach.

# 2.2.3. Hybrid forecasting models

More recently, hybrid forecasting models have been extensively applied to combine linear and nonlinear models because they can have superior capabilities to deal with some weaknesses in the forecasting field when compared to traditional forecasting models. Han et al. (2014) employed wavelet transform to denoise the BDI series and proposed the algorithm that combined the model of wavelet transform and support vector machine (SVM). Zeng et al. (2016) contributed to knowledge in respect of improving the forecast accuracy by using Empirical Mode Decomposition (EMD). The BDI series was decomposed into several independent instinct mode functions (IMFs). In this context, each component was modelled by using ANN. It was concluded that the proposed methodology that was EMD-ANN approach led to improved forecasting performance rather than the VAR model (based on out-sample results). Guan et al. (2016) forecasted the Baltic Supramax Index by using hybrid multi-step SVM. Eslami et al. (2017) proposed a new hybrid forecasting approach that combined the ANN model and adaptive genetic algorithm (AGA) to improve forecast accuracy. They found that the proposed hybrid model performed better forecasting results by providing smaller mean square error (MSE) than the regression model, moving average (MA) model, and ANN model.

# 3. Methodology and data

# 3.1. Shipping Q as an adaptation of Tobin's Q index

SQ index, in other words, a momentum indicator for shipping asset prices, created following the fundamentals of capital investment model, Tobin Q theory (Brainard and Tobin, 1968; Tobin, 1969). In Tobin Q model, dynamic value change of assets throughout the time captured by the ratio of market value of a firm to replacement value. The Q ratio aimed to identify if the firm's value is over-valued, when the ratio is greater than 1, or under-valued, when the ratio is lower than 1. In Tobin Q theory, if ratio is greater

3

<!-- Page 5 -->

Fig. 2. Training, validation, and test sets of dry bulk carriers: (a) 5 years old, (b) 10 years old, and (c) 15 years old.

Fig. 3. Differences in ranked order means of models: (a) 5 years old dry bulk carrier, (b) 10 years old dry bulk carrier, and (c) 15 years old dry bulk carrier.

4

<!-- Page 6 -->

Table 1

Descriptive statistics for output and input variables (1990–2017).

|  |  | Mean | Standard deviations | Skewness | Kurtosis |
| **---** | | | | | |
| **Bulker/Handysize5** | | | | | |
| SH5 | β5 | 14.502 | 8.515 | 1.865 | 8.103 |
| SQ | Φsq | 1.401 | 0.749 | 1.533 | 4.996 |
| TC | ∞ | 8,858.70 | 6,110.07 | 2.961 | 13.501 |
| **Bulker/Handysize10** | | | | | |
| SH10 | β10 | 14.264 | 8.194 | 2.033 | 7.470 |
| SQ | Φsq | 1.960 | 1.461 | 1.390 | 4.432 |
| TC | ∞ | 8,858.70 | 6,110.07 | 2.961 | 13.501 |
| **Bulker/Handysize15** | | | | | |
| SH15 | β15 | 12.033 | 7.634 | 1.573 | 5.414 |
| SQ | Φsq | 1.562 | 2.795 | 2.469 | 14.242 |
| TC | ∞ | 8,858.70 | 6,110.07 | 2.961 | 13.501 |
| **Bulker/Handymax5** | | | | | |
| SH5 | β5 | 21.753 | 12.143 | 2.529 | 10.534 |
| SQ | Φsq | 1.133 | 0.758 | 4.427 | 10.191 |
| TC | ∞ | 13,144.73 | 10,907.74 | 2.868 | 11.795 |
| **Bulker/Handymax10** | | | | | |
| SH10 | β10 | 17.771 | 11.230 | 2.377 | 8.969 |
| SQ | Φsq | 1.255 | 1.050 | 2.433 | 8.524 |
| TC | ∞ | 13,144.73 | 10,907.74 | 2.868 | 11.795 |
| **Bulker/Handymax15** | | | | | |
| SH15 | β15 | 15.342 | 10.754 | 1.857 | 6.313 |
| SQ | Φsq | 1.855 | 1.618 | 1.847 | 5.808 |
| TC | ∞ | 13,144.73 | 10,907.74 | 2.868 | 11.795 |
| **Bulker/Panamax5** | | | | | |
| SH5 | β5 | 21.690 | 14.510 | 2.535 | 11.219 |
| SQ | Φsq | 1.052 | 0.651 | 2.223 | 7.817 |
| TC | ∞ | 13,407.25 | 12,349.51 | 3.251 | 15.011 |
| **Bulker/Panamax10** | | | | | |
| SH10 | β10 | 20.829 | 14.236 | 2.367 | 8.815 |
| SQ | Φsq | 1.168 | 0.956 | 2.241 | 7.602 |
| TC | ∞ | 13,407.25 | 12,349.51 | 3.251 | 15.011 |
| **Bulker/Panamax15** | | | | | |
| SH15 | β15 | 17.744 | 13.392 | 1.881 | 6.309 |
| SQ | Φsq | 1.669 | 1.504 | 1.831 | 5.769 |
| TC | ∞ | 13,407.25 | 12,349.51 | 3.251 | 15.011 |
| **Bulker/Capesize5** | | | | | |
| SH5 | β5 | 36.503 | 24.744 | 2.696 | 12.022 |
| SQ | Φsq | 0.901 | 0.560 | 1.765 | 5.917 |
| TC | ∞ | 21,521.43 | 25,842.84 | 3.476 | 16.445 |
| **Bulker/Capesize10** | | | | | |
| SH10 | β10 | 31.199 | 21.517 | 2.243 | 8.136 |
| SQ | Φsq | 0.755 | 0.577 | 2.334 | 8.028 |
| TC | ∞ | 21,521.43 | 25,842.84 | 3.476 | 16.445 |
| **Bulker/Capesize15** | | | | | |
| SH15 | β15 | 26.214 | 20.577 | 1.955 | 6.321 |
| SQ | Φsq | 0.905 | 0.849 | 1.926 | 5.925 |
| TC | ∞ | 21,521.43 | 25,842.84 | 3.476 | 16.445 |

than 1, the investment is worthwhile. However, while adapting Q model to shipping industry, Celik Girgin et al. (2019) followed a different approach. They adapted Q-model to second-hand dry bulk market to create a buy and sell warning system. In this system, they used presumption of "if Q is greater than 1, sell and if Q is lower than 1, buy". In other words, if SQ is over 1 level, then ship is overvalued, and the signal is interpreted as a "sell"; if SQ is below 1 level, then ship is undervalued, and the signal is interpreted as a "buy".

SQ index is calculated as a ratio of the market value of a ship to a nominal value of a ship. The nominal value of a ship is determined by long-term value of ship (income-based approach). There is an alternative way to identify nominal value of a vessel, which is DCF of the book value of the ship, however, in the shipping industry 'Book Value' could be misguiding predictor as it is static value of an asset (Duru, 2013). Especially, 2008 Global Financial Crisis period raised the questions about the book value of vessels, dramatic price changes over the period of 2007–2009. Therefore, the long-term value of a ship as a nominal value of a vessel was used in SQ calculation and the spot market value of a SH dry bulker used as a market value.

To utilize discounted cash flow method, the anticipated revenue and expenditure were identified for every year in the life of the ship and net cash flow calculated as revenue minus expenditure, adjusted by a discount factor. Each individual cash flow for vessel started from 1990 as a reference year and measured until the available year. The assumption build on the investment scenario of an investor seeks to buy a second-hand dry bulk in 1990 either 5, 10 or 15 years old, so for each vessel types and age discounted cash flow is calculated to find the nominal value a second-hand dry bulkers in 1990. The calculation consecutively conducted for every second-hand vessel types and ages. For instance, Handysize 5-year-old SH is up for sale in the market in 1990 and to calculate this vessel's nominal value, ten-year average of TC rate and scrap values from 1980 to 1990 are used. The economic life of a second-hand dry bulkers accepted as 25 years (Stopford, 2009). Scrap value is measured by the corresponding year's scrap prices multiplied by LDT \( ^{3} \) . Finally, nominal asset value is found as the sum of the discounted

5

\( ^{3} \)  Lightweight tone data is collected from various sources for each vessel/age and their average is considered to calculate scrap value of second-hand dry bulkers.

<!-- Page 7 -->

# Table 2

Accuracy metrics and predictive results for Handysize dry bulk ships.

| Handysize, 5-year-old | Handysize, 5-year-old | Handysize, 10-year-old | Handysize, 10-year-old | Handysize, 15-year-old | Handysize, 15-year-old |
| **---** | | | | | |
| **Univariate Models no inputs or independent variable** | | | | | |
| ARIMA | 0.009 | ARIMA | 0.007 | ARIMA | 0.018 |
| HW-A | 0.012 | HW-A | 0.012 | HW-A | 0.026 |
| HW-M | 0.012 | HW-M | 0.012 | HW-M | 0.026 |
| ETS | 0.011 | ETS | 0.005 | ETS | 0.014 |
| TBATS | 0.011 | TBATS | 0.006 | TBATS | 0.018 |
| regARIMA | 0.010 | regARIMA | 0.007 | regARIMA | 0.018 |
| **Multivariate Models including Shipping Q as an independent variable** | | | | | |
| VAR | 0.010 | VAR | 0.005 | VAR | 0.015 |
| ARDL | 0.005 | ARDL | 0.012 | ARDL | 0.009 |
| **Nonlinear Models** | | | | | |
| ANNa | 0.003 | ANNa | 0.010 | ANNa | 0.025 |
| ANNb | 0.003 | ANNb | 0.004 | ANNb | 0.018 |
| **Hybrid Models** | | | | | |
| ARIMA-ANCc | 0.009 | ARIMA-ANCc | 0.007 | ARIMA-ANCc | 0.022 |
| ETS-ANNd | 0.010 | ETS-ANNd | 0.005 | ETS-ANNd | 0.014 |
| ARDL-ANNe | 0.005 | ARDL-ANNe | 0.010 | ARDL-ANNe | 0.008 |
| ARDL-EMD-ANNf | 0.002 | ARDL-EMD-ANNf | 0.002 | ARDL-EMD-ANNf | 0.009 |

Bold values signifies the high accuracy among forecasting models.

a Inputs, output lags.

b Inputs, shipping Q.

c No inputs in linear modelling.

d No inputs in linear modelling.

e inputs, shipping Q, in linear modelling.

f inputs, shipping Q, in linear modelling.

# Table 3

Accuracy metrics and predictive results for Handymax dry bulk ships.

| Handymax, 5-year-old | Handymax, 5-year-old | Handymax, 10-year-old | Handymax, 10-year-old | Handymax, 15-year-old | Handymax, 15-year-old |
| **---** | | | | | |
| **Univariate Models no inputs or independent variable** | | | | | |
| ARIMA | 0.006 | ARIMA | 0.010 | ARIMA | 0.011 |
| HW-A | 0.013 | HW-A | 0.007 | HW-A | 0.011 |
| HW-M | 0.014 | HW-M | 0.029 | HW-M | 0.011 |
| ETS | 0.006 | ETS | 0.010 | ETS | 0.011 |
| TBATS | 0.006 | TBATS | 0.009 | TBATS | 0.012 |
| regARIMA | 0.006 | regARIMA | 0.010 | regARIMA | 0.011 |
| **Multivariate Models including Shipping Q as an independent variable** | | | | | |
| VAR | 0.007 | VAR | 0.010 | VAR | 0.008 |
| ARDL | 0.006 | ARDL | 0.006 | ARDL | 0.006 |
| **Nonlinear Models** | | | | | |
| ANNa | 0.005 | ANNa | 0.005 | ANNa | 0.005 |
| ANNb | 0.003 | ANNb | 0.004 | ANNb | 0.007 |
| **Hybrid Models** | | | | | |
| ARIMA-ANNc | 0.006 | ARIMA-ANNc | 0.010 | ARIMA-ANNc | 0.011 |
| ETS-ANNd | 0.005 | ETS-ANNd | 0.010 | ETS-ANNd | 0.012 |
| ARDL-ANNe | 0.004 | ARDL-ANNe | 0.006 | ARDL-ANNe | 0.006 |
| ARDL-EMD-ANNf | 0.000 | ARDL-EMD-ANNf | 0.001 | ARDL-EMD-ANNf | 0.001 |

Bold values signifies the high accuracy among forecasting models.

a Inputs, output lags.

b Inputs, shipping Q.

c No inputs in linear modelling.

d No inputs in linear modelling.

e Inputs, shipping Q, in linear modelling.

f Inputs, shipping Q, in linear modelling.

cash flows plus the discounted residual value, demolition value of the ship. The formulation of the SQ index is provided below:

\[
\varPhi_ {Q} = \frac {S H _ {n , \mathrm{d}}}{D C F _ {n , \mathrm{d}}}
\]

(2.1)

\[
D C F _ {n, d} = \sum_ {t = 1} ^ {T} \frac {\left(R _ {n , t} - \mathrm{OPEX} _ {n , t}\right)}{(1 + i) ^ {t}} + \frac {S C R P _ {t + i}}{(1 + i) ^ {t}}
\]

(2.2)

\[
R = T C _ {n} * 350
\]

(2.3)

\[
\mathrm{OPEX} _ {n, t} = \text { OPEX } _ {\text { daily }} * 365
\]

(2.4)

where,  \( \Phi_{Q} \)  is a ratio of market value,  \( SH_{n,d} \)  of a second-hand dry bulk ship (n) age 5~15 (d) to  \( DCF_{n,d} \)  is an intrinsic value of a dry

bulk ship (n) age 5~15 (d), which was computed by discounted free cash flow method. OPEX \( _{n,t} \) stands for the operating expense of a dry bulk ship (n) at time (t), and \( SCRP_{t+i} \) is the maturity value of the asset at the end of economic life t+i. R represents yearly operating income.

The approach used in the computation of this leading index was previously studied by Marcus et al. (1991), and utilized Buy Low and Sell High approach. However, to calculate the nominal value of a ship, they used the cost-based value of an asset with the assumption of constant cash flow during the economic life of a ship, which possibly leads to bias and overlooks freight market cyclicality and volatility. In the SQ index, these issues were dissolved by utilizing a discounted free cash flow approach.

6

<!-- Page 8 -->

# 3.2. Sample data and predictive models

The sample data was compiled from various databases (Bloomberg Inc., Thompson Reuters) including time-charter rate and second-hand prices over the period of 1980–2017 (monthly) for commodity carriers (Handysize, Handymax, Panamax, and Capesize dry bulk ships). Due to the requirements of DCF valuation, the SQ index was generated from 1990 to 2017 in a walk-forward valuation structure. The diagnostic features of the data were discussed in Section 4.

The predictive feature of the SQ was tested through a spectrum of univariate models as the benchmark of the 'no effect' hypothesis and multivariate models implementing the leading indicator as to the benchmark of the 'predictive gain/loss' hypothesis. In this regard, the empirical study applied the univariate models such as autoregressive integrated moving average (ARIMA) (Pankratz, 1983); Holt-Winter's additive (H-WA) (Makridakis et al., 2008) and multiplicative (H-W M) models; error, trend, seasonal (ETS); trigonometric box-cox transformation ARMA Errors, trend and seasonal components (TBATS) (Petropoulos et al., 2018). ; and regression with ARIMA errors (regARIMA). For observing the predictive gain, a bundle of multivariate models were utilised including vector autoregression (VAR); autoregressive distributed lag model (ARDL) (Pesaran and Shin, 1998); and artificial neural networks (ANN) (Kaboudan, 2001; Rasouli et al., 2016). In this paper, we used the simulation of various hybrid algorithms, including ARIMA-ANN and ETS-ANN. To achieve this, modification first aimed to address the use of EMD decomposition method, while the nonlinear component is modelled by ANN; second, a novel hybrid algorithm based on the ARDL model, which refers to linear part modelling, and the ANN model, which refers to nonlinear modelling part, are proposed to maximise different models' advantages by providing better forecast accuracy. Fig. 1 presents the proposed algorithm to compute forecasts:

Lastly, post-sample illustrated in Fig. 2:

# 4. Empirical results and discussion

Data for this study consisted of four dry bulk carriers in three age groups (5, 10, 15-years old). Table 1 summarises the basic statistical results of the SQ index for the given sample. The results indicated that the volatility increases as ship size increases; we can state that the time-charter rates for larger vessels fluctuate more than smaller ones.

The time-charter rate was positively skewed, and it was in a trend to increase as the vessel tonnage increases. The level of kurtosis was both asset prices (SH) and operating income (TC, period charter rate) supported the motivation of this study and signalled the potential of temporal arbitrage in the shipping assets.

The parametric significance of the leading indicator has been investigated as the accuracy gain in the pseudo predictive test procedure (i.e., back-testing). The theoretical argument behind the proposed technique relied on the fact that a leading index of ship prices must reduce the reference accuracy metric in the out of sample data (holdout test set) (Tables 2–5, second-hand ship prices of dry bulk carriers). If the presence of the leading indicator did not reduce the prediction error, that would indicate the false cause or impracticality of the proposed lead-lag structure.

In this regard, univariate models were estimated as benchmarks to observe the pseudo predictive performance in the absence of the indicator. The superiority of any of these models would reject the predictive significance, and multivariate models with the SQ as an (only) explanatory variable are expected to outperform the univariate benchmarks to validate its predictive feature.

To comprehend the out-of-sample forecasting performances of the models visually, the models were ranked using MASE metrics. Depending on the minimum MASE values, the ranked order from one to 14 was assigned to each model. The Tukey test was used to find out which models' ranked order means are different. Fig. 3 shows that (1) for 5 years old dry bulk carriers, the ARDL-EMD-ANN \( ^{f} \) model has the minimum ranked order mean and statistical significance from the other models' forecasting performances, (2) for 10 years old dry bulk carriers, there is no statistical difference between the ANN \( ^{b} \) and the ARDL-EMD-ANN \( ^{f} \) in terms of the ranked order means. However, these two models have better out-of-sample forecasting performance than the other models, and (3) for 15 years old dry bulk carriers, the models such as ARDL, ANN \( ^{b} \), ARDL-ANN \( ^{e} \) and ARDL-EMD-ANN \( ^{f} \) which use the SQ index as input to improve forecast accuracy are not statistically different in terms of the ranked order means. Nevertheless, these four models lead to better forecasts than other single models.

Moreover, the time plots of the actual values of the test set and the forecasts of the four models having best out-of-sample forecasting performances were given in Figs. 4, 5 and 6 for 5, 10 and 15 years-old dry bulk carriers. Based on the evaluation of the graphs of the forecasts, the four models, where the shipping Q index was used as explanatory variable, performed well in predicting dry bulk carriers, and was able to capture most of changes in both magnitude and direction of the dry bulk carriers.

Empirical results for Handysize tonnage given in Table 2 indicated that the accuracy gain with the SQ index was relatively

(a)
40
35
30
25
20
1 3 5 7 9 11 13 15 17 19 21 23
Test Data
ARDL
ANN \( ^{b} \)
ARDL-ANN \( ^{e} \)
ARDL-EMD-ANN \( ^{f} \)

(b)
20
15
10
1 3 5 7 9 11 13 15 17 19 21 23
Test Data
ARDL
ANN \( ^{b} \)
ARDL-ANN \( ^{e} \)
ARDL-EMD-ANN \( ^{f} \)
(c)
20
15
10
5
1 3 5 7 9 11 13 15 17 19 21 23
Test Data
ARDL
ANN \( ^{b} \)
ARDL-ANN \( ^{e} \)
ARDL-EMD-ANN \( ^{f} \)
(d)
25
20
15
10
1 3 5 7 9 11 13 15 17 19 21 23
Test Data
ARDL
ANN \( ^{b} \)
ARDL-ANN \( ^{e} \)
ARDL-EMD-ANN \( ^{f} \)

Fig. 4. Second-hand dry bulk carriers 5 years-old: (a) Capesize, (b) Handymax, (c) Handysize, and (d) Panamax.

7

<!-- Page 9 -->

# Table 4

Accuracy metrics and predictive results for Panamax dry bulk ships.

| Panamax, 5-year-old | Panamax, 5-year-old | Panamax, 10-year-old | Panamax, 10-year-old | Panamax, 15-year-old | Panamax, 15-year-old |
| **---** | | | | | |
| **Univariate Models no inputs or independent variable** | | | | | |
| ARIMA | 0.006 | ARIMA | 0.008 | ARIMA | 0.008 |
| HW-A | 0.011 | HW-A | 0.008 | HW-A | 0.011 |
| HW-M | 0.011 | HW-M | 0.011 | HW-M | 0.011 |
| ETS | 0.007 | ETS | 0.009 | ETS | 0.011 |
| TBATS | 0.006 | TBATS | 0.008 | TBATS | 0.007 |
| regARIMA | 0.006 | regARIMA | 0.008 | regARIMA | 0.008 |
| **Multivariate Models including Shipping Q as an independent variable** | | | | | |
| VAR | 0.007 | VAR | 0.009 | VAR | 0.012 |
| ARDL | 0.002 | ARDL | 0.009 | ARDL | 0.011 |
| **Nonlinear Models** | | | | | |
| \( ANN^a \) | 0.005 | \( ANN^a \) | 0.009 | \( ANN^a \) | 0.009 |
| \( ANN^b \) | 0.002 | \( ANN^b \) | 0.006 | \( ANN^b \) | 0.007 |
| **Hybrid Models** | | | | | |
| \( ARIMA-ANN^c \) | 0.006 | \( ARIMA-ANN^c \) | 0.008 | \( ARIMA-ANN^c \) | 0.008 |
| \( ETS-ANN^d \) | 0.006 | \( ETS-ANN^d \) | 0.008 | \( ETS-ANN^d \) | 0.012 |
| \( ARDL-ANN^e \) | 0.002 | \( ARDL-ANN^e \) | 0.003 | \( ARDL-ANN^e \) | 0.002 |
| \( ARDL-EMD-ANN^f \) | 0.001 | \( ARDL-EMD-ANN^f \) | 0.002 | \( ARDL-EMD-ANN^f \) | 0.002 |

Bold values signifies the high accuracy among forecasting models.

a Inputs, output lags.

b Inputs, shipping Q.

c No inputs in linear modelling.

d No inputs in linear modelling.

e inputs, shipping Q, in linear modelling.

f inputs, shipping Q, in linear modelling.

# Table 5

Accuracy metrics and predictive results for Capesize dry bulk ships.

| Capesize, 5-year-old | Capesize, 5-year-old | Capesize, 10-year-old | Capesize, 10-year-old | Capesize, 15-year-old | Capesize, 15-year-old |
| **---** | | | | | |
| **Univariate Models no inputs or independent variable** | | | | | |
| ARIMA | 2.627 | ARIMA | 0.012 | ARIMA | 0.010 |
| HW-A | 5.460 | HW-A | 0.013 | HW-A | 0.014 |
| HW-M | 3.530 | HW-M | 0.013 | HW-M | 0.014 |
| ETS | 2.965 | ETS | 0.012 | ETS | 0.011 |
| TBATS | 2.865 | TBATS | 0.011 | TBATS | 0.009 |
| regARIMA | 2.644 | regARIMA | 0.011 | regARIMA | 0.009 |
| **Multivariate Models including Shipping Q as an independent variable** | | | | | |
| VAR | 3.047 | VAR | 0.011 | VAR | 0.009 |
| ARDL | 1.731 | ARDL | 0.005 | ARDL | 0.007 |
| **Nonlinear Models** | | | | | |
| \( ANN^a \) | 1.483 | \( ANN^a \) | 0.004 | \( ANN^a \) | 0.008 |
| \( ANN^b \) | 1.095 | \( ANN^b \) | 0.004 | \( ANN^b \) | 0.005 |
| **Hybrid Models** | | | | | |
| \( ARIMA-ANN^c \) | 2.672 | \( ARIMA-ANN^c \) | 0.011 | \( ARIMA-ANN^c \) | 0.010 |
| ETS-ANN\( ^d \) | 1.879 | ETS-ANN\( ^d \) | 0.009 | ETS-ANN\( ^d \) | 0.008 |
| ARDL-ANN\( ^e \) | 1.404 | ARDL-ANN\( ^e \) | 0.005 | ARDL-ANN\( ^e \) | 0.002 |
| ARDL-EMD-ANN\( ^f \) | 0.737 | ARDL-EMD-ANN\( ^f \) | 0.003 | ARDL-EMD-ANN\( ^f \) | 0.001 |

Bold values signifies the high accuracy among forecasting models.

a Inputs, output lags.

b Inputs, shipping Q.

c No inputs in linear modelling.

d No inputs in linear modelling.

e Inputs, shipping Q, in linear modelling.

f Inputs, shipping Q, in linear modelling.

limited in younger ships. Both ANN and ARDL-EMD-ANN combination gained a few points of reduction in MASE for 5 and 10 years old ships. On the other hand, ARDL as a dynamic model and ARDL-EMD-ANN as a hybrid model improved the accuracy in 15 years old Handysize ships with comparatively much significant reduction.

Results are also reported in Tables 3–5 to demonstrate the post-sample accuracy results for Handymax, Panamax, and Capesize tonnages respectively. Accuracy gain in those tonnages was also indicated the pseudo predictive improvement, particularly in older ships (10- or 15-year-old). Empirical results suggested that the SQ index as a leading indicator reduces predictive error which validates its practical value. The accuracy gain has been recorded over 50% in certain assets (e.g. Capesize, 10-year old). Overall, the

proposed hybrid algorithm is the one with the best forecasting performance by achieving a significant reduction in forecasting error.

Considering that shipping asset prices would generate massive volatility, the monetary value of such predictive accuracy translated to over USD 50 million gain or offsetting the loss by improving the investment timing. In the counter-cyclical asset play, the SQ index signalled the asset security value shortfalls or a run-up in 3–5 months' time lags.

The proposed leading indicator has also implications in the ship finance regarding the minimum security value covenant. In the security of outstanding debt obligations, senior loan facility agreements required periodical valuations of ship mortgages to detect security value shortfalls. However, the ship valuation exercise is

8

<!-- Page 10 -->

Fig. 5. Second-hand dry bulk carriers 10 years-old: (a) Capesize, (b) Handymax, (c) Handysize, and (d) Panamax.

Fig. 6. Second-hand dry bulk carriers 15 years old: (a) Capesize, (b) Handymax, (c) Handysize, and (d) Panamax.

not practically useful if the security shortfall arises as a result of the market collapse and asset bubbles. In this regard, the SQ index can be utilised in identifying overpriced assets and potential security value shortfalls during the credit analysis stage.

# 5. Conclusion

This paper proposed a novel hybrid algorithm for second-hand bulk carriers forecasting, and ARDL-EMD-ANN hybrid model developed to test forecasting performance. The modelling and forecasting steps were described, and the empirical analysis was carried out based on various types of carriers. The forecasting accuracy of the hybrid model was compared with the competitive models in most of the forecasting studies. The results indicated that the proposed algorithm that uses the strength of the combination of the ARDL and ANN models by including the decomposition part for modelling residuals were superior to all benchmark models.

The proposed novel model applied to the SQ index sample data, which was tested and validated as a leading index for investment timing in a given set of dry bulk assets, which developed information for the market entry-exit mechanism. In limited use, the SQ index can improve the long-term return of investment by optimising the asset play components. In massive use, anticipated dynamics would be negated by investors, and the leading impact may have deteriorated. Eventually, the empirical analysis proved that the proposed hybrid algorithm is a viable alternative for second-hand bulk carriers forecasting, and it can be applied to different time series data in other areas.

Moreover, utilised empirical mode decomposition (EMD) and feedforward neural networks (artificial neural network-ANN) stated that the SQ index has a crucial role in explaining market entry and exit decisions. Practically, we can state that this index can be used by market players, charterers, shipping management companies. Using this index in the decision-making process can lead to several benefits, forecasting market conditions can facilitate taking a position in the market, buy, or sell.

SQ index is a dynamic momentum indicator for shipping asset prices, which re-evaluates the market entry and exit decisions, as the freight rate changes. In earlier studies, the SQ index presented solely dynamic index, not implemented in parametric linear or nonlinear predictive models as an explanatory variable. In this study, it was analysed as an explanatory variable and tested its forecasting performance. In the extended literature, historical asset prices and freight rates are utilized as an explanatory variable. On the other hand, the raw dataset does not reflect asset price misvaluation which is very common in the industry. Asset misvaluation typically cause asset value shortfalls (minimum value covenant) and trigger foreclosure or restructuring of the loan facility. In this novel study, we implemented the SQ index to represent the misvaluation as a momentum indicator.

One-step ahead predictive performance in this study leads the future research on the optimisation of lead-lag structure for various methodologies as well as blending with other explanatory variables.

9

<!-- Page 11 -->

# Author declaration

There is no conflict of interest to declare. This manuscript has not been published or resented elsewhere in part or in entirety and is not under consideration by another journal. We have read and understood your journal’s policies, and we believe that neither the manuscript nor the study violates any of these.

# Declarations of interest

None.

# References

Alizadeh, A., & Nomikos, N. (2007). Investment timing and trading strategies in the sale and purchase market for ships. Transportation Research Part B Methodological, 41(1), 126–143.

Batchelor, R., Alizadeh, A., & Visvikis, I. (2007). Forecasting spot and forward prices in the international freight market. International Journal of Forecasting, 23(1), 101–114.

Box, G. E. P., & Jenkins, G. M. (1976). Time series analysis: Forecasting and control. Holden-Day.

Brainard, W., & Tobin, J. (1968). Pitfalls in financial model building. The American Economic Review, 58, 99–122.

Celik Girgin, S., Karlis, T., & Duru, O. (2019). Valuation mismatch and shipping q indicator for shipping asset management. Maritime Policy & Management, 1–18.

Chen, S., Meersman, H., & Van de Voorde, E. (2012). Forecasting spot rates at main routes in the dry bulk market. Maritime Economics & Logistics, 14(4), 498–537.

Cullinane, K., & Khanna, M. (1999). Economies of scale in large container ships. Journal of Transport Economics and Policy, 33(2), 185–207.

Dikos, G., & Marcus, H. (2003). The term structure of second-hand prices: A structural partial equilibrium model. Maritime Economics & Logistics, 5(3), 251–267.

Duru, O. (2013). Irrational exuberance, overconfidence and short-termism: Knowledge-to-action asymmetry in shipping asset management. The Asian Journal of Shipping and Logistics, 29(1), 43–58.

Duru, O. (2018). Shipping business unwrapped: Illusion, Bias and fallacy in the shipping business. Routledge.

Engle, R. F., & Granger, C. W. (1987). Co-integration and error correction: Representation, estimation, and testing. Econometrica: Journal of the Econometric Society, 251–276.

Eslami, P., Jung, K., Lee, D., & Tjolleng, A. (2017). Predicting tanker freight rates using parsimonious variables and a hybrid artificial neural network with an adaptive genetic algorithm. Maritime Economics & Logistics, 19(3), 538–550.

Forrester, J. W. (1958). Industrial dynamics. A major breakthrough for decision makers. Harvard business review, 36(4), 37–66.

Franses, P. H., & Veenstra, A. (1997). A cointegration approach to forecasting freight rates in the dry bulk shipping sector. Transportation Research Part A: Policy & Practice, 447–458.

Girgin, S. C., Karlis, T., & Nguyen, H.-O. (2018). A critical review of the literature on firm-level theories on ship investment. International Journal of Financial Studies, 6(11).

Greenwood, R., & Hanson, S. G. (2015). Waves in ship prices and investment. The Quarterly Journal of Economics, 130(1), 55–109.

Guan, F., Peng, Z., Wang, K., Song, X., & Gao, J. (2016). Multi-step hybrid prediction model of baltic supermax index based on support vector machine. Neural Network World, 26(3), 219.

Han, Q., Yan, B., Ning, G., & Yu, B. (2014). Forecasting dry bulk freight index with improved SVM. Mathematical Problems in Engineering, 2014.

Jeon, J.-W., Duru, O., & Yeo, G.-T. (2020). Modelling cyclic container freight index using system dynamics. Maritime Policy & Management, 47(3), 287–303.

Kaboudan, M. (2001). Compumetric forecasting of crude oil prices. In Paper Presented at the Proceedings of the 2001 Congress on Evolutionary Computation (IEEE Cat. No. 01TH8546).

Karlis, T., Polemis, D., Girgin, S. C., & Syntychaki, A. (2019). Future challenges of Maritime economics research. In Paper Presented at the IAME 2019 CONFERENCE.

Kou, Y., & Luo, M. (2018). Market driven ship investment decision using the real option approach. Transportation Research Part A: Policy and Practice, 118, 714–729.

Li, J., & Parsons, M. G. (1997). Forecasting tanker freight rate using neural networks. Maritime Policy & Management, 24(1), 9–30.

Lyridis, D., Zacharioudakis, P., Mitrou, P., & Mylonas, A. (2004). Forecasting tanker market using artificial neural networks. Maritime Economics & Logistics, 6(2), 93–108.

Makridakis, S., Wheelwright, S. C., & Hyndman, R. J. (2008). Forecasting methods and applications. John wiley & sons.

Marcus, H., Glucksman, M., Ziogas, B., & Meyer, K. (1991). A buy-low, sell-high investment methodology: The case of bulk shipping. Interfaces, 21(2), 8–21.

Merikas, A. G., Merika, A. A., & Koutroubousis, G. (2008). Modelling the investment decision of the entrepreneur in the tanker sector: Choosing between a second-hand vessel and a newly built one. Maritime Policy & Management, 35(5), 433–447.

Pankratz, A. (1983). Forecasting with univariate box-jenkins models: Concepts and cases. USA: John Wiley & Sons. Inc.

Pesaran, M. H., & Shin, Y. (1998). An autoregressive distributed-lag modelling approach to cointegration analysis. Econometric Society Monographs, 31, 371–413.

Petropoulos, F., Kourentzes, N., Nikolopoulos, K., & Siemsen, E. (2018). Judgmental selection of forecasting models. Journal of Operations Management, 60, 34–46.

Rasouli, S., Tabesh, H., & Etminani, K. (2016). A study of input variable selection to artificial neural network for predicting hospital inpatient flows. Current Journal of Applied Science and Technology, 1–8.

Rau, P., & Spinler, S. (2016). Investment into container shipping capacity: A real options approach in oligopolistic competition. Transportation Research Part E: Logistics and Transportation Review, 93, 130–147.

Sims, C. A. (1980). Macroeconomics and reality. Econometrica: Journal of the Econometric Society, 1–48.

Stopford, M. (2009). Maritime economics 3e. Routledge.

Thalassinos, I., Hanias, M. P., Curtis, G., & Thalassinos, E. (2013). Forecasting financial indices: The Baltic dry indices. In Marine navigation and safety of sea transportation: STCW, maritime education and training (MET), human resources and crew manning, maritime policy, logistics and economic matters. pp. 190–283.

Tobin, J. (1969). A general equilibrium approach to monetary theory. Journal of Money, Credit and Banking, 1(1), 15–29.

Tsolakis, S., Cridland, C., & Haralambides, H. (2003). Econometric modelling of second-hand ship prices. Maritime Economics & Logistics, 5(4), 347–377. https://doi.org/10.1057/palgrave.mel.9100086

Uyar, K., & Ilhan, A. (2016). Long term dry cargo freight rates forecasting by using recurrent fuzzy neural networks. Procedia Computer Science, 102, 642–647.

Zeng, Q., Qu, C., Ng, A. K., & Zhao, X. (2016). A new approach for Baltic Dry Index forecasting based on empirical mode decomposition and neural networks. Maritime Economics & Logistics, 18(2), 192–210.

10
