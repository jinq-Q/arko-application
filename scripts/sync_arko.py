import os
import re
import json
import hashlib
import html
from datetime import datetime

import requests


URL = "https://theater.arko.or.kr/product/performance/year"
BASE = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SECRET_KEY"]

VENUES = {
    "아르코예술극장 대극장",
    "아르코예술극장 소극장",
    "대학로예술극장 대극장",
    "대학로예술극장 소극장",
}


def parse_period(value, year):
    """01-03 ~ 01-04 또는 01-03 형식을 날짜로 변환"""
    dates = re.findall(r"(\d{1,2})-(\d{1,2})", value)

    if not dates:
        raise ValueError(f"날짜 파싱 실패: {value}")

    start_month, start_day = map(int, dates[0])
    end_month, end_day = map(int, dates[-1])

    end_year = year
    if end_month < start_month:
        end_year += 1

    start_date = f"{year:04d}-{start_month:02d}-{start_day:02d}"
    end_date = f"{end_year:04d}-{end_month:02d}-{end_day:02d}"

    return start_date, end_date


year = datetime.now().year

response = requests.get(
    URL,
    params={"year": year},
    headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml",
    },
    timeout=30,
)
response.raise_for_status()

page = html.unescape(response.text)

# Vue data 안의 Schedule 배열 추출
match = re.search(
    r'["\']Schedule["\']\s*:\s*(\[\s*\{.*?\}\s*\])\s*,\s*["\']',
    page,
    re.S,
)

if not match:
    raise RuntimeError("ARKO 페이지에서 Schedule 데이터를 찾지 못했습니다.")

schedule = json.loads(match.group(1))

rows = []

for month in schedule:
    for day in month.get("Days", []):

        venue = str(day.get("Place") or "").strip()
        title = str(day.get("Title") or "").strip()
        period_text = str(day.get("Period") or "").strip()

        if venue not in VENUES:
            continue

        if not title or not period_text:
            continue

        start_date, end_date = parse_period(period_text, year)

        raw_key = f"{title}|{venue}|{start_date}|{end_date}"

        rows.append({
            "title": title,
            "venue": venue,
            "start_date": start_date,
            "end_date": end_date,
            "active": True,
            "source_url": URL,
            "source_key": "arko-" + hashlib.sha256(
                raw_key.encode("utf-8")
            ).hexdigest()[:32],
        })


# 중복 제거
unique_rows = {
    row["source_key"]: row
    for row in rows
}

rows = list(unique_rows.values())

if not rows:
    raise RuntimeError(
        "ARKO Schedule은 찾았지만 대상 공연장에서 수집된 공연이 없습니다."
    )

headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

result = requests.post(
    f"{BASE}/rest/v1/performances?on_conflict=source_key",
    headers=headers,
    json=rows,
    timeout=30,
)

result.raise_for_status()

print(f"ARKO 공연 {len(rows)}건 동기화 완료")
