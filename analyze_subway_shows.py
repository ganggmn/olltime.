"""2025 공연 날, 올림픽공원역(5호선)과 몽촌토성역(8호선)에서 내린 사람이 평소보다 얼마나 늘었는지 봐요.

필요한 파일 (data 폴더)
    서울교통공사_역별 일별 시간대별 승하차인원_20251231.csv  (서울 열린데이터광장 OA-12921)
    linked_2025.csv  (8_입출차_1년치로 받은 공연명, 관람객 수)
    performances_ksponco.csv  (공연장 이름 붙이기용, 없어도 돼요)

결과: data/checks/subway_shows.csv, 화면 요약
"""
import csv
import glob
import json
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

from common import DATA

STATIONS = ("올림픽공원", "몽촌토성", "한성백제")
by_line = defaultdict(float)   # (날짜, 노선) -> 하루 하차
WEEK = "월화수목금토일"


def open_any(path):
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            f = open(path, encoding=enc, newline="")
            f.read(4096)
            f.seek(0)
            return f
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"[중단] {path} 글자 인코딩을 못 읽었어요")


def hour_of(col):
    m = re.search(r"(\d{1,2})", col)
    if not m:
        return None
    h = int(m.group(1))
    if "이전" in col:
        return h - 1
    return h


def parse_date(s):
    s = re.sub(r"[^0-9]", "", s)[:8]
    return datetime.strptime(s, "%Y%m%d").date() if len(s) == 8 else None


def load_subway():
    """1~8호선 파일과 9호선 2·3단계 파일이 둘 다 있으면 합쳐요."""
    files = sorted(set(glob.glob(str(DATA / "*역별*일별*시간대별*승하차*.csv")) + glob.glob(str(DATA / "*9호선*시간대별*.csv"))))
    if not files:
        raise SystemExit("[중단] data 폴더에 '서울교통공사_역별 일별 시간대별 승하차인원' 파일이 없어요")
    off = defaultdict(lambda: defaultdict(float))   # off[date][hour]
    on = defaultdict(lambda: defaultdict(float))
    names, all_hours, per_file = set(), set(), {}
    global by_line
    for path in files:
        f = open_any(path)
        rd = csv.reader(f)
        head = next(rd)
        while "역명" not in "".join(head) and "역사명" not in "".join(head):
            head = next(rd)
        col = {name.strip(): i for i, name in enumerate(head)}
        i_date = next(i for n, i in col.items() if "일자" in n or "날짜" in n or "일시" in n)
        i_name = next(i for n, i in col.items() if "역명" in n or "역사명" in n)
        i_kind = next(i for n, i in col.items() if "구분" in n)
        i_line = next((i for n, i in col.items() if "호선" in n), None)
        hours = [(i, hour_of(n)) for n, i in col.items() if "시" in n and i not in (i_date, i_name, i_kind) and hour_of(n) is not None]
        all_hours.update(h for _, h in hours)
        cnt = 0
        for row in rd:
            if len(row) <= max(i for i, _ in hours):
                continue
            nm = row[i_name]
            if not any(s in nm for s in STATIONS):
                continue
            d = parse_date(row[i_date])
            if not d or d.year != 2025:
                continue
            tgt = off if "하차" in row[i_kind] else on if "승차" in row[i_kind] else None
            if tgt is None:
                continue
            ln = (row[i_line] if i_line is not None else "?").replace("호선", "")
            names.add(f"{nm}({ln}호선)")
            if tgt is off:
                by_line[(d, ln)] += sum(float(row[i].replace(",", "") or 0) for i, _ in hours if row[i].strip())
            for i, h in hours:
                try:
                    tgt[d][h] += float(row[i].replace(",", "") or 0)
                except ValueError:
                    pass
            cnt += 1
        per_file[path.split("/")[-1]] = cnt
    return ", ".join(f"{k} {v}줄" for k, v in per_file.items()), names, off, on, sorted(all_hours)


def load_shows():
    shows = defaultdict(dict)   # shows[date][perf] = (first_hour, last_hour, audience)
    for r in csv.DictReader(open(DATA / "linked_2025.csv", encoding="utf-8-sig")):
        a = r.get("perf_audience") or "0"
        if a in ("", "0"):
            continue
        d = date.fromisoformat(r["datetime"][:10])
        h = int(r["datetime"][11:13])
        nm = (r.get("perf_name") or "").strip()
        f, l, aud = shows[d].get(nm, (h, h, 0))
        shows[d][nm] = (min(f, h), max(l, h), max(aud, int(a)))
    return shows


def main():
    path, names, off, on, hours = load_subway()
    shows = load_shows()
    print(f"파일: {path}")
    print(f"찾은 역: {', '.join(sorted(names))}")
    days = sorted(off)
    print(f"날짜: {days[0]} ~ {days[-1]} ({len(days)}일), 시간 칸: {hours[0]}시 ~ {hours[-1]}시")
    show_days = set(shows)
    tot = lambda D, d: sum(D[d].values())

    def base(d, h, D):
        near = [x for x in days if x.weekday() == d.weekday() and x not in show_days and abs((x - d).days) <= 42]
        if len(near) < 3:
            near = [x for x in days if x.weekday() == d.weekday() and x not in show_days]
        return statistics.median(D[x].get(h, 0) for x in near) if near else 0

    out, curve = [], defaultdict(list)
    for d in sorted(show_days):
        if d not in off:
            continue
        perfs = shows[d]
        start = min(f for f, _, _ in perfs.values()) + 1      # 연계 데이터는 시작 1시간 전부터 표시돼요 (2025-12-05, 12-06 기록으로 확인)
        last = max(l for _, l, _ in perfs.values())
        aud = sum(a for _, _, a in perfs.values())
        ext = {h: off[d].get(h, 0) - base(d, h, off) for h in hours}
        ext_on = {h: on[d].get(h, 0) - base(d, h, on) for h in hours}
        arr = sum(ext[h] for h in range(start - 4, start + 1) if h in ext)
        dep = sum(ext_on[h] for h in range(last, last + 3) if h in ext_on)
        day_extra = sum(ext.values())
        if arr > 0:
            for k in range(-4, 1):
                curve[k].append(ext.get(start + k, 0) / arr)
        out.append({"date": d.isoformat(), "weekday": WEEK[d.weekday()], "start_est": f"{start}:00",
                    "perfs": " / ".join(p[:30] for p in perfs), "audience": aud,
                    "extra_off_before": round(arr), "extra_on_after": round(dep), "extra_off_day": round(day_extra),
                    "ratio_before": round(arr / aud, 3) if aud else ""})
    (DATA / "checks").mkdir(exist_ok=True)
    with open(DATA / "checks" / "subway_shows.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    big = [r for r in out if r["audience"] >= 5000]
    rat = [r["ratio_before"] for r in big if r["ratio_before"] != ""]
    xs, ys = [r["audience"] for r in big], [r["extra_off_before"] for r in big]
    r = statistics.correlation(xs, ys) if len(xs) > 2 else float("nan")
    print(f"\n공연 날 {len(out)}일 (관객 5천 명 넘는 날 {len(big)}일)")
    print(f"관객 수와 '시작 전 4시간 동안 늘어난 하차'의 상관계수 {r:.2f}")
    q = statistics.quantiles(rat, n=4) if len(rat) >= 4 else [min(rat), statistics.median(rat), max(rat)]
    print(f"관객 1명당 늘어난 하차 (파일에 있는 역 합계): 중앙값 {statistics.median(rat):.2f}, 25~75% {q[0]:.2f}~{q[-1]:.2f}")
    print("시작 전 도착 비율 (시작 4시간 전 ~ 시작 시각 칸):",
          ", ".join(f"{k:+d}시간 {statistics.median(v) * 100:.0f}%" for k, v in sorted(curve.items())))
    for wd in "금토일":
        L = [x["ratio_before"] for x in big if x["weekday"] == wd and x["ratio_before"] != ""]
        if L:
            print(f"  {wd}요일 {len(L)}일: 관객 1명당 {statistics.median(L):.2f}")
    print("\n관객 많은 날 10개")
    for x in sorted(big, key=lambda x: -x["audience"])[:10]:
        print(f"  {x['date']}({x['weekday']}) {x['start_est']} 관객 {x['audience']:>6,}  시작 전 하차 +{x['extra_off_before']:>6,}"
              f"  끝나고 승차 +{x['extra_on_after']:>6,}  {x['perfs'][:28]}")
    json.dump({"corr": r, "ratio_median": statistics.median(rat), "ratio_q": q, "n": len(big),
               "curve": {k: statistics.median(v) for k, v in curve.items()}},
              open(DATA / "checks" / "subway_shows.json", "w"), ensure_ascii=False, indent=1)
    print("\n자세한 표: data/checks/subway_shows.csv")


if __name__ == "__main__":
    main()
