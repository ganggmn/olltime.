"""인증키 점검: 각 API를 3건만 불러서 되는지 확인해요. 키는 화면에 나오지 않아요."""
import re
import urllib.parse

from common import ApiError, _redact, get_key, http_get, load_env

KCISA_APIS = [
    ("KCISA_KEY_LINKED", "API_CPM_009", "연계 데이터"),
    ("KCISA_KEY_PERF", "API_CCA_144", "공연정보(통합)"),
    ("KCISA_KEY_INOUT", "API_CPM_008", "2025 입출차정보"),
]


def short(text, key):
    return " ".join(_redact(text, [key]).split())[:180]


def main():
    load_env()
    for env, api, name in KCISA_APIS:
        key = get_key(env, required=False)
        print(f"\n[{name}] .env의 {env}")
        if not key:
            print("  키가 비어 있어요 (건너뜀)")
            continue
        shape = "UUID 형식(8-4-4-4-12)" if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", key) else "UUID 형식 아님"
        print(f"  키 길이 {len(key)}자, {shape}")
        for scheme in ("https", "http"):
            for hd in ({"Accept": "application/json"}, {}):
                tag = f"{scheme}/{'JSON' if hd else 'XML'}"
                try:
                    text = http_get(f"{scheme}://api.kcisa.kr/openapi/{api}/request",
                                    {"serviceKey": key, "numOfRows": 3, "pageNo": 1}, headers=hd, retries=1)
                    print(f"  {tag}: 응답 → {short(text, key)}")
                except ApiError as e:
                    print(f"  {tag}: 실패 → {short(str(e), key)}")

    key = get_key("SEOUL_KEY", required=False)
    print("\n[서울 실시간 도시데이터] .env의 SEOUL_KEY")
    if key:
        try:
            text = http_get(f"http://openapi.seoul.go.kr:8088/{key}/json/citydata/1/5/{urllib.parse.quote('올림픽공원')}",
                            retries=1, secrets=[key])
            print(f"  응답 → {short(text, key)}")
        except ApiError as e:
            print(f"  실패 → {short(str(e), key)}")
    else:
        print("  키가 비어 있어요")
    print("\n점검 끝. 이 창의 내용을 그대로 복사해서 보내주세요.")


if __name__ == "__main__":
    main()
