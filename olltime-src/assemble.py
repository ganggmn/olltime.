"""올타임 웹사이트 원본: head.html + body.html + app.js를 합쳐 옆 폴더 olltime-web/index.html을 만들어요.
사용: python3 assemble.py

데이터(REF, HOURLY, ICONS, ROUTE, SHOWS, LOST, SYN)와 지도 SVG, 길찾기 계산은 data/ 폴더의 조각에서 가져와요."""
import pathlib, re, sys
SRC = pathlib.Path(__file__).parent
OUT = next((SRC.parent / d / 'index.html' for d in ('olltime-web', 'olltime') if (SRC.parent / d).is_dir()), SRC.parent / 'index.html')  # 맥: 옆의 olltime-web, 저장소: 바로 위 폴더
D = SRC / 'data'

def piece(name):
    return (D / name).read_text(encoding='utf-8').rstrip('\n')

def extract_from(old_path):
    """처음 한 번: 예전 index.html에서 데이터 조각을 떼어 data/에 저장해요."""
    s = pathlib.Path(old_path).read_text(encoding='utf-8')
    lines = s.split('\n')
    D.mkdir(exist_ok=True)
    def line_starting(prefix):
        hits = [l for l in lines if l.startswith(prefix)]
        assert len(hits) == 1, (prefix, len(hits))
        return hits[0]
    data = [line_starting(p) for p in ('const REF=', 'const HOURLY=', 'const ICONS=', 'const ROUTE=')]
    a = s.index('const SHOWS=['); b = s.index('];', a) + 2
    data.append(s[a:b])
    data.append(line_starting('const LOST='))
    data.append(line_starting('const SYN='))
    (D / 'data.js').write_text('\n'.join(data) + '\n', encoding='utf-8')
    a = s.index('<svg id="svg"'); b = s.index('</svg>', a) + len('</svg>')
    (D / 'map.svg').write_text(s[a:b] + '\n', encoding='utf-8')
    a = s.index('const mkTravel='); b = s.index('const TR=mkTravel(ROUTE);') + len('const TR=mkTravel(ROUTE);')
    (D / 'travel.js').write_text(s[a:b] + '\n', encoding='utf-8')
    print('extracted to', D)

def build():
    head = (SRC / 'head.html').read_text(encoding='utf-8')
    body = (SRC / 'body.html').read_text(encoding='utf-8')
    app = (SRC / 'app.js').read_text(encoding='utf-8')
    for k, v in (('__MAPSVG__', piece('map.svg')),):
        assert body.count(k) == 1, k
        body = body.replace(k, v)
    acc = (D / 'accuracy.json').read_text(encoding='utf-8') if (D / 'accuracy.json').exists() else 'null'
    import json as _j
    acc = _j.dumps(_j.loads(acc), ensure_ascii=False, separators=(',', ':'))
    for k, v in (('__DATA__', piece('data.js') + '\nconst ACC=' + acc + ';'), ('__TRAVEL__', piece('travel.js'))):
        assert app.count(k) == 1, k
        app = app.replace(k, v)
    out = head + body + app
    for k in ('__MAPSVG__', '__DATA__', '__TRAVEL__'):
        assert k not in out, k
    OUT.write_text(out, encoding='utf-8')
    print('built', OUT, len(out.encode()), 'bytes')

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == 'extract':
        extract_from(sys.argv[2])
    else:
        build()
