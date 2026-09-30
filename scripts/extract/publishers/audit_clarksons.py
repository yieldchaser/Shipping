import pandas as pd

df_sales = pd.read_csv('data/extracted/series/clarksons_snp_sales_series.csv')
print('=== S&P SALES SERIES AUDIT ===')
print('Total rows:', len(df_sales))
df_sales['year'] = pd.to_datetime(df_sales['issue_date']).dt.year
print('\nSales by Year:')
print(df_sales['year'].value_counts().sort_index())
print('\nSales by Sector:')
print(df_sales['sector'].value_counts())
print('\nSales by Segment:')
print(df_sales['segment'].value_counts())
pct_p = df_sales['price_usd_m'].notna().mean() * 100
valid_p = df_sales['price_usd_m'].notna().sum()
print(f'\nNumeric Price Coverage: {valid_p} ({pct_p:.1f}%)')
print('En bloc deals:', df_sales['is_en_bloc'].sum())
print('Auction deals:', df_sales['is_auction'].sum())
print('BWTS fitted:', df_sales['bwts_fitted'].sum())
print('Scrubber fitted:', df_sales['scrubber_fitted'].sum())

df_comm = pd.read_csv('data/extracted/series/clarksons_desk_talk_series.csv')
print('\n=== DESK TALK COMMENTARY AUDIT ===')
print('Total rows:', len(df_comm))
df_comm['year'] = pd.to_datetime(df_comm['issue_date']).dt.year
print('\nCommentary by Year:')
print(df_comm['year'].value_counts().sort_index())
print('\nCommentary by Sector:')
print(df_comm['sector'].value_counts())

df_demo = pd.read_csv('data/extracted/series/clarksons_demolition_sales_series.csv')
print('\n=== DEMOLITION SALES AUDIT ===')
print('Total rows:', len(df_demo))
df_demo['year'] = pd.to_datetime(df_demo['issue_date']).dt.year
print(df_demo['year'].value_counts().sort_index())

df_macro = pd.read_csv('data/extracted/series/clarksons_macro_series.csv')
print('\n=== MACRO SERIES AUDIT ===')
print('Total rows:', len(df_macro))
print('Macro with BDI:', df_macro['bdi'].notna().sum())
print('Macro with EUR/USD:', df_macro['eur_usd'].notna().sum())
