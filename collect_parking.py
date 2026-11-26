"""올림픽공원 실시간 주차 대수: 10분마다 저장해요.

한국체육산업개발이 공개한 주소를 그대로 불러요. 신청할 필요가 없어요.
(공공데이터포털 15168686 '바로가기'에 적힌 공용 키라 비밀이 아니에요.)

돌려주는 값은 숫자 하나예요: 동2문, 남2문, 북2문 주차장을 합친 지금 주차 대수.
전체 주차면 수나 주차장별 대수는 없어요.
장기 주차 차량이 섞여 있어 실제보다 많게 나와요. 새벽에도 빠지지 않는 바닥값을 나중에 빼서 써요.

사용법:
    caffeinate -i python3 collect_parking.py
멈출 때는 Ctrl+C. 다시 실행하면 같은 파일에 이어서 쌓여요.

저장 위치 data/parking/
    parking.csv            collected_at, parking_sum, code, note
    raw_YYYYMMDD.jsonl.gz  응답 원본
"""
import csv
import gzip
import json
import time
from datetime import datetime

from common import DATA, ApiError, http_get, parse_body

URL = "https://www.ksponco.or.kr/online/main/parkingorsApi.do"
PUBLIC_KEY = "PARKING21803504"  # 주최 측이 누리집에 공개한 공용 키
INTERVAL = 600  # 10분
OUT = DATA / "parking"
FIELDS = ["collected_at", "parking_sum", "code", "note"]


def read_value(obj):
    """[{"parking_sum": 1026}] 또는 {"code": "9999", ...} 같은 응답에서 값을 꺼내요."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        obj = obj[0]
    if not isinstance(obj, dict):
        return None, "?", "응답 모양이 예상과 달라요"
    code = str(obj.get("code") or obj.get("resultCode") or "0000")
    val = obj.get("parking_sum")
    try:
        val = int(float(val))
    except (TypeError, ValueError):
        val = None
    note = "" if code == "0000" else ("점검 중" if code == "9999" else str(obj.get("message") or obj.get("msg") or ""))
    return val, code, note


def collect_once():
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    text = http_get(URL, params={"apiKey": PUBLIC_KEY}, retries=3, timeout=20)
    try:
        obj = json.loads(text)
    except ValueError:
        obj = parse_body(text)
    val, code, note = read_value(obj)
    with gzip.open(OUT / f"raw_{now:%Y%m%d}.jsonl.gz", "at", encoding="utf-8") as g:
        g.write(json.dumps({"collected_at": stamp, "response": obj}, ensure_ascii=False) + "\n")
    path = OUT / "parking.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"collected_at": stamp, "parking_sum": "" if val is None else val, "code": code, "note": note})
    shown = f"{val:,}대" if val is not None else "값 없음"
    return f"{stamp}  주차 {shown}" + (f" ({note})" if note else "")


def main():
    print("올림픽공원 실시간 주차 대수를 10분마다 저장해요. 멈추려면 Ctrl+C")
    while True:
        try:
            print(collect_once(), flush=True)
        except ApiError as e:
            print(f"{datetime.now():%H:%M:%S}  ! {e}", flush=True)
        except Exception as e:  # 네트워크 끊김 등은 다음 회차에 다시 시도
            print(f"{datetime.now():%H:%M:%S}  ! 예상 못한 오류: {type(e).__name__}", flush=True)
        # 10분 정각(00, 10, 20 ...)에 맞춰 부르면 나중에 다른 데이터와 붙이기 쉬워요
        wait = INTERVAL - (time.time() % INTERVAL)
        if wait < 60:  # 정각 바로 앞에 불렀으면 그 정각은 건너뛰어요 (몇 초 간격으로 두 번 저장되지 않게)
            wait += INTERVAL
        time.sleep(wait)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n멈췄어요.")
