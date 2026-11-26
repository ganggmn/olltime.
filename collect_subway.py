"""서울시 실시간 지하철 도착정보: 올림픽공원 주변 역 4곳을 3분마다 저장해요.

올림픽공원역은 9호선이 '올림픽공원', 5호선이 '올림픽공원(한국체대)'로 따로 잡혀서 둘 다 물어요.

실시간 지하철 API는 하루 최대 1,000번만 부를 수 있어요.
4곳 x 3분 간격 = 1시간에 80번이라 하루 약 11시간 수집할 수 있어요.
(서울시 활용사례 승인으로 한도가 풀리면 INTERVAL을 60으로 줄이고 ACTIVE_FROM을 앞당겨요.)
그래서 공연 날 저녁(시작 2시간 전부터 끝나고 2시간 뒤까지)에 켜두는 걸 권해요.
하루 950번을 넘으면 자정까지 쉬었다가 다시 모아요.

사용법:
    caffeinate -i python3 collect_subway.py
멈출 때는 Ctrl+C. 다시 실행하면 같은 파일에 이어서 쌓여요.

저장 위치 data/subway/
    raw_YYYYMMDD.jsonl.gz  응답 원본
    arrivals.csv           역별 도착 예정 열차
    calls_YYYYMMDD.txt     그날 부른 횟수 (하루 한도 관리용)
"""
import csv
import gzip
import json
import sys
import time
import urllib.parse
from datetime import datetime, timedelta

from common import DATA, ApiError, get_key, http_get, load_env, parse_body

STATIONS = ["올림픽공원", "올림픽공원(한국체대)", "몽촌토성(평화의문)", "한성백제"]
INTERVAL = 180  # 3분
DAILY_LIMIT = 950  # 서울시 한도 1,000번에서 여유를 둬요
# 공연 관객이 오가는 시간만 모아요 (14:30 ~ 다음 날 01:00, 10시간 30분 x 80번 = 840번).
# 사이트(olltime.vercel.app)도 같은 키를 조금 써서 여유를 남겨 둬요.
# 이렇게 하면 창을 며칠 켜 둬도 새벽과 오전에 한도를 다 써 버리지 않아요.
ACTIVE_FROM = (14, 30)
ACTIVE_TO = (1, 0)
OUT = DATA / "subway"
FIELDS = ["collected_at", "statnNm", "subwayId", "updnLine", "trainLineNm", "btrainSttus", "barvlDt",
          "btrainNo", "bstatnNm", "recptnDt", "arvlMsg2", "arvlMsg3", "arvlCd", "lstcarAt", "ordkey"]


def calls_today():
    p = OUT / f"calls_{datetime.now():%Y%m%d}.txt"
    return int(p.read_text()) if p.exists() else 0


def add_call():
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"calls_{datetime.now():%Y%m%d}.txt"
    p.write_text(str(calls_today() + 1))


def fetch(key, station):
    url = f"http://swopenapi.seoul.go.kr/api/subway/{key}/json/realtimeStationArrival/0/40/{urllib.parse.quote(station)}"
    add_call()
    text = http_get(url, retries=2, secrets=[key])
    obj = parse_body(text)
    rows = obj.get("realtimeArrivalList") if isinstance(obj, dict) else None
    if rows is None:
        err = (obj.get("errorMessage") if isinstance(obj, dict) else None) or {}
        code, msg = err.get("code", "?"), err.get("message", "")
        if code == "INFO-200":  # 지금 도착 예정 열차 없음 (밤늦게)
            return obj, []
        raise ApiError(f"{station}: 서울시 응답 {code} {msg}")
    return obj, rows if isinstance(rows, list) else [rows]


def collect_once(key):
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "arrivals.csv"
    new = not path.exists()
    total, notes = 0, []
    with gzip.open(OUT / f"raw_{now:%Y%m%d}.jsonl.gz", "at", encoding="utf-8") as g, \
            open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        for st in STATIONS:
            try:
                obj, rows = fetch(key, st)
            except ApiError as e:  # 한 역이 실패해도 나머지 역은 계속 모아요
                notes.append(f"{st.split('(')[0]} 실패({e})")
                continue
            g.write(json.dumps({"collected_at": stamp, "station": st, "response": obj}, ensure_ascii=False) + "\n")
            for r in rows:
                w.writerow(dict(r, collected_at=stamp))
            total += len(rows)
            notes.append(f"{st.split('(')[0]} {len(rows)}")
    return f"{stamp}  열차 {total}건 ({', '.join(notes)}), 오늘 {calls_today()}번 불렀어요"


def in_window(now):
    m = now.hour * 60 + now.minute
    a, b = ACTIVE_FROM[0] * 60 + ACTIVE_FROM[1], ACTIVE_TO[0] * 60 + ACTIVE_TO[1]
    return m >= a or m < b


def next_start(now):
    st = now.replace(hour=ACTIVE_FROM[0], minute=ACTIVE_FROM[1], second=0, microsecond=0)
    return st if st > now else st + timedelta(days=1)


def main():
    load_env()
    key = get_key("SEOUL_SUBWAY_KEY")
    print("올림픽공원 주변 지하철 도착정보를 14:30~01:00에 3분마다 저장해요(5·8·9호선, 역 4곳). 켜 두면 며칠이고 알아서 그 시간만 모아요. 멈추려면 Ctrl+C")
    while True:
        started = time.time()
        now = datetime.now()
        if not in_window(now):
            nxt = next_start(now)
            print(f"{now:%H:%M}  공연 관객이 오가는 시간이 아니라 {nxt:%m/%d %H:%M}까지 쉬어요.", flush=True)
            time.sleep(max(60, min(3600, (nxt - now).total_seconds())))
            continue
        if calls_today() + len(STATIONS) > DAILY_LIMIT:
            tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=1, second=0)
            print(f"{datetime.now():%H:%M}  오늘 한도에 가까워서 {tomorrow:%m/%d %H:%M}까지 쉬어요.", flush=True)
            time.sleep(max(60, (tomorrow - datetime.now()).total_seconds()))
            continue
        try:
            print(collect_once(key), flush=True)
        except ApiError as e:
            print(f"{datetime.now():%H:%M:%S}  ! {e}", flush=True)
        except Exception as e:  # 네트워크 끊김 등은 다음 회차에 다시 시도
            print(f"{datetime.now():%H:%M:%S}  ! 예상 못한 오류: {type(e).__name__}", flush=True)
        time.sleep(max(5, INTERVAL - (time.time() - started)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n멈췄어요.")
