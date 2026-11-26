"""2024·2025년 KSPO DOME 공연 날에 공통된 패턴이 있는지 봐요(오륜동 생활인구, 시간별, 성별·나이 포함).
사용: data 폴더에서 python3 ../analysis/patterns.py
필요: ~/oryun_demo.pkl(LOCAL_PEOPLE_DONG 2024~2025에서 오륜동만 뽑은 것), ../analysis/kopis_daily_*.csv(공연장별 하루 판매수),
      ../analysis/kopis_meta_2024_2025.csv(공연 상세: 기간, 공연 시각, 가격, 내한 여부), ~/past3.pkl(2025 공연 시각), checks/park_population_2025_hourly_poi127_full.csv(맞는지 확인)
오륜동은 올림픽공원과 둘레 아파트를 품은 행정동이에요. 2024년엔 250m 칸 자료가 없어 두 해를 같은 잣대로 보려고 오륜동을 써요.
KSPO DOME 공연이 없는 주말은 대부분 다른 공연장·88잔디마당 축제가 있는 날이라 '공연 없는 날'과 비교하면 주말 공연 몫이 0에 가깝게 나와요.
그래서 같은 날 종류(월~목/금/토/일·공휴일)의 다른 KSPO DOME 공연 날과 비교해요.
지표(공연 시작 시각 기준, 오전 10시 대비 늘어난 사람)
  크기 배율: 같은 날 종류 공연 날들의 시작 시각 기준 중앙값 모양에 비해 몇 배인지(시작 −3~+3시간)
  일찍 옴: 시작 3시간 전 증가 ÷ 시작 1시간 뒤 증가
  남아 있음: 시작 4시간 뒤 증가 ÷ 시작 1시간 뒤 증가
  가장 많은 시각: 시작 기준 몇 시간 뒤
  관객층: 오전 10시 → 시작~+2시간에 늘어난 사람(늘어난 쪽만)의 여성 비율, 나이대 비율
  다른 공연장 판매수: 같은 날 핸드볼경기장·올림픽홀·우리금융아트홀·88잔디마당·공원 일대 판매수 합"""
import os, re, glob, pickle, json, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
D = pickle.load(open(os.path.expanduser('~/oryun_demo.pkl'), 'rb')); rows = []
for ym, (hdr, rs) in D.items(): rows += rs
hdr = list(D[next(iter(D))][0]); X = pd.DataFrame(rows, columns=hdr)
X['d'] = pd.to_datetime(X['기준일ID']).dt.strftime('%Y-%m-%d'); X['h'] = X['시간대구분'].astype(int)
num = hdr[3:]; X[num] = X[num].apply(pd.to_numeric, errors='coerce').fillna(0)
AGE = {'10대': (10, 19), '20대': (20, 29), '30대': (30, 39), '40대': (40, 49), '50대': (50, 59), '60대 이상': (60, 200)}
def cols(sex, lo, hi):
    out = []
    for c in num[1:]:
        if not c.startswith(sex): continue
        m = re.findall(r'(\d+)세', c); a = int(m[0])
        b = int(m[1]) if len(m) > 1 else 200
        if a >= lo and b <= hi: out.append(c)
    return out
X['여'] = X[[c for c in num[1:] if c.startswith('여자')]].sum(axis=1); X['남'] = X[[c for c in num[1:] if c.startswith('남자')]].sum(axis=1)
for k, (lo, hi) in AGE.items(): X[k] = X[cols('남자', lo, hi) + cols('여자', lo, hi)].sum(axis=1)
X['20~30대 여성'] = X[cols('여자', 20, 39)].sum(axis=1)
VALS = ['총생활인구수', '여', '남', *AGE, '20~30대 여성']
Y = {v: X.pivot_table(index='d', columns='h', values=v) for v in VALS}
days = sorted(d for d in Y['총생활인구수'].index if Y['총생활인구수'].loc[d].notna().sum() == 24)
TOT = Y['총생활인구수'].loc[days]
# ---------- 공연 날(KOPIS 판매수) + 시작 시각
K = pd.concat([pd.read_csv(f, dtype={'from': str}) for f in sorted(glob.glob('../analysis/kopis_daily_202[45]*.csv'))]).drop_duplicates(['from', 'prfnmplc'])
K['d'] = pd.to_datetime(K['from']).dt.strftime('%Y-%m-%d')
DOME = K[K.prfnmplc.str.startswith('KSPO DOME')].set_index('d')
TK = DOME.totnmrs[(DOME.prfdtcnt > 0) & (DOME.totnmrs > 0)]; NPRF = DOME.prfdtcnt
M = pd.read_csv('../analysis/kopis_meta_2024_2025.csv', dtype=str)
M = M[M.fcltynm.fillna('').str.contains('KSPO|체조')].copy()
M['a'] = pd.to_datetime(M.prfpdfrom, format='%Y.%m.%d', errors='coerce'); M['b'] = pd.to_datetime(M.prfpdto, format='%Y.%m.%d', errors='coerce')
WD = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}
HOL = {'2024-01-01', '2024-02-09', '2024-02-10', '2024-02-11', '2024-02-12', '2024-03-01', '2024-04-10', '2024-05-06', '2024-05-15', '2024-06-06', '2024-08-15', '2024-09-16', '2024-09-17', '2024-09-18', '2024-10-01', '2024-10-03', '2024-10-09', '2024-12-25'}
try:
    h = pd.read_csv('holidays.csv', dtype=str, encoding='utf-8-sig'); HOL |= {pd.to_datetime(x).strftime('%Y-%m-%d') for x in h[h.is_holiday == 'Y'].date}
except Exception: pass
def times_for(g, d):
    """'금요일(19:00), 토요일 ~ 일요일(17:00)', 'HOL(17:00)' 같은 글에서 그날 시각들"""
    if not isinstance(g, str): return []
    w = pd.Timestamp(d).weekday(); hol = d in HOL; out = []
    for m in re.finditer(r'(HOL|[월화수목금토일])요?일?\s*(?:~\s*([월화수목금토일])요?일?)?\s*\(([^)]*)\)', g):
        a, b, t = m.group(1), m.group(2), m.group(3)
        ok = (a == 'HOL' and hol) or (a != 'HOL' and ((WD[a] <= w <= WD[b]) if b else w == WD[a]))
        if ok: out += re.findall(r'(\d{1,2}):(\d{2})', t)
    return sorted(int(x) + int(y) / 60 for x, y in out)
P3 = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); S25 = P3['show']
SHOWS = {}
for d in TK.index:
    if d not in TOT.index: continue
    ts = pd.Timestamp(d); cand = M[(M.a <= ts) & (M.b >= ts)]
    r = cand.iloc[0] if len(cand) else None
    st = None
    if d in S25 and 'big' in S25[d]: st = min(int(s['t'][:2]) + int(s['t'][3:5]) / 60 for s in S25[d]['big'])
    if st is None and r is not None:
        t = times_for(r.dtguidance, d); st = t[0] if t else None
    SHOWS[d] = dict(name=(r.prfnm if r is not None else (S25.get(d, {}).get('big', [{}])[0].get('name', ''))), mt=(r.mt20id if r is not None else None),
                    start=st, start_src='시각 있음' if st is not None else '없음', price=(r.pcseguidance if r is not None else ''), visit=(r.visit if r is not None else ''),
                    runtime=(r.prfruntime if r is not None else ''), a=(r.a if r is not None else None), b=(r.b if r is not None else None))
nost = [d for d, s in SHOWS.items() if s['start'] is None]
for d in nost: SHOWS[d]['start'] = {4: 19.0, 5: 18.0, 6: 17.0}.get(pd.Timestamp(d).weekday(), 19.5 if d < '2025' else 20.0) if d not in HOL else 17.0
# ---------- 같은 날 종류의 공연 없는 날로 기준 만들기(앞뒤 28일)
def cls(d):
    w = pd.Timestamp(d).weekday()
    if d in HOL or w == 6: return '일·공휴일'
    return '토' if w == 5 else '금' if w == 4 else '월~목'
CL = {d: cls(d) for d in days}; DAWN = {v: Y[v].loc[days][[2, 3, 4]].median(axis=1) for v in VALS}
INC = {v: Y[v].loc[days].sub(DAWN[v], axis=0) for v in VALS}
SHOWDAY = set(TK.index) | {d for d in NPRF.index if NPRF[d] > 0} | {d for d in S25 if 'big' in S25[d]}
BC = {}
def basecurve(v, d):
    # 같은 날 종류의 공연 없는 날을 앞뒤 28일에서 찾고, 3일이 안 되면 56·91·182일로 넓혀요(주말은 거의 늘 공연이 있어서)
    if (v, d) in BC: return BC[(v, d)]
    t = pd.Timestamp(d); out = (None, 0)
    for span in (28, 56, 91, 182):
        c = [e for e in days if e not in SHOWDAY and CL[e] == CL[d] and abs((pd.Timestamp(e) - t).days) <= span]
        if len(c) >= 3: out = (np.median(INC[v].loc[c].values, axis=0), len(c)); break
    BC[(v, d)] = out; return out
def run_of(d):
    s = SHOWS[d]; mt = s['mt']; ds = sorted(x for x in SHOWS if SHOWS[x]['mt'] == mt and mt) if mt else [d]
    # 같은 공연이라도 3일 넘게 떨어지면 다른 묶음
    groups = []
    for x in ds:
        if groups and (pd.Timestamp(x) - pd.Timestamp(groups[-1][-1])).days <= 3: groups[-1].append(x)
        else: groups.append([x])
    g = next(g for g in groups if d in g)
    return len(ds), g.index(d) + 1, len(g)
REF = 10
OTHER = K[~K.prfnmplc.str.startswith('KSPO DOME')].groupby('d').totnmrs.sum()
def rel(d, v='총생활인구수'):
    st = int(SHOWS[d]['start']); y = Y[v].loc[d].values; return np.array([y[st + r] - y[REF] if 0 <= st + r < 24 else np.nan for r in range(-6, 6)])
SD = [d for d in SHOWS if d in days]
PROF = {c: np.nanmedian(np.vstack([rel(d) for d in SD if CL[d] == c]), axis=0) for c in set(CL[d] for d in SD)}
W = list(range(3, 10))  # 상대 −3~+3
REC = []
for d in SD:
    s = SHOWS[d]; st = int(s['start']); y = rel(d); p = PROF[CL[d]]
    k = float(np.nansum(p[W] * y[W]) / np.nansum(p[W] * p[W]))
    pk1 = y[7]
    hs = [h for h in (st, st + 1, st + 2) if h < 24]
    ex = {v: max(0.0, float(np.mean(Y[v].loc[d, hs].values)) - float(Y[v].loc[d, REF])) for v in VALS[1:]}
    t1 = ex['여'] + ex['남']; ta = sum(ex[a] for a in AGE)
    nrun, pos, glen = run_of(d)
    pr = [int(x.replace(',', '')) for x in re.findall(r'(\d{1,3}(?:,\d{3})+)\s*원', s['price'] or '')]
    REC.append(dict(d=d, 해=d[:4], 이름=s['name'][:26], 날종류=CL[d], 시작=s['start'], 판매수=TK.get(d), 다른공연장=float(OTHER.get(d, 0)), 크기배율=k, 시작1시간뒤증가=pk1,
                    일찍옴=y[3] / pk1 if pk1 > 1000 else np.nan, 남아있음=y[10] / pk1 if pk1 > 1000 else np.nan, 가장많은시각=int(np.nanargmax(y[3:11])) - 3,
                    여성=100 * ex['여'] / t1 if t1 > 1000 else np.nan, **{a: (100 * ex[a] / ta if ta > 1000 else np.nan) for a in AGE},
                    공연일수=nrun, 묶음안순서=pos, 묶음일수=glen, 최고가=max(pr) if pr else np.nan, 내한=s['visit'], 달=int(d[5:7])))
R = pd.DataFrame(REC).sort_values('d')
print('공연 날 %d일(2024 %d, 2025 %d)' % (len(R), (R.해 == '2024').sum(), (R.해 == '2025').sum()))
# 맞는지: 2025년 오륜동과 서울시 올림픽공원 영역(POI127)의 시작 1시간 뒤 증가
PO = pd.read_csv('checks/park_population_2025_hourly_poi127_full.csv'); PO['ts'] = pd.to_datetime(PO.ts); PO['d'] = PO.ts.dt.strftime('%Y-%m-%d'); PO['h'] = PO.ts.dt.hour
YP = PO.pivot_table(index='d', columns='h', values='park_pop')
x = R[R.해 == '2025'].copy(); x['공원'] = [float(YP.loc[d, min(int(SHOWS[d]['start']) + 1, 23)] - YP.loc[d, REF]) if d in YP.index else np.nan for d in x.d]; x = x.dropna(subset=['공원'])
print('확인: 2025년 %d일, 시작 1시간 뒤 증가(오전 10시 대비) 오륜동 vs 서울시 올림픽공원 영역 상관 %.2f, 오륜동 ÷ 공원 중앙값 %.2f' % (len(x), np.corrcoef(x.시작1시간뒤증가, x.공원)[0, 1], (x.시작1시간뒤증가 / x.공원).median()))
R['20~30대'] = R['20대'] + R['30대']; R['50대 이상'] = R['50대'] + R['60대 이상']
print('관객층 분포: 여성 %s, 20~30대 %s, 50대 이상 %s' % tuple(str(list(np.round(q, 0))) for q in (R.여성.quantile([.1, .25, .5, .75, .9]), R['20~30대'].quantile([.1, .25, .5, .75, .9]), R['50대 이상'].quantile([.1, .25, .5, .75, .9]))))
R['관객층'] = np.where(R.여성.isna(), '알 수 없음', np.where(R['50대 이상'] >= 40, '50대 이상 중심', np.where(R['20~30대'] >= 60, '20~30대 중심', '고르게')))
R['순서'] = R.묶음안순서.map(lambda x: '첫날' if x == 1 else '둘째 날' if x == 2 else '셋째 날 이후')
R['일수'] = R.공연일수.map(lambda x: '1~2일' if x <= 2 else '3~4일' if x <= 4 else '5일 이상')
R['시작대'] = R.시작.map(lambda x: '16시 이전' if x < 17 else '17시대' if x < 18 else '18시대' if x < 19 else '19시 이후')
R['가격'] = R.최고가.map(lambda x: '가격 모름' if np.isnan(x) else '15만 원 이하' if x <= 150000 else '15~18만 원' if x <= 180000 else '18만 원 넘음')
R['계절'] = R.달.map(lambda m: '겨울' if m in (12, 1, 2) else '봄' if m <= 5 else '여름' if m <= 8 else '가을')
R['판매수대'] = R.판매수.map(lambda x: '8천 매 미만' if x < 8000 else '8천~1만1천' if x <= 11000 else '1만1천 매 넘음')
R['다른공연장대'] = R.다른공연장.map(lambda x: '없음·2천 매 미만' if x < 2000 else '2천~5천' if x <= 5000 else '5천 매 넘음')
R.to_csv('checks/patterns_2024_2025.csv', index=False, encoding='utf-8-sig')
def table(col, order):
    g = R.groupby(col)
    print('\n[%s] 일수(2024/2025) | 크기 배율 2024 → 2025 | 일찍 옴 | 남아 있음 | 가장 많은 시각' % col)
    for k in order:
        if k not in g.groups: continue
        x = g.get_group(k); a = x[x.해 == '2024']; b = x[x.해 == '2025']
        print('  %-14s %3d(%2d/%2d) | %4.2f → %4.2f | %4.2f | %4.2f | %+4.1f시간' % (k, len(x), len(a), len(b), a.크기배율.median(), b.크기배율.median(), x.일찍옴.median(), x.남아있음.median(), x.가장많은시각.median()))
print('\n== 2024·2025년 KSPO DOME 공연 날, 오륜동 기준. 크기 배율 1.00 = 같은 날 종류 공연 날의 보통 크기. 값은 중앙값')
table('관객층', ['20~30대 중심', '고르게', '50대 이상 중심', '알 수 없음'])
table('날종류', ['월~목', '금', '토', '일·공휴일'])
table('순서', ['첫날', '둘째 날', '셋째 날 이후'])
table('일수', ['1~2일', '3~4일', '5일 이상'])
table('시작대', ['16시 이전', '17시대', '18시대', '19시 이후'])
table('가격', ['15만 원 이하', '15~18만 원', '18만 원 넘음'])
table('계절', ['겨울', '봄', '여름', '가을'])
table('판매수대', ['8천 매 미만', '8천~1만1천', '1만1천 매 넘음'])
table('다른공연장대', ['없음·2천 매 미만', '2천~5천', '5천 매 넘음'])
print('\n관객층 예: ' + ' / '.join('%s: %s' % (k, ', '.join(list(dict.fromkeys(R[R.관객층 == k].이름.str[:12]))[:14])) for k in ('20~30대 중심', '고르게', '50대 이상 중심')))
# ---------- 모양 지표가 두 해 모두 같은 쪽인지, 그리고 2024로 배워 2025 첫날에 써 보기
for col in ('관객층', '시작대'):
    print('\n' + col, R.groupby([col, '해'])[['일찍옴', '남아있음', '가장많은시각']].median().round(2).unstack('해').to_string())
DW = Y['총생활인구수'].loc[days][[2, 3, 4]].median(axis=1)
def inc(d): return Y['총생활인구수'].loc[d].values - DW[d]
tr = R[R.해 == '2024']; te = R[(R.해 == '2025') & (R.묶음안순서 == 1)]
def prof(c):
    ds = [d for d in tr.d if CL[d] == c] or list(tr.d)
    al = np.nanmedian(np.vstack([[inc(d)[int(SHOWS[d]['start']) + r] if 0 <= int(SHOWS[d]['start']) + r < 24 else np.nan for r in range(-10, 7)] for d in ds]), axis=0)
    return al, np.median(np.vstack([inc(d) for d in ds]), axis=0)
PF = {c: prof(c) for c in set(CL[d] for d in R.d)}
def pred(d, k=1.0):
    al, ck = PF[CL[d]]; st = int(SHOWS[d]['start']); p = ck.copy()
    for r in range(-10, 7):
        h = st + r
        if 0 <= h < 24 and not np.isnan(al[r + 10]): p[h] = al[r + 10] * (k if -3 <= r <= 3 else 1)
    return p
def X(df, o):
    cs = [np.ones(len(df)), df.다른공연장.values / 5000, (df.시작 < 17).astype(float).values, ((df.시작 >= 17) & (df.시작 < 18)).astype(float).values]
    if o: cs.append(df.판매수.values / 10000)
    return np.column_stack(cs)
def acc(kmap):
    e = a = 0
    for d in te.d:
        y = Y['총생활인구수'].loc[d].values; p = DW[d] + pred(d, kmap.get(d, 1.0)); e += np.abs(p[7:24] - y[7:24]).sum(); a += y[7:24].sum()
    return 100 * (1 - e / a)
print('\n2024로 배우고 2025년 첫날 %d일 채점(오륜동, 07~23시. 주민이 섞여 있어 공원 영역보다 정확도가 높게 나와요)' % len(te))
print('  같은 날 종류 공연 날 모양 그대로: %.1f%%' % acc({}))
for lab, o in (('미리 아는 것(다른 공연장 판매수, 시작 시각)', False), ('+ 그날 판매수(공연 뒤에야 앎)', True)):
    b = np.linalg.lstsq(X(tr, o), tr.크기배율.values, rcond=None)[0]; km = dict(zip(te.d, np.clip(X(te, o) @ b, 0.4, 2.5)))
    print('  %s: %.1f%% (배운 식 %s)' % (lab, acc(km), np.round(b, 2).tolist()))
