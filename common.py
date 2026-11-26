"""공통 도구: .env 읽기, API 호출, 응답(JSON/XML) 해석.

인증키는 화면에 절대 출력하지 않습니다. 오류 메시지에도 URL을 넣지 않아요.
외부 패키지 없이 파이썬 기본 기능만 씁니다.
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"

HANGUL = re.compile(r"[가-힣]")


class ApiError(Exception):
    """키가 들어간 URL은 담지 않는 오류."""


def load_env():
    env_path = BASE / ".env"
    if not env_path.exists():
        sys.exit("[중단] 이 폴더에 .env 파일이 없어요. README.md를 보고 .env에 인증키를 넣어주세요.")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")


def get_key(name, required=True):
    v = os.environ.get(name, "").strip()
    # 템플릿 문구(한글)가 그대로 남아 있으면 아직 안 넣은 것으로 봐요.
    if not v or HANGUL.search(v):
        if required:
            sys.exit(f"[중단] .env의 {name} 칸에 인증키가 아직 없어요.")
        return None
    # 공공데이터포털 'Encoding' 키를 넣은 경우에도 동작하도록 한 번 풀어줘요.
    if "%" in v:
        v = urllib.parse.unquote(v)
    return v


def _redact(text, secrets):
    for s in secrets:
        if s:
            text = text.replace(s, "***").replace(urllib.parse.quote(s, safe=""), "***")
    return text


# 서버별 최소 요청 간격(초). 문화공공데이터광장은 "2초에 1번" 제한이 있어요.
MIN_INTERVAL = {"api.kcisa.kr": 2.5}
_last_call = {}


def _throttle(url):
    host = urllib.parse.urlparse(url).hostname or ""
    gap = MIN_INTERVAL.get(host, 0)
    if gap:
        wait = _last_call.get(host, 0) + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.time()


def http_get(url, params=None, headers=None, retries=3, timeout=40, secrets=()):
    secrets = list(secrets) + [str(v) for k, v in (params or {}).items() if "key" in k.lower()]
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers or {})
    errors = []
    tries = 0
    rate_limited = 0
    while tries < retries:
        _throttle(url)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            try:
                body = e.read()[:300].decode("utf-8", errors="replace")
            except Exception:
                body = ""
            body = " ".join(_redact(body, secrets).split())
            if e.code == 429 and rate_limited < 8:
                # 요청 간격 제한: 실패로 치지 않고 잠깐 쉬었다가 다시
                rate_limited += 1
                time.sleep(3 + rate_limited)
                continue
            msg = f"HTTP {e.code}" + (f" / 서버 응답: {body}" if body else "")
            if msg not in errors:
                errors.append(msg)
            if 400 <= e.code < 500:
                break
        except urllib.error.URLError as e:
            reason = e.reason
            if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
                raise ApiError(
                    "SSL 인증서 확인에 실패했어요. 파이썬을 python.org에서 설치했다면 "
                    "Finder > 응용 프로그램 > Python 3.x 폴더의 'Install Certificates.command'를 "
                    "한 번 실행한 뒤 다시 돌려주세요."
                )
            errors.append(_redact(f"접속 실패({reason})", secrets))
        except TimeoutError:
            errors.append("시간 초과")
        tries += 1
        time.sleep(2 * tries)
    raise ApiError(" | ".join(errors) or "알 수 없는 오류")


def _xml_to_obj(elem):
    children = list(elem)
    if not children:
        return (elem.text or "").strip()
    d = {}
    for c in children:
        v = _xml_to_obj(c)
        if c.tag in d:
            if not isinstance(d[c.tag], list):
                d[c.tag] = [d[c.tag]]
            d[c.tag].append(v)
        else:
            d[c.tag] = v
    return d


def parse_body(text):
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return json.loads(text)
    if text.startswith("<"):
        root = ET.fromstring(text)
        return {root.tag: _xml_to_obj(root)}
    raise ApiError("응답 형식을 알 수 없어요: " + text[:120])


def find_first(obj, key):
    """중첩 dict/list에서 key를 처음 찾으면 그 값을 돌려줘요 (대소문자 무시)."""
    lk = key.lower()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() == lk:
                return v
        for v in obj.values():
            r = find_first(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_first(v, key)
            if r is not None:
                return r
    return None


OK_CODES = {"00", "0", "0000", "000", "INFO-000", "NORMAL_SERVICE"}


def extract(obj):
    """(items, totalCount) 반환. 오류 코드면 ApiError."""
    auth = find_first(obj, "returnAuthMsg")
    if auth and auth not in ("NORMAL_SERVICE", "NORMAL_CODE"):
        raise ApiError(f"인증 오류: {auth} (키가 맞는지, 활용신청이 승인됐는지 확인해주세요. 막 발급받았다면 1~2시간 뒤 다시)")
    code = find_first(obj, "resultCode")
    if code is not None and str(code).strip() not in OK_CODES:
        msg = find_first(obj, "resultMsg") or ""
        if str(code).strip() in ("03", "NODATA_ERROR"):
            return [], 0
        raise ApiError(f"API 오류 코드 {code}: {msg}")
    items = find_first(obj, "items")
    if isinstance(items, dict):
        items = items.get("item", items.get("ITEM", []))
    if items in (None, ""):
        items = []
    if isinstance(items, dict):
        items = [items]
    total = find_first(obj, "totalCount")
    try:
        total = int(str(total).strip())
    except (TypeError, ValueError):
        total = None
    return [i for i in items if isinstance(i, dict)], total


def norm_keys(d):
    """LOCAL_ID, localId, local_id 를 모두 LOCALID 로 맞춰요 (API마다 표기가 달라서)."""
    return {str(k).replace("_", "").upper(): v for k, v in d.items()}
