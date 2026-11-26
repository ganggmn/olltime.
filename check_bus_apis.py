"""공공데이터포털 API 3개가 우리 키로 되는지, 올림픽공원에 쓸 만한 값이 오는지 확인해요.

먼저 공공데이터포털(data.go.kr)에서 아래 3개를 '활용신청' 해 주세요. 모두 자동 승인이에요.
    1) 서울특별시_정류소정보조회 서비스        (15000303)  주변 정류장, 정류장별 실시간 도착
    2) 서울특별시_대중교통환승경로 조회 서비스  (검색해서 신청)  출발지→공원 버스+지하철 경로와 시간
    3) 한국교통안전공단_주차정보 (15099883)     공원 주차장 면수, 주변 주차장
    4) 국토교통부_정류장별 노선별 이용량 (15142065)  하남 30-3, 30-5, 35 같은 경기 버스 승객도 잡히는지
승인 직후에는 1~2시간 동안 '등록되지 않은 키' 오류가 날 수 있어요. 그땐 조금 뒤에 다시 돌려 주세요.

키는 .env의 DATA_GO_KR_KEY를 그대로 써요. 화면에 키는 나오지 않아요.
결과는 data/checks/에 저장해요.
"""
import json
import urllib.parse
from datetime import datetime, timedelta

from common import DATA, ApiError, get_key, http_get, load_env

OUT = DATA / "checks"
PARK = (127.1215, 37.5205)      # 올림픽공원 가운데 쯤 (경도, 위도)
DOME = (127.1272, 37.5192)      # KSPO DOME
GAEBONG = (126.8586, 37.4946)   # 예시 출발지: 개봉역


def ws(key, path, **params):
    """서울시 버스 API (ws.bus.go.kr). 결과 코드와 목록을 돌려줘요."""
    params = dict(serviceKey=key, resultType="json", **params)
    text = http_get(f"http://ws.bus.go.kr/api/rest/{path}", params=params, retries=2, timeout=30)
    try:
        obj = json.loads(text)
    except ValueError:
        # 키 오류는 XML로 오기도 해요
        msg = text.split("<returnAuthMsg>")[-1].split("<")[0] if "returnAuthMsg" in text else text[:120]
        raise ApiError(f"응답이 JSON이 아니에요: {msg}")
    head = obj.get("msgHeader") or {}
    code, msg = str(head.get("headerCd", "?")), head.get("headerMsg", "")
    items = (obj.get("msgBody") or {}).get("itemList") or []
    if isinstance(items, dict):
        items = [items]
    if code not in ("0", "4"):  # 4 = 결과 없음
        raise ApiError(f"결과 코드 {code} {msg}")
    return items


def check_stations(key, report):
    print("\n1) 올림픽공원 주변 버스 정류장 + 실시간 도착")
    stops = ws(key, "stationinfo/getStationByPos", tmX=PARK[0], tmY=PARK[1], radius=900)
    report["stations"] = stops
    print(f"   반경 900m 안 정류장 {len(stops)}곳")
    for s in sorted(stops, key=lambda s: float(s.get("dist", 0)))[:12]:
        print(f"   - {s.get('stationNm')} (ARS {s.get('arsId')}, {s.get('dist')}m)")
    arrivals = {}
    for s in stops[:4]:
        ars = s.get("arsId")
        if not ars or ars == "0":
            continue
        items = ws(key, "stationinfo/getStationByUid", arsId=ars)
        arrivals[ars] = items
        sample = ", ".join(f"{i.get('rtNm')} {i.get('arrmsg1')}" for i in items[:4])
        print(f"   {s.get('stationNm')}: 노선 {len(items)}개  예) {sample}")
    report["arrivals"] = arrivals


def check_path(key, report):
    print("\n2) 개봉역 → KSPO DOME 대중교통 경로 (버스 포함)")
    items = ws(key, "pathinfo/getPathInfoByBusNSub",
               startX=GAEBONG[0], startY=GAEBONG[1], endX=DOME[0], endY=DOME[1])
    report["path"] = items
    print(f"   경로 {len(items)}개")
    for it in items[:5]:
        legs = it.get("pathList") or []
        if isinstance(legs, dict):
            legs = [legs]
        how = " → ".join(f"{l.get('routeNm')}({l.get('fname')}~{l.get('tname')})" for l in legs)
        print(f"   - {it.get('time')}분, {it.get('distance')}m: {how}")


def kotsa(key, op, **extra):
    base = "https://apis.data.go.kr/B553881/Parking_v1"
    params = dict(serviceKey=key, pageNo=1, numOfRows=1000, format=2, sidoCd="11", sigunguCd="11710", **extra)
    last = None
    for path in (op, op + "_v1"):  # 문서마다 이름이 달라서 둘 다 시도해요
        try:
            text = http_get(f"{base}/{path}", params=params, retries=1, timeout=30)
        except ApiError as e:
            last = e
            continue
        try:
            obj = json.loads(text)
        except ValueError:
            last = ApiError(f"{op}: JSON이 아니에요 ({text[:100].strip()})")
            continue
        return path, obj
    raise last or ApiError(f"{op}: 응답 없음")


def records(obj, op):
    """응답 안에서 주차장 목록(딕셔너리들의 리스트)을 찾아요."""
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            if op in o and isinstance(o[op], list):
                return o[op]
            stack.extend(o.values())
        elif isinstance(o, list):
            if o and all(isinstance(x, dict) for x in o) and len(o[0]) > 3:
                return o
            stack.extend(o)
    return []


def check_kotsa(key, report):
    print("\n3) 한국교통안전공단 주차정보 (송파구)")
    path, obj = kotsa(key, "PrkSttusInfo")
    lots = records(obj, "PrkSttusInfo")
    print(f"   시설정보 {len(lots)}곳 ({path})")
    if lots:
        print(f"   항목 이름: {', '.join(lots[0].keys())}")
    hits = [r for r in lots if "올림픽" in json.dumps(r, ensure_ascii=False)]
    report["kotsa_lots"] = hits
    print(f"   이름이나 주소에 '올림픽'이 들어간 곳 {len(hits)}곳")
    for r in hits[:10]:
        print("   - " + json.dumps(r, ensure_ascii=False)[:300])
    ids = set()
    for r in hits:
        for k, v in r.items():
            if "id" in k.lower() or k.lower().endswith("_cd"):
                ids.add(str(v))
    for op in ("PrkOprInfo", "PrkRealtimeInfo"):
        try:
            p, o = kotsa(key, op)
        except ApiError as e:
            print(f"   {op}: ! {e}")
            continue
        rows = records(o, op)
        mine = [r for r in rows if ids & {str(v) for v in r.values()}]
        report[op] = mine
        print(f"   {op}: 송파구 {len(rows)}곳 중 올림픽공원 쪽 {len(mine)}곳")
        for r in mine[:5]:
            print("     " + json.dumps(r, ensure_ascii=False)[:300])


def check_molit(key, report):
    """국토교통부 정류장별 노선별 하루 이용량: 경기 버스(하남 30-3, 30-5, 35 등)까지 들어 있는지 봐요."""
    print("\n4) 국토교통부 정류장별 노선별 이용량 (송파구)")
    url = "https://apis.data.go.kr/1613000/StopbyRouteTripVolume/getDailyStopbyRouteTripVolume"
    words = ("올림픽공원", "몽촌토성", "한성백제", "올림픽회관", "평화의문")
    for back in range(3, 15):
        day = (datetime.now() - timedelta(days=back)).strftime("%Y%m%d")
        rows, page, total = [], 1, None
        while True:
            text = http_get(url, params=dict(serviceKey=key, pageNo=page, numOfRows=1000, opr_ymd=day,
                                             ctpv_cd="11", sgg_cd="11710", dataType="JSON"), retries=2, timeout=40)
            try:
                obj = json.loads(text)
            except ValueError:
                raise ApiError(f"JSON이 아니에요 ({text[:120].strip()})")
            body = (obj.get("response") or obj).get("body") or {}
            items = body.get("items") or {}
            got = items.get("item") if isinstance(items, dict) else items
            got = [got] if isinstance(got, dict) else (got or [])
            if not got and not rows:
                head = (obj.get("response") or obj).get("header") or {}
                if head.get("resultCode") not in (None, "00", "0", "INFO-000", "03"):
                    raise ApiError(f"결과 코드 {head.get('resultCode')} {head.get('resultMsg', '')}")
            rows += got
            total = int(body.get("totalCount") or len(rows))
            if len(rows) >= total or not got or page >= 30:
                break
            page += 1
        if rows:
            break
        print(f"   {day}: 데이터 없음, 하루 전으로")
    if not rows:
        print("   최근 2주 안에 데이터가 없어요.")
        return
    print(f"   {day} 송파구 {len(rows)}줄, 항목 이름: {', '.join(rows[0].keys())}")
    near = [r for r in rows if any(w in json.dumps(r, ensure_ascii=False) for w in words)]
    report["molit_day"], report["molit_rows"] = day, near
    print(f"   올림픽공원 주변 정류장 줄 {len(near)}개")
    names = set()
    for r in near:
        for k, v in r.items():
            if "rte" in k.lower() or "route" in k.lower() or "노선" in k:
                names.add(str(v))
    print(f"   지나는 노선(이름/번호 칸): {', '.join(sorted(names))[:600]}")
    gg = [n for n in names if n.strip().split("번")[0] in ("30-3", "30-5", "35")]
    print("   하남 30-3, 30-5, 35가 " + ("보여요 → 경기 버스 승객도 셀 수 있어요" if gg else "안 보여요 → 아래 줄을 보고 확인이 필요해요"))
    for r in near[:5]:
        print("   - " + json.dumps(r, ensure_ascii=False)[:300])


def main():
    load_env()
    key = get_key("DATA_GO_KR_KEY")
    report = {"checked_at": f"{datetime.now():%Y-%m-%d %H:%M:%S}"}
    for name, fn in (("정류소", check_stations), ("환승경로", check_path), ("주차정보", check_kotsa), ("국토부이용량", check_molit)):
        try:
            fn(key, report)
        except ApiError as e:
            report[name + "_error"] = str(e)
            print(f"   ! {e}")
            print("   → 활용신청을 했는지, 승인 뒤 1~2시간이 지났는지 확인해 주세요.")
        except Exception as e:
            report[name + "_error"] = type(e).__name__
            print(f"   ! 예상 못한 오류: {type(e).__name__}")
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"bus_apis_{datetime.now():%Y%m%d_%H%M}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n결과 저장: data/checks/{p.name}")


if __name__ == "__main__":
    main()
