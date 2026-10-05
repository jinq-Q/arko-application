import os,re,hashlib
from datetime import datetime
from io import StringIO
import pandas as pd, requests

URL="https://theater.arko.or.kr/product/performance/year"
BASE=os.environ["SUPABASE_URL"].rstrip("/")
KEY=os.environ["SUPABASE_SECRET_KEY"]
VENUES={"아르코예술극장 대극장","아르코예술극장 소극장","대학로예술극장 대극장","대학로예술극장 소극장"}

def clean(x):
    return "" if pd.isna(x) else re.sub(r"\s+"," ",str(x)).strip()

def period(x,year):
    ds=re.findall(r"(\d{2})-(\d{2})",clean(x))
    if not ds: raise ValueError(f"날짜 파싱 실패: {x}")
    sm,sd=map(int,ds[0]); em,ed=map(int,ds[-1])
    ey=year+(em<sm)
    return f"{year:04d}-{sm:02d}-{sd:02d}",f"{ey:04d}-{em:02d}-{ed:02d}"

year=datetime.now().year
r=requests.get(URL,params={"year":year},headers={"User-Agent":"Mozilla/5.0"},timeout=30)
r.raise_for_status()
table=None
for t in pd.read_html(StringIO(r.text)):
    t.columns=[clean(c) for c in t.columns]
    if {"공연일자","공연장명","공연명"}.issubset(t.columns):
        table=t; break
if table is None: raise RuntimeError("ARKO 연간일정 표를 찾지 못했습니다.")

rows=[]
for _,x in table.iterrows():
    venue=clean(x["공연장명"]); title=clean(x["공연명"])
    if venue not in VENUES or not title: continue
    start,end=period(x["공연일자"],year)
    raw=f"{title}|{venue}|{start}|{end}"
    rows.append({"title":title,"venue":venue,"start_date":start,"end_date":end,"active":True,
                 "source_url":URL,"source_key":"arko-"+hashlib.sha256(raw.encode()).hexdigest()[:32]})
rows=list({x["source_key"]:x for x in rows}.values())
if not rows: raise RuntimeError("수집된 공연이 없습니다.")

h={"apikey":KEY,"Authorization":f"Bearer {KEY}","Content-Type":"application/json",
   "Prefer":"resolution=merge-duplicates,return=minimal"}
res=requests.post(f"{BASE}/rest/v1/performances?on_conflict=source_key",headers=h,json=rows,timeout=30)
res.raise_for_status()
print(f"ARKO 공연 {len(rows)}건 동기화 완료")
