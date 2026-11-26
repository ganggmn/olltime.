"""한 번만 받으면 되는 데이터를 data/ 폴더에 CSV로 저장해요.

사용법 (터미널에서 이 폴더로 이동한 뒤):
    python3 fetch_static.py            # holidays weather perf linked 순서로 받기
    python3 fetch_static.py linked     # 골라서 받기: holidays weather linked perf inout

linked(연계 데이터)에는 시간대별 요약과 입출차 원본이 함께 들어 있어서 1~2시간 걸려요.
중간에 끊겨도 다시 실행하면 이어서 받아요. inout은 linked가 안 될 때만 쓰는 예비용이에요.
"""
import csv
import json
import re
import sys
import time
from calendar import monthrange

from common import DATA, ApiError, extract, get_key, http_get, load_env, norm_keys, parse_body

class NoData(ApiError):
    pass


DATA_GO_KR = "https://apis.data.go.kr"
KCISA = "https://api.kcisa.kr/openapi"
JSON_HEADERS = {"Accept": "application/json"}


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for r in rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  -> {path.relative_to(DATA.parent)} ({len(rows):,}행)")


# ---------------------------------------------------------------- 공휴일
def fetch_holidays(years=(2025, 2026)):
    print("[공휴일] 한국천문연구원 특일 정보")
    key = get_key("DATA_GO_KR_KEY")
    rows = []
    for y in years:
        for m in range(1, 13):
            text = http_get(
                f"{DATA_GO_KR}/B090041/openapi/service/SpcdeInfoService/getRestDeInfo",
                {"serviceKey": key, "solYear": y, "solMonth": f"{m:02d}", "numOfRows": 50, "_type": "json"},
            )
            items, _ = extract(parse_body(text))
            for it in items:
                rows.append({"date": str(it.get("locdate")), "name": it.get("dateName"), "is_holiday": it.get("isHoliday")})
            time.sleep(0.2)
    write_csv(DATA / "holidays.csv", rows, ["date", "name", "is_holiday"])


# ---------------------------------------------------------------- 날씨 (ASOS 서울 108)
def fetch_weather(year=2025, stn="108"):
    print(f"[날씨] 기상청 ASOS 시간자료 {year}년 (지점 {stn}=서울)")
    key = get_key("DATA_GO_KR_KEY")
    rows = []
    for m in range(1, 13):
        last = monthrange(year, m)[1]
        page = 1
        while True:
            text = http_get(
                f"{DATA_GO_KR}/1360000/AsosHourlyInfoService/getWthrDataList",
                {
                    "serviceKey": key, "pageNo": page, "numOfRows": 999, "dataType": "JSON",
                    "dataCd": "ASOS", "dateCd": "HR", "stnIds": stn,
                    "startDt": f"{year}{m:02d}01", "startHh": "00",
                    "endDt": f"{year}{m:02d}{last:02d}", "endHh": "23",
                },
            )
            items, total = extract(parse_body(text))
            rows.extend(items)
            if not items or total is None or page * 999 >= total:
                break
            page += 1
        print(f"  {year}-{m:02d}: 누적 {len(rows):,}시간")
        time.sleep(0.2)
    write_csv(DATA / f"weather_asos_{stn}_{year}.csv", rows)


# ---------------------------------------------------------------- 문화공공데이터광장 공통
def kcisa_pages(api_id, key, extra=None, page_size=1000, start_page=1, on_page=None, label=""):
    """페이지를 넘기며 전부 받아요. on_page(items, page)가 있으면 페이지마다 호출."""
    page = start_page
    size = page_size
    got = 0
    total = None
    all_items = []
    headers = JSON_HEADERS

    base = KCISA

    def call(pg, sz, hd, b=None):
        params = {"serviceKey": key, "numOfRows": sz, "pageNo": pg}
        if extra:
            params.update(extra)
        try:
            text = http_get(f"{b or base}/{api_id}/request", params, headers=hd, retries=2)
        except ApiError as e:
            if "From data is null" in str(e):
                raise NoData(str(e))
            raise
        return extract(parse_body(text))

    # 첫 호출은 설정을 바꿔가며 시도해요 (https/http, JSON/XML, 페이지 크기)
    http_base = KCISA.replace("https://", "http://")
    attempts = [(size, JSON_HEADERS, KCISA), (size, {}, http_base), (100, JSON_HEADERS, KCISA),
                (100, {}, http_base), (10, {}, KCISA), (10, {}, http_base)]
    if start_page != 1:
        attempts = [(size, JSON_HEADERS, KCISA), (size, {}, http_base)]
    errors = []
    nodata = 0
    first = None
    for sz, hd, b in attempts:
        tag = f"{sz}건/{'JSON' if hd else 'XML'}/{b.split(':')[0]}"
        try:
            first = call(page, sz, hd, b)
            if (sz, hd, b) != attempts[0]:
                print(f"  {label}설정을 바꿔서 성공했어요 ({tag}).")
            size, headers, base = sz, hd, b
            break
        except NoData as e:
            nodata += 1
            errors.append(f"[{tag}] From data is null")
        except ApiError as e:
            errors.append(f"[{tag}] {e}")
    if first is None:
        if nodata == len(attempts) and extra:
            print(f"  {label}검색 결과가 없어요 (From data is null).")
            return [], 0, size
        if nodata:
            errors.append(
                "→ 'From data is null'은 보통 인증키 문제예요. 문화공공데이터광장은 API마다 활용신청 메일로 "
                "키가 따로 와요. 이 API 메일의 키가 .env의 맞는 칸에 들어갔는지 확인해주세요."
            )
        raise ApiError("모든 방법이 실패했어요:\n    " + "\n    ".join(errors))

    while True:
        if first is not None:
            items, t = first
            first = None
        else:
            try:
                items, t = call(page, size, headers)
            except NoData:
                break
        if t is not None:
            total = t
        if page == 1 and items and total and len(items) < size and total > len(items):
            # 서버가 한 번에 주는 개수에 상한이 있으면 그 크기로 맞춰서 계속 받아요
            size = len(items)
            print(f"  {label}한 번에 {size}건까지만 줘서 그 크기로 받을게요.")
        if not items:
            break
        got += len(items)
        if on_page:
            on_page(items, page, size, total)
        else:
            all_items.extend(items)
        if total is not None and (page * size) >= total:
            break
        page += 1
    return all_items, total, size


# ---------------------------------------------------------------- 연계 데이터 (입출차+공연+날씨, 2025)
LINK_RE = re.compile(
    r"주차대수:(?P<parking>.*?),\s*방문객:(?P<visitors>.*?),\s*기온:(?P<temp>.*?),\s*풍향:(?P<wind>.*?),"
    r"\s*강수량:(?P<rain>.*?),\s*습도:(?P<humidity>.*?),\s*휴일:(?P<holiday>.*?),\s*공연명:(?P<perf_name>.*),"
    r"\s*공연관람객수:(?P<perf_audience>.*)$",
    re.S,
)


def parse_linked(it):
    it = norm_keys(it)
    desc = (it.get("DESCRIPTION") or "").strip()
    if not desc:
        desc = next((str(v).strip() for v in it.values() if isinstance(v, str) and "주차대수" in v), "")
    row = {"id": it.get("LOCALID"), "datetime": it.get("ISSUEDDATE"), "title": it.get("TITLE")}
    m = LINK_RE.search(desc)
    if m:
        row.update({k: v.strip() for k, v in m.groupdict().items()})
    else:
        row["raw_description"] = desc
    # API는 설명 칸이 비어 있고 제목에 "공연명:...,공연관람객수:..."만 와요
    t = TITLE_RE.search(row.get("title") or "")
    if t and not row.get("perf_name") and not row.get("perf_audience"):
        row["perf_name"], row["perf_audience"] = t.group(1).strip(), t.group(2).strip()
    return row


TITLE_RE = re.compile(r"공연명:(.*?)\s*,\s*공연관람객수:\s*(\d+)", re.S)


LINKED_FIELDS = ["id", "datetime", "title", "parking", "visitors", "temp", "wind", "rain", "humidity",
                 "holiday", "perf_name", "perf_audience", "raw_description"]


def fetch_linked():
    """연계 데이터에는 시간대별 요약(추가정보)과 차량 한 대씩의 입출차 원본이 함께 들어 있어요.
    둘을 나눠서 linked_2025.csv(요약)와 inout_2025.csv(원본)로 저장해요."""
    print("[연계] 2025 차량입출차·공연·날씨 연계 데이터 (요약 + 입출차 원본)")
    print("  서버가 2초에 1번만 받아서 1~2시간 걸려요. Ctrl+C로 멈춰도 다시 실행하면 이어받아요.")
    key = get_key("KCISA_KEY_LINKED")
    DATA.mkdir(parents=True, exist_ok=True)
    sum_path, raw_path = DATA / "linked_2025.csv", DATA / "linked_inout_2025.csv"
    prog_path = DATA / ".linked_progress.json"

    start_page, size = 1, 1000
    if prog_path.exists() and sum_path.exists() and raw_path.exists():
        prog = json.loads(prog_path.read_text())
        start_page, size = prog["next_page"], prog["page_size"]
        print(f"  지난번에 이어서 {start_page}페이지부터 받아요.")
    else:
        for path, fields in ((sum_path, LINKED_FIELDS), (raw_path, INOUT_FIELDS)):
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.DictWriter(f, fieldnames=fields).writeheader()

    t0 = time.time()

    def on_page(items, page, page_size, total):
        sums, raws = [], []
        if page == start_page:  # 응답 모양을 나중에 확인할 수 있게 첫 3건을 남겨요 (키는 들어 있지 않아요)
            (DATA / "checks").mkdir(parents=True, exist_ok=True)
            (DATA / "checks" / "linked_sample.json").write_text(json.dumps(items[:3], ensure_ascii=False, indent=1))
        for it in items:
            n = norm_keys(it)
            desc = (n.get("DESCRIPTION") or "").strip()
            if not desc:  # 설명 칸 이름이 다르게 올 때를 대비해 모든 칸에서 찾아요
                desc = next((str(v).strip() for v in n.values() if isinstance(v, str) and ("주차대수" in v or "입구:" in v)), "")
            if "입구:" not in desc or "주차대수" in desc:  # 시간대별 요약 (값이 비어 있어도 시각은 남겨요)
                sums.append(parse_linked(it))
            else:
                # 연계 데이터의 원본 행은 '입차시간' 칸에 문 이름이 잘못 들어 있어서 ISSUED_DATE를 입차시간으로 써요
                row = {"id": n.get("LOCALID"), "entry_time": n.get("ISSUEDDATE")}
                m = INOUT_RE.search(desc)
                if m:
                    g = m.groupdict()
                    row.update(entry_gate=g["entry_gate"].strip(), exit_gate=g["exit_gate"].strip(),
                               exit_time=g["exit_time"].strip())
                else:
                    row["raw_description"] = desc
                raws.append(row)
        for path, fields, rows in ((sum_path, LINKED_FIELDS, sums), (raw_path, INOUT_FIELDS, raws)):
            if rows:
                with open(path, "a", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                    w.writerows(rows)
        prog_path.write_text(json.dumps({"next_page": page + 1, "page_size": page_size, "total": total}))
        if page % 20 == 0 or (total and page * page_size >= total):
            pages = (total // page_size + 1) if total else "?"
            el = (time.time() - t0) / 60
            print(f"  {page:,}/{pages} 페이지 ({el:.0f}분 경과)", flush=True)

    try:
        _, total, _ = kcisa_pages("API_CPM_009", key, page_size=size, start_page=start_page,
                                  on_page=on_page, label="연계: ")
    except KeyboardInterrupt:
        print("\n  멈췄어요. 다시 실행하면 이어서 받아요.")
        return
    prog_path.unlink(missing_ok=True)

    # 요약은 시간순으로 정리
    with open(sum_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: r.get("datetime") or "")
    write_csv(sum_path, rows, LINKED_FIELDS)
    with open(raw_path, encoding="utf-8-sig", newline="") as f:
        n_raw = sum(1 for _ in f) - 1
    filled = sum(1 for r in rows if r.get("parking"))
    print(f"  -> data/linked_2025.csv ({len(rows):,}행 중 주차대수가 들어 있는 행 {filled:,}, 시간대별 요약)")
    print(f"  -> data/linked_inout_2025.csv ({n_raw:,}행, 차량 한 대씩)")
    if rows and not filled:
        print("  ! 서버 응답에 주차대수 같은 값이 비어 있어요. 내려받은 파일 데이터(연계 데이터 CSV)를 쓰면 돼요.")
        print("    응답 모양은 data/checks/linked_sample.json에 남겨 뒀어요.")
    if total:
        print(f"  서버 기준 전체 {total:,}건")


# ---------------------------------------------------------------- 공연정보(통합)에서 한국체육산업개발 것만
def fetch_perf():
    print("[공연] 공연정보(통합) - 한국체육산업개발")
    key = get_key("KCISA_KEY_PERF")
    rows = []
    for kw in ("한국체육산업개발(주)", "한국체육산업개발", None):
        extra = {"keyword": kw} if kw else None
        label = f"공연({kw or '전체'}): "
        try:
            items, total, _ = kcisa_pages("API_CCA_144", key, extra=extra, label=label)
        except ApiError as e:
            print(f"  {label}실패 - {e}")
            continue
        if kw is None and items:
            print(f"  전체 {len(items):,}건을 받아서 한국체육산업개발·올림픽공원 공연만 골라요.")
            pat = re.compile(r"체육산업개발|올림픽공원|올림픽홀|KSPO|핸드볼경기장|티켓링크 라이브|88잔디마당|우리금융아트홀|뮤즈라이브")
            items = [i for i in items if pat.search(" ".join(str(v) for v in i.values()))]
        if items:
            rows = items
            print(f"  {label}{len(items):,}건 찾았어요.")
            break
    if not rows:
        print("  ! 한국체육산업개발 공연을 못 찾았어요. 연계 데이터의 공연명으로 대신할게요.")
    write_csv(DATA / "performances_ksponco.csv", rows)


# ---------------------------------------------------------------- 입출차 원본 2025 (수백만 건, 이어받기 지원)
INOUT_RE = re.compile(
    r"입구:(?P<entry_gate>.*?),\s*입차시간:(?P<entry_time>.*?),\s*출구:(?P<exit_gate>.*?),\s*출차시간:(?P<exit_time>.*)$",
    re.S,
)
INOUT_FIELDS = ["id", "entry_gate", "entry_time", "exit_gate", "exit_time", "raw_description"]


def fetch_inout():
    print("[입출차] 올림픽공원 2025 입출차정보 원본 (서버가 2초에 1번만 받아서 1~2시간 걸려요. Ctrl+C로 멈춰도 다음에 이어받아요)")
    key = get_key("KCISA_KEY_INOUT")
    out = DATA / "inout_2025.csv"
    prog_path = DATA / ".inout_progress.json"
    DATA.mkdir(parents=True, exist_ok=True)

    start_page, size = 1, 1000
    if prog_path.exists() and out.exists():
        prog = json.loads(prog_path.read_text())
        start_page, size = prog["next_page"], prog["page_size"]
        print(f"  지난번에 이어서 {start_page}페이지부터 받아요.")
    else:
        with open(out, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=INOUT_FIELDS).writeheader()

    t0 = time.time()

    def on_page(items, page, page_size, total):
        with open(out, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=INOUT_FIELDS, extrasaction="ignore")
            for it in items:
                it = norm_keys(it)
                desc = (it.get("DESCRIPTION") or "").strip()
                row = {"id": it.get("LOCALID")}
                m = INOUT_RE.search(desc)
                if m:
                    row.update({k: v.strip() for k, v in m.groupdict().items()})
                else:
                    row["raw_description"] = desc
                w.writerow(row)
        prog_path.write_text(json.dumps({"next_page": page + 1, "page_size": page_size, "total": total}))
        if page % 20 == 0 or (total and page * page_size >= total):
            pages = (total // page_size + 1) if total else "?"
            el = time.time() - t0
            print(f"  {page:,}/{pages} 페이지 ({el/60:.1f}분 경과)")

    try:
        _, total, size = kcisa_pages("API_CPM_008", key, page_size=size, start_page=start_page,
                                     on_page=on_page, label="입출차: ")
    except KeyboardInterrupt:
        print("\n  멈췄어요. 다시 실행하면 이어서 받아요.")
        return
    prog_path.unlink(missing_ok=True)
    print(f"  -> data/inout_2025.csv 완료 (서버 기준 전체 {total:,}건)" if total else "  -> data/inout_2025.csv 완료")


STEPS = {
    "holidays": fetch_holidays,
    "weather": fetch_weather,
    "linked": fetch_linked,
    "perf": fetch_perf,
    "inout": fetch_inout,
}


def main():
    load_env()
    chosen = sys.argv[1:] or ["holidays", "weather", "perf", "linked"]
    for name in chosen:
        if name not in STEPS:
            sys.exit(f"모르는 단계예요: {name} (가능: {' '.join(STEPS)})")
    failed = []
    for name in chosen:
        try:
            STEPS[name]()
        except ApiError as e:
            print(f"  ! {name} 실패: {e}")
            failed.append(name)
        print()
    if failed:
        print("실패한 단계:", " ".join(failed))
        print(f"고친 뒤 이렇게 다시 돌리면 돼요: python3 fetch_static.py {' '.join(failed)}")
    else:
        print("전부 끝났어요. data 폴더를 확인해주세요.")


if __name__ == "__main__":
    main()
