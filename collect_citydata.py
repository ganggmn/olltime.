"""서울시 실시간 도시데이터에서 '올림픽공원'을 5분마다 저장해요.

사용법 (맥북이 잠들지 않게 caffeinate와 같이):
    caffeinate -i python3 collect_citydata.py
멈출 때는 Ctrl+C. 다시 실행하면 같은 파일에 이어서 쌓여요.

저장 위치 data/citydata/
    raw_YYYYMMDD.jsonl.gz  응답 원본 (나중에 다른 항목이 필요할 때 다시 꺼내 쓰는 용도)
    ppltn.csv              실시간 인구·혼잡도
    fcst.csv               서울시가 낸 향후 12시간 예측 (우리 모델과 비교할 기준)
    parking.csv            주변 주차장 현황
    weather.csv            날씨·대기질
    events.csv             주변 문화행사
"""
import csv
import gzip
import json
import sys
import time
import urllib.parse
from datetime import datetime

from common import DATA, ApiError, get_key, http_get, load_env, parse_body

AREA = "올림픽공원"
INTERVAL = 300  # 5분
OUT = DATA / "citydata"

TABLES = {
    "ppltn": ["collected_at", "PPLTN_TIME", "AREA_CONGEST_LVL", "AREA_PPLTN_MIN", "AREA_PPLTN_MAX",
              "NON_RESNT_PPLTN_RATE", "RESNT_PPLTN_RATE", "AREA_CONGEST_MSG"],
    "fcst": ["collected_at", "PPLTN_TIME", "FCST_TIME", "FCST_CONGEST_LVL", "FCST_PPLTN_MIN", "FCST_PPLTN_MAX"],
    "parking": ["collected_at", "PRK_NM", "PRK_CD", "PRK_TYPE", "CPCTY", "CUR_PRK_CNT", "CUR_PRK_TIME", "CUR_PRK_YN"],
    "weather": ["collected_at", "WEATHER_TIME", "TEMP", "SENSIBLE_TEMP", "HUMIDITY", "WIND_SPD", "PRECIPITATION",
                "PRECPT_TYPE", "PCP_MSG", "PM10", "PM25", "AIR_IDX"],
    "events": ["collected_at", "EVENT_NM", "EVENT_PERIOD", "EVENT_PLACE", "EVENT_ETC_DETAIL"],
}


def as_list(v):
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


def append(table, rows):
    if not rows:
        return
    path = OUT / f"{table}.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TABLES[table], extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def collect_once(key):
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/citydata/1/5/{urllib.parse.quote(AREA)}"
    text = http_get(url)
    obj = parse_body(text)

    # 원본은 압축해서 그대로 보관
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / f"raw_{now:%Y%m%d}.jsonl.gz", "at", encoding="utf-8") as f:
        f.write(json.dumps({"collected_at": stamp, "response": obj}, ensure_ascii=False) + "\n")

    city = obj.get("CITYDATA") if isinstance(obj, dict) else None
    if not city:
        result = obj.get("RESULT") or obj.get("result") or {}
        code = result.get("RESULT.CODE") or result.get("CODE") or "?"
        msg = result.get("RESULT.MESSAGE") or result.get("MESSAGE") or ""
        raise ApiError(f"서울시 응답 오류 {code}: {msg}")

    ppl = as_list(city.get("LIVE_PPLTN_STTS"))
    append("ppltn", [dict(p, collected_at=stamp) for p in ppl])
    fc = []
    for p in ppl:
        for f_ in as_list(p.get("FCST_PPLTN")):
            fc.append(dict(f_, collected_at=stamp, PPLTN_TIME=p.get("PPLTN_TIME")))
    append("fcst", fc)
    append("parking", [dict(p, collected_at=stamp) for p in as_list(city.get("PRK_STTS"))])
    append("weather", [dict(w, collected_at=stamp) for w in as_list(city.get("WEATHER_STTS"))])
    append("events", [dict(e, collected_at=stamp) for e in as_list(city.get("EVENT_STTS"))])

    p0 = ppl[0] if ppl else {}
    return (f"{stamp}  혼잡도 {p0.get('AREA_CONGEST_LVL', '?')} "
            f"({p0.get('AREA_PPLTN_MIN', '?')}~{p0.get('AREA_PPLTN_MAX', '?')}명), "
            f"예측 {len(fc)}건, 주차장 {len(as_list(city.get('PRK_STTS')))}곳")


def main():
    load_env()
    key = get_key("SEOUL_KEY")
    print(f"'{AREA}' 실시간 도시데이터를 5분마다 저장해요. 멈추려면 Ctrl+C")
    fails = 0
    while True:
        started = time.time()
        try:
            print(collect_once(key), flush=True)
            fails = 0
        except ApiError as e:
            fails += 1
            print(f"{datetime.now():%H:%M:%S}  ! {e}", flush=True)
            if fails == 1 and "INFO-200" in str(e):
                print("  (장소 이름이 안 맞을 수 있어요. 갱민님이 저한테 이 메시지를 보여주세요.)")
        except Exception as e:  # 네트워크 끊김 등은 다음 회차에 다시 시도
            fails += 1
            print(f"{datetime.now():%H:%M:%S}  ! 예상 못한 오류: {type(e).__name__}", flush=True)
        try:
            time.sleep(max(5, INTERVAL - (time.time() - started)))
        except KeyboardInterrupt:
            print("\n멈췄어요.")
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n멈췄어요.")
