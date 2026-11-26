"""입출차 원본 1년치를 여러 페이지 동시에 받아요 (8번보다 3~4배 빠르게).

8_입출차_1년치 창을 먼저 Ctrl+C로 멈춘 다음 실행하세요. 거기서 받은 페이지는 건너뛰고 나머지만 받아요.
서버 규칙(2초에 1번)을 지키려고 요청 시작 간격은 항상 2.5초 이상이에요.
서버가 한 번에 오래 걸려서(한 페이지 15초 안팎), 여러 개를 겹쳐 보내면 빨라져요.

사용법:
    caffeinate -i python3 fetch_inout_fast.py        동시에 4개
    caffeinate -i python3 fetch_inout_fast.py 3      동시에 3개
멈춰도 다시 실행하면 이어서 받아요. 다 받으면 data/inout_2025.csv 하나로 합쳐요.
"""
import csv
import json
import os
import queue
import sys
import threading
import time

from common import DATA, ApiError, extract, get_key, http_get, load_env, norm_keys, parse_body
from fetch_static import INOUT_FIELDS, INOUT_RE, JSON_HEADERS, KCISA

API = "API_CPM_008"
SIZE = 1000
GAP = 2.5
OUT = DATA / "inout_2025.csv"
PARTS = DATA / "inout_parts"
PROG = DATA / ".inout_progress.json"

_lock = threading.Lock()
_last = [0.0]


def wait_turn():
    with _lock:
        w = _last[0] + GAP - time.time()
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()


def fetch_page(key, page):
    wait_turn()
    text = http_get(f"{KCISA}/{API}/request", {"serviceKey": key, "numOfRows": SIZE, "pageNo": page},
                    headers=JSON_HEADERS, retries=2, timeout=90)
    return extract(parse_body(text))


def to_rows(items):
    rows = []
    for it in items:
        it = norm_keys(it)
        desc = (it.get("DESCRIPTION") or "").strip()
        row = {"id": it.get("LOCALID")}
        m = INOUT_RE.search(desc)
        if m:
            row.update({k: v.strip() for k, v in m.groupdict().items()})
        else:
            row["raw_description"] = desc
        rows.append(row)
    return rows


def save_part(page, rows):
    tmp = PARTS / f"p{page:05d}.tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=INOUT_FIELDS, extrasaction="ignore")
        w.writerows(rows)
    os.replace(tmp, PARTS / f"p{page:05d}.csv")


def merge(first_new, last_page):
    """8번이 받은 앞부분(inout_2025.csv) 뒤에 나머지 페이지를 차례대로 붙여요. 겹친 줄은 빼요."""
    seen = set()
    tmp = DATA / "inout_2025.merging"
    n = dup = 0
    with open(tmp, "w", newline="", encoding="utf-8-sig") as out:
        w = csv.DictWriter(out, fieldnames=INOUT_FIELDS)
        w.writeheader()
        srcs = []
        if OUT.exists() and first_new > 1:
            srcs.append((OUT, True))
        srcs += [(PARTS / f"p{p:05d}.csv", False) for p in range(first_new, last_page + 1)]
        for path, has_head in srcs:
            with open(path, encoding="utf-8-sig", newline="") as f:
                rd = csv.DictReader(f) if has_head else csv.DictReader(f, fieldnames=INOUT_FIELDS)
                for r in rd:
                    if r["id"] in seen:
                        dup += 1
                        continue
                    seen.add(r["id"])
                    w.writerow(r)
                    n += 1
    os.replace(tmp, OUT)
    for p in range(first_new, last_page + 1):
        (PARTS / f"p{p:05d}.csv").unlink(missing_ok=True)
    (PARTS / "meta.json").unlink(missing_ok=True)
    try:
        PARTS.rmdir()
    except OSError:
        pass
    PROG.unlink(missing_ok=True)
    return n, dup


def main():
    load_env()
    key = get_key("KCISA_KEY_INOUT")
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    PARTS.mkdir(parents=True, exist_ok=True)
    first_new = 1
    if PROG.exists() and OUT.exists():
        first_new = json.loads(PROG.read_text())["next_page"]
    meta = PARTS / "meta.json"
    if meta.exists():
        m = json.loads(meta.read_text())
        first_new, total = m["first_new"], m["total"]
    else:
        items, total = fetch_page(key, first_new)
        if not total:
            sys.exit("[중단] 서버가 전체 건수를 알려주지 않았어요. 8번으로 받아 주세요.")
        save_part(first_new, to_rows(items))
        meta.write_text(json.dumps({"first_new": first_new, "total": total}))
    last_page = (total + SIZE - 1) // SIZE
    todo = [p for p in range(first_new, last_page + 1) if not (PARTS / f"p{p:05d}.csv").exists()]
    print(f"전체 {total:,}건, {last_page:,}페이지. 앞 {first_new - 1:,}페이지는 이미 받았고, 남은 {len(todo):,}페이지를 동시에 {workers}개씩 받아요.")
    q = queue.Queue()
    for p in todo:
        q.put(p)
    done = [0]
    fails = []
    t0 = time.time()
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            try:
                p = q.get_nowait()
            except queue.Empty:
                return
            for attempt in range(4):
                try:
                    items, _ = fetch_page(key, p)
                    save_part(p, to_rows(items))
                    break
                except ApiError as e:
                    if attempt == 3:
                        fails.append(p)
                        print(f"  ! {p}페이지 실패: {e}", flush=True)
                    else:
                        time.sleep(10 * (attempt + 1))
            with _lock:
                done[0] += 1
                d = done[0]
            if d % 20 == 0 or d == len(todo):
                el = time.time() - t0
                left = (len(todo) - d) * el / d / 60
                print(f"  {d:,}/{len(todo):,} 페이지 ({el / 60:.0f}분 경과, 약 {left:.0f}분 남음)", flush=True)

    ths = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
    for t in ths:
        t.start()
    try:
        while any(t.is_alive() for t in ths):
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()
        print("\n멈췄어요. 다시 실행하면 받은 페이지는 건너뛰고 이어서 받아요.")
        return
    missing = [p for p in range(first_new, last_page + 1) if not (PARTS / f"p{p:05d}.csv").exists()]
    if missing:
        print(f"아직 못 받은 페이지가 {len(missing)}개 있어요. 다시 실행하면 그것만 받아요.")
        return
    print("다 받았어요. 하나로 합치는 중이에요 (1~2분)...", flush=True)
    n, dup = merge(first_new, last_page)
    print(f"-> data/inout_2025.csv {n:,}행 (겹친 줄 {dup:,}개 뺌, 서버 기준 {total:,}건)")


if __name__ == "__main__":
    main()
