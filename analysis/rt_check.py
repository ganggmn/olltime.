"""실시간 기록(2026년 11월 22~25일, 5분마다 저장한 서울시 실시간 도시데이터 '올림픽공원')을 2025년 같은 날짜 유형과 견줘요.
- 사람 수: 실시간 범위(최소~최대)의 가운데 vs 2025년 같은 유형·같은 시각의 '올림픽공원' 영역 생활인구 중앙값
- 성별·연령: 실시간 비율 vs 2025년 같은 유형·같은 시각 공원 칸(past3.py의 공원 안+DOME+올림픽공원역 칸) 구성
사용: data 폴더에서 python3 ../analysis/rt_check.py (~/past3.pkl, citydata/raw_*.jsonl.gz, livingpop_zone, checks/park_population_2025_hourly_poi127.csv)
11/22(일)은 KSPO DOME 로이킴 공연(오후 5시), 11/23~25(월~수)는 큰 공연 없는 평일이에요."""
import gzip, json, glob, os, pickle, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
rows = []
for f in sorted(glob.glob('citydata/raw_202611*.jsonl.gz')):
    for line in gzip.open(f, 'rt', encoding='utf-8'):
        try:
            r = json.loads(line); p = r['response']['CITYDATA']['LIVE_PPLTN_STTS'][0]
        except Exception: continue
        g = lambda k: float(p.get(k) or 'nan')
        rows.append(dict(ts=pd.Timestamp(p.get('PPLTN_TIME') or r['collected_at']), lo=g('AREA_PPLTN_MIN'), hi=g('AREA_PPLTN_MAX'), fem=g('FEMALE_PPLTN_RATE'),
                         **{'a%d' % a: g('PPLTN_RATE_%d' % a) for a in range(0, 80, 10)}, res=g('RESNT_PPLTN_RATE')))
T = pd.DataFrame(rows).drop_duplicates('ts').sort_values('ts'); T['mid'] = (T.lo + T.hi) / 2; T['d'] = T.ts.dt.strftime('%Y-%m-%d'); T['h'] = T.ts.dt.hour
T['a60'] = T.a60 + T.a70
H = T.groupby(['d', 'h'])[['mid', 'lo', 'hi', 'fem', 'a0', 'a10', 'a20', 'a30', 'a40', 'a50', 'a60', 'res']].mean()
print('실시간: %s ~ %s, %d개(5분마다)' % (T.ts.min(), T.ts.max(), len(T)))
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); G, show = P['G'], P['show']
PO = pd.read_csv('checks/park_population_2025_hourly_poi127.csv'); PO['ts'] = pd.to_datetime(PO.ts); PO['d'] = PO.ts.dt.strftime('%Y-%m-%d'); PO['h'] = PO.ts.dt.hour
PO = PO.set_index(['d', 'h']).park_pop
ZC = json.load(open('checks/zone_cells_2025.json', encoding='utf-8')); park = {c for c, v in ZC.items() if v['z'] in ('공원 안', 'DOME') or (v['z'] == '통로' and v['q'] == '올림픽공원')}
M = ['M%02d' % i for i in range(14)]; F = ['F%02d' % i for i in range(14)]; cols = ['date', 'hour', 'dong', 'cell', 'total'] + M + F
fr = []
for f in sorted(glob.glob('livingpop_zone/2025??.csv')):
    d = pd.read_csv(f, header=None, names=cols, dtype=str); d['cell'] = d.cell.str.strip().str[-8:]; fr.append(d[d.cell.isin(park)])
D = pd.concat(fr)
for c in ['total'] + M + F: D[c] = pd.to_numeric(D[c].str.strip(), errors='coerce').fillna(0)
D['d'] = D.date.str[:4] + '-' + D.date.str[4:6] + '-' + D.date.str[6:8]; D['h'] = D.hour.str.strip().astype(int)
Z = D.groupby(['d', 'h'])[['total'] + M + F].sum()
AG = {'a0': [0], 'a10': [1, 2], 'a20': [3, 4], 'a30': [5, 6], 'a40': [7, 8], 'a50': [9, 10], 'a60': [11, 12, 13]}
def comp(ds, h):
    idx = [(d, h) for d in ds if (d, h) in Z.index]
    if not idx: return None
    v = Z.loc[idx].median(); s = v[M].sum() + v[F].sum(); o = {'fem': 100 * v[F].sum() / s}; o.update({k: 100 * sum(v[M[i]] + v[F[i]] for i in ix) / s for k, ix in AG.items()}); return o
# 계절 차이를 빼려고 2025년 10~12월 날만 씀
sun17 = [d for d, g in G.items() if g in ('일·큰 공연', '토·큰 공연') and d[5:7] in ('10', '11', '12') and 'big' in show.get(d, {}) and min(int(s['t'][:2]) for s in show[d]['big']) == 17]
wk = [d for d, g in G.items() if g == '월~목·없음' and d[5:7] in ('10', '11', '12')]
CASES = [('2026-11-22', '일요일 KSPO DOME 오후 5시 공연(2025년 10~12월 주말 KSPO DOME 오후 5시 공연과)', sun17), ('2026-11-23', '월요일 큰 공연 없음', wk), ('2026-11-24', '화요일 큰 공연 없음', wk), ('2026-11-25', '수요일 큰 공연 없음', wk)]
OUT = {}
for day, lab, ref in CASES:
    print('\n== %s %s (2025년 같은 유형 %d일과 견줌)' % (day, lab, len(ref)))
    print(' 시 | 실시간 사람(범위 가운데)  2025 중앙값(25~75%%)  | 여성 실시간/2025 | 20대 실시간/2025 | 30대 | 40대 | 50대 | 60+ 실시간/2025')
    OUT[day] = []
    for h in range(0, 24):
        if (day, h) not in H.index: continue
        r = H.loc[(day, h)]; v = np.array([PO.get((d, h), np.nan) for d in ref]); v = v[~np.isnan(v)]
        c = comp(ref, h)
        if c is None or not len(v): continue
        q1, q2, q3 = np.percentile(v, [25, 50, 75]); inb = q1 <= r.mid <= q3
        OUT[day].append(dict(h=h, rt=round(r.mid), ref=round(q2), q1=round(q1), q3=round(q3), fem=[round(r.fem, 1), round(c['fem'], 1)], **{k: [round(r[k], 1), round(c[k], 1)] for k in ('a20', 'a30', 'a40', 'a50', 'a60')}))
        if h % 2 == 0 or h in (17, 19, 21):
            print(' %2d | %7.0f  %7.0f (%5.0f~%5.0f)%s | %4.1f / %4.1f | %4.1f / %4.1f | %4.1f / %4.1f | %4.1f / %4.1f | %4.1f / %4.1f | %4.1f / %4.1f' % (
                h, r.mid, q2, q1, q3, ' ' if inb else '*', r.fem, c['fem'], r.a20, c['a20'], r.a30, c['a30'], r.a40, c['a40'], r.a50, c['a50'], r.a60, c['a60']))
    X = pd.DataFrame(OUT[day]); X = X[X.h.between(7, 23)]
    fe = np.array([f[0] - f[1] for f in X.fem]); a6 = np.array([f[0] - f[1] for f in X.a60]); a2 = np.array([f[0] - f[1] for f in X.a20])
    rr = X.rt / X.ref
    print(' 7~23시: 실시간 ÷ 2025 중앙값 = %.2f (시간별 25~75%%: %.2f~%.2f), 시간별 모양 상관 %+.2f' % (rr.median(), rr.quantile(.25), rr.quantile(.75), np.corrcoef(X.rt, X.ref)[0, 1]))
    print(' 7~23시: 사람 수 2025 중앙값 대비 %+.0f%%(시간별 중앙값), 25~75%% 안 %d/%d시간 | 여성 비율 차 평균 %+.1f%%p, 20대 %+.1f%%p, 60+ %+.1f%%p, 시간별 여성 비율 상관 %+.2f' % (
        100 * np.median(X.rt / X.ref - 1), sum((X.q1 <= X.rt) & (X.rt <= X.q3)), len(X), fe.mean(), a2.mean(), a6.mean(), np.corrcoef([f[0] for f in X.fem], [f[1] for f in X.fem])[0, 1]))
json.dump(OUT, open('checks/rt_check_202611.json', 'w'), ensure_ascii=False, separators=(',', ':'))
