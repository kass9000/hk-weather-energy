#!/usr/bin/env python3
"""
香港氣溫 × 用電量自動更新腳本
每日執行，自動下載最新數據並更新 index.html

使用方法：
  python update_data.py

需要安裝：
  pip install requests pandas
"""

import requests
import pandas as pd
import json
import re
import sys
from datetime import datetime

print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 開始更新數據...")

# ── 1. 下載天文台每日氣溫 ─────────────────────────────────
print("正在下載天文台氣溫數據...")
try:
    url_hko = "https://data.weather.gov.hk/weatherAPI/opendata/opendata.php?dataType=CLMTEMP&rformat=csv&station=HKO"
    resp = requests.get(url_hko, timeout=30)
    resp.raise_for_status()
    lines = resp.text.strip().split('\n')
    
    daily_rows = []
    for line in lines:
        parts = line.strip().split(',')
        if len(parts) < 4: continue
        try:
            y,m,d,t = int(parts[0]),int(parts[1]),int(parts[2]),float(parts[3])
            if y >= 2020:
                daily_rows.append([y,m,d,t])
        except: pass
    
    print(f"  ✅ 氣溫數據：{len(daily_rows)} 天（最新：{daily_rows[-1]}）")
except Exception as e:
    print(f"  ❌ 氣溫數據下載失敗：{e}")
    sys.exit(1)

# ── 2. 計算每月氣溫摘要 ──────────────────────────────────
df = pd.DataFrame(daily_rows, columns=['year','month','day','temp'])
df = df[df['year'] >= 2020]

monthly_temp = df.groupby(['year','month'])['temp'].agg(
    avg='mean', mx='max', mn='min', cnt='count'
).round(1).reset_index()

# ── 3. 讀取用電量數據（需手動更新） ─────────────────────
print("正在讀取本地用電量數據...")
try:
    # 嘗試下載政府統計處數據（需要 session cookie，通常要手動）
    # 如果失敗，使用本地 CSV
    elec_url = "https://www.censtatd.gov.hk/en/web_table.html?id=127"
    print("  ⚠️  用電數據需要手動更新（政府統計處不提供直接 API）")
    print("  請定期去以下網址下載最新 CSV 並放喺同一個資料夾：")
    print("  https://www.censtatd.gov.hk/en/web_table.html?id=127")
    
    # 讀取本地 CSV
    import glob
    csv_files = glob.glob("Table_915*.csv") + glob.glob("../Table_915*.csv")
    if not csv_files:
        print("  ❌ 找唔到用電量 CSV，請下載並放喺同一資料夾")
        sys.exit(1)
    
    elec_rows = []
    month_map = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
                 'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
    
    with open(csv_files[0], encoding='utf-8-sig') as f:
        for line in f:
            parts = line.strip().split(',')
            if not parts[0].strip().isdigit(): continue
            year = int(parts[0].strip())
            if year < 2020: continue
            ms = parts[1].strip()
            if ms not in month_map: continue
            try:
                elec_rows.append([year, month_map[ms],
                    float(parts[2].replace(' ','')),
                    float(parts[3].replace(' ','')),
                    float(parts[6].replace(' ',''))])
            except: pass
    
    print(f"  ✅ 用電數據：{len(elec_rows)} 個月")
except Exception as e:
    print(f"  ❌ 用電數據讀取失敗：{e}")
    sys.exit(1)

# ── 4. 合併數據 ──────────────────────────────────────────
df_elec = pd.DataFrame(elec_rows, columns=['year','month','domestic','commercial','total'])
df_monthly = pd.merge(monthly_temp, df_elec, on=['year','month'], how='left')
df_monthly = df_monthly.sort_values(['year','month'])

monthly_list = []
for _, r in df_monthly.iterrows():
    monthly_list.append([
        int(r['year']), int(r['month']),
        float(r['avg']), float(r['mx']), float(r['mn']), int(r['cnt']),
        float(r['domestic']) if not pd.isna(r.get('domestic',float('nan'))) else None,
        float(r['commercial']) if not pd.isna(r.get('commercial',float('nan'))) else None,
        float(r['total']) if not pd.isna(r.get('total',float('nan'))) else None,
    ])

# ── 5. 更新 index.html ───────────────────────────────────
print("正在更新 index.html...")
daily_json   = json.dumps(daily_rows,   separators=(',',':'))
monthly_json = json.dumps(monthly_list, separators=(',',':'))
today = datetime.now().strftime('%Y·%m·%d')

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace data arrays
html = re.sub(r'const DAILY = \[.*?\];',   f'const DAILY = {daily_json};',   html, flags=re.DOTALL)
html = re.sub(r'const MONTHLY = \[.*?\];', f'const MONTHLY = {monthly_json};', html, flags=re.DOTALL)
# Update version date
html = re.sub(r'(\d{{4}}·\d{{2}}·\d{{2}})', today, html)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"  ✅ 完成！數據已更新至 {daily_rows[-1][0]}年{daily_rows[-1][1]}月{daily_rows[-1][2]}日")
print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 更新完成 🎉")
