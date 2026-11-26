"""올림픽공원 주변 버스 정류장과 지하철역의 하루 승하차 인원을 받아요.

서울 열린데이터광장 (이미 쓰고 있는 SEOUL_KEY 그대로, 따로 신청할 필요 없어요)
    버스: 서울시 버스노선별 정류장별 승하차 인원 정보 (OA-12912, CardBusStatisticsServiceNew)
    지하철: 서울시 지하철호선별 역별 승하차 인원 정보 (CardSubwayStatsNew)
교통카드 기준 하루 합계이고, 3일 뒤에 올라와요. (오늘 11/22이면 11/19까지)

이걸로 알 수 있는 것
    공연 날 관객이 버스로 얼마나 오는지 (지하철과 비교한 비중)
    평소 요일별 기준값 (공연 날과의 차이 = 공연 관객 추정)

사용법:
    python3 fetch_ridership.py            최근 40일
    python3 fetch_ridership.py 90         최근 90일
이미 받은 날은 건너뛰니 여러 번 돌려도 괜찮아요.

저장 위치 data/ridership/
    stops.csv              찾은 버스 정류장 목록 (이름, ARS 번호, 지나는 노선)
    bus/YYYYMMDD.csv       그날 해당 정류장 노선별 승하차
    subway/YYYYMMDD.csv    그날 3개 역 호선별 승하차
    summary.csv            날짜별 합계 (버스 하차, 지하철 하차, 버스 비중)
"""
import csv
import statistics
import sys
import time
from datetime import datetime, timedelta

from common import DATA, ApiError, get_key, http_get, load_env

OUT = DATA / "ridership"
# 정류장 이름에 이 낱말이 들어가면 올림픽공원 주변으로 봐요. 결과는 stops.csv에서 꼭 확인해 주세요.
BUS_WORDS = ["올림픽공원", "몽촌토성", "한성백제", "올림픽회관", "평화의문", "올림픽파크텔", "한국체대", "체조경기장"]
SUBWAY_WORDS = ["올림픽공원", "몽촌토성", "한성백제"]
WEEK = "월화수목금토일"
BUS_FIELDS = ["USE_YMD", "RTE_NO", "RTE_NM", "STOPS_ARS_NO", "SBWY_STNS_NM", "GTON_TNOPE", "GTOFF_TNOPE"]
SUB_FIELDS = ["USE_YMD", "SBWY_ROUT_LN_NM", "SBWY_STNS_NM", "GTON_TNOPE", "GTOFF_TNOPE"]


def call(key, svc, a, b, *args):
    path = "/".join(str(x) for x in args)
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{svc}/{a}/{b}/{path}"
    time.sleep(0.15)
    import json
    text = http_get(url, retries=3, timeout=40, secrets=[key])
    obj = json.loads(text)
    body = obj.get(svc)
    if body is None:  # 데이터 없음이나 오류는 RESULT만 와요
        res = obj.get("RESULT") or {}
        if res.get("CODE") == "INFO-200":
            return 0, []
        raise ApiError(f"서울시 응답 {res.get('CODE', '?')} {res.get('MESSAGE', '')}")
    return int(body.get("list_total_count", 0)), body.get("row") or []


def call_all(key, svc, *args):
    total, rows = call(key, svc, 1, 1000, *args)
    start = 1001
    while start <= total:
        _, more = call(key, svc, start, start + 999, *args)
        rows += more
        start += 1000
    return rows


def ymd(d):
    return d.strftime("%Y%m%d")


def latest_day(key):
    d = datetime.now().date() - timedelta(days=2)
    for _ in range(6):
        total, _ = call(key, "CardSubwayStatsNew", 1, 1, ymd(d))
        if total:
            return d
        d -= timedelta(days=1)
    raise ApiError("최근 6일 안에 올라온 승하차 데이터가 없어요")


def clean(name):
    return name.split("(")[0].strip()


def find_stops(key, day):
    """하루치 전체(약 4만 줄)를 한 번 훑어서 주변 정류장과 노선을 찾아요."""
    print(f"{day:%m/%d} 하루치 버스 전체를 훑어서 올림픽공원 주변 정류장을 찾는 중이에요 (1~2분)...", flush=True)
    rows = call_all(key, "CardBusStatisticsServiceNew", ymd(day))
    stops = {}
    for r in rows:
        nm = r.get("SBWY_STNS_NM", "")
        if any(w in nm for w in BUS_WORDS):
            s = stops.setdefault(r["STOPS_ARS_NO"], {"ars": r["STOPS_ARS_NO"], "name": clean(nm), "routes": set()})
            s["routes"].add(r["RTE_NO"])
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "stops.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ars", "name", "routes"])
        for s in sorted(stops.values(), key=lambda s: s["name"]):
            w.writerow([s["ars"], s["name"], " ".join(sorted(s["routes"]))])
    return stops, rows


def load_stops():
    p = OUT / "stops.csv"
    if not p.exists():
        return None
    stops = {}
    for r in csv.DictReader(open(p, encoding="utf-8-sig")):
        stops[r["ars"]] = {"ars": r["ars"], "name": r["name"], "routes": set(r["routes"].split())}
    return stops


def save(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def main():
    load_env()
    key = get_key("SEOUL_KEY")
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    last = latest_day(key)
    print(f"승하차 데이터는 {last:%Y-%m-%d}까지 올라와 있어요. 최근 {days}일을 받아요.", flush=True)

    stops = load_stops()
    first_rows = None
    if not stops:
        stops, first_rows = find_stops(key, last)
    if not stops:
        sys.exit("[중단] 이름이 맞는 정류장을 못 찾았어요. BUS_WORDS를 확인해 주세요.")
    ars = set(stops)
    routes = sorted({rt for s in stops.values() for rt in s["routes"]})
    print(f"정류장 {len(stops)}곳, 노선 {len(routes)}개를 따라가요. (목록: data/ridership/stops.csv)", flush=True)

    empty_run = 0
    for i in range(days):
        d = last - timedelta(days=i)
        bp, sp = OUT / "bus" / f"{ymd(d)}.csv", OUT / "subway" / f"{ymd(d)}.csv"
        if bp.exists() and sp.exists():
            continue
        try:
            srows = [r for r in call_all(key, "CardSubwayStatsNew", ymd(d))
                     if any(w in r.get("SBWY_STNS_NM", "") for w in SUBWAY_WORDS)]
            if i == 0 and first_rows is not None:
                brows = [r for r in first_rows if r.get("STOPS_ARS_NO") in ars]
            else:
                brows = []
                for rt in routes:
                    brows += [r for r in call_all(key, "CardBusStatisticsServiceNew", ymd(d), rt)
                              if r.get("STOPS_ARS_NO") in ars]
        except ApiError as e:
            print(f"{d:%m/%d}  ! {e}", flush=True)
            continue
        if not srows and not brows:
            empty_run += 1
            print(f"{d:%m/%d}  데이터 없음", flush=True)
            if empty_run >= 3:
                print("3일 연속 비어 있어서 여기까지만 받아요. (이 API가 그보다 오래된 날은 안 주는 것 같아요)")
                break
            continue
        empty_run = 0
        if not srows or not brows:  # 한쪽만 비면 그날은 비교에서 빼요 (파일을 안 만들어서 다음에 다시 시도)
            print(f"{d:%m/%d}  {'지하철' if not srows else '버스'} 데이터가 비어 있어서 건너뛰어요", flush=True)
            continue
        save(sp, SUB_FIELDS, srows)
        save(bp, BUS_FIELDS, brows)
        print(f"{d:%m/%d}({WEEK[d.weekday()]})  지하철 하차 {sum(num(r['GTOFF_TNOPE']) for r in srows):>8,.0f}"
              f"   버스 하차 {sum(num(r['GTOFF_TNOPE']) for r in brows):>7,.0f}", flush=True)

    summarize()


def summarize():
    rows = []
    for sp in sorted((OUT / "subway").glob("*.csv")):
        bp = OUT / "bus" / sp.name
        if not bp.exists():
            continue
        sub = list(csv.DictReader(open(sp, encoding="utf-8-sig")))
        bus = list(csv.DictReader(open(bp, encoding="utf-8-sig")))
        if not sub or not bus:
            continue
        d = datetime.strptime(sp.stem, "%Y%m%d").date()
        s_off, s_on = sum(num(r["GTOFF_TNOPE"]) for r in sub), sum(num(r["GTON_TNOPE"]) for r in sub)
        b_off, b_on = sum(num(r["GTOFF_TNOPE"]) for r in bus), sum(num(r["GTON_TNOPE"]) for r in bus)
        rows.append({"date": f"{d:%Y-%m-%d}", "weekday": WEEK[d.weekday()],
                     "subway_off": int(s_off), "subway_on": int(s_on), "bus_off": int(b_off), "bus_on": int(b_on),
                     "bus_share_off": round(b_off / (b_off + s_off), 3) if b_off + s_off else ""})
    if not rows:
        return
    # 평소 기준값: 같은 요일의 하위 25% 값. 공연이 잦은 토요일도 '공연 없는 날'에 가깝게 잡혀요.
    def low(vals):
        vals = sorted(vals)
        return statistics.quantiles(vals, n=4)[0] if len(vals) >= 4 else vals[0]
    base = {}
    for wd in WEEK:
        same = [r for r in rows if r["weekday"] == wd]
        if same:
            base[wd] = (low([r["subway_off"] for r in same]), low([r["bus_off"] for r in same]), len(same))
    for r in rows:
        bs, bb, _ = base[r["weekday"]]
        r["subway_extra"] = int(r["subway_off"] - bs)
        r["bus_extra"] = int(r["bus_off"] - bb)
    save(OUT / "summary.csv", list(rows[0].keys()), rows)

    print(f"\n{rows[0]['date']} ~ {rows[-1]['date']}, {len(rows)}일")
    print("요일별 평소 하차 (같은 요일 하위 25%)")
    for wd, (bs, bb, n) in base.items():
        print(f"  {wd}  지하철 {bs:>8,.0f}   버스 {bb:>7,.0f}   버스 비중 {bb / (bs + bb) * 100 if bs + bb else 0:4.1f}%   ({n}일)")
    cand = []
    for r in rows:
        bs, bb, _ = base[r["weekday"]]
        extra = r["subway_extra"] + r["bus_extra"]
        if extra > 0.2 * (bs + bb):
            cand.append((extra, r))
    cand.sort(key=lambda x: x[0], reverse=True)
    if not cand:
        print("\n평소보다 눈에 띄게 늘어난 날이 없어요.")
    else:
        print("\n평소보다 하차가 20% 넘게 늘어난 날 (공연이나 행사 후보)")
        for extra, r in cand[:12]:
            share = f"{max(0, r['bus_extra']) / extra * 100:4.1f}%"
            print(f"  {r['date']}({r['weekday']})  늘어난 하차 {extra:>+7,}  (지하철 {r['subway_extra']:>+7,}, 버스 {r['bus_extra']:>+6,})"
                  f"   늘어난 사람 중 버스 {share}")
        se = sum(e for e, _ in cand)
        sb = sum(max(0, r["bus_extra"]) for _, r in cand)
        print(f"\n이 날들을 합치면 늘어난 하차 {se:,}명 중 버스가 {sb:,}명 ({sb / se * 100:.1f}%)")
    print("자세한 표: data/ridership/summary.csv")


if __name__ == "__main__":
    try:
        main()
    except ApiError as e:
        sys.exit(f"[중단] {e}")
    except KeyboardInterrupt:
        print("\n멈췄어요. 다시 실행하면 받은 날은 건너뛰고 이어서 받아요.")
