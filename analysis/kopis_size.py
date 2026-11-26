"""KOPIS 티켓 판매수로 KSPO DOME 공연 날 인원의 '크기'를 맞출 수 있는지 2025년 자료로 봐요.
사용: data 폴더에서 python3 ../analysis/kopis_size.py ../analysis/kopis_daily_2025.csv
필요: ~/past3.pkl(날짜 종류·공연), checks/park_population_2025_hourly_poi127_full.csv(서울시 '올림픽공원' 영역, 시간별),
      checks/bigshow_counts_2025.csv(공연 날 시작+1시간 증가·지하철·연계 관객)
출처: 공연예술통합전산망(KOPIS) 공연시설별 통계, 서울특별시 생활인구.
1) 판매수와 실제 늘어난 사람 수가 얼마나 같이 움직이는지(상관, 표 한 장당 늘어난 사람)
2) 모델 비교(지난 달들만으로 배움, 3~12월, 07~23시 정확도)
   M0 사이트 지금 / M0+같은 공연 전날 / A 평균 크기(판매수 없이, 같은 요일 KSPO DOME 공연 없는 날 + 시작 시각 기준 공연 몫) / T 판매수 크기(그날 판매수 × 표 한 장당 모양)
   T는 공연이 끝난 뒤에야 알 수 있는 값이라 '판매수를 미리 알면 얼마나 좋아지나'의 위쪽 끝이에요.
3) 판매수를 대충만 알 때(±10·20·30% 틀림) 얼마나 남는지"""
import os, sys, pickle, numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); G, SHOW = P['G'], P['show']
PO = pd.read_csv('checks/park_population_2025_hourly_poi127_full.csv'); PO['ts'] = pd.to_datetime(PO.ts); PO['d'] = PO.ts.dt.strftime('%Y-%m-%d'); PO['h'] = PO.ts.dt.hour
Y = PO.pivot_table(index='d', columns='h', values='park_pop'); days = list(Y.index); DAWN = Y[[2, 3, 4]].median(axis=1); INC = Y.sub(DAWN, axis=0)
K = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else '../analysis/kopis_daily_2025.csv', dtype={'from': str}); K['d'] = pd.to_datetime(K['from']).dt.strftime('%Y-%m-%d')
DOME = K[K.prfnmplc.str.startswith('KSPO DOME')].set_index('d'); TK = DOME.totnmrs[DOME.totnmrs > 0]; NPRF = DOME.prfdtcnt
OTHER = K[K.prfnmplc.str.contains('올림픽홀|핸드볼')].groupby('d').totnmrs.sum()
wd = {d: pd.Timestamp(d).weekday() for d in days}
def base(d):
    g = G.get(d, '')
    if g == '명절': return '명절'
    if g.startswith('평일 공휴일'): return '평일공휴일'
    return '월~목' if wd[d] < 4 else '금' if wd[d] == 4 else '토' if wd[d] == 5 else '일'
BASE = {d: base(d) for d in days}
ST = {d: min(int(s['t'][:2]) + int(s['t'][3:5]) / 60 for s in SHOW[d]['big']) for d in days if 'big' in SHOW.get(d, {})}
NSH = {d: len(SHOW[d]['big']) for d in ST}
ANY = {d for d in days if SHOW.get(d)}
SEQ = {d: SHOW[d]['big'][0].get('seq') for d in ST}
def prev_run(d):
    c = [x for x in days if x < d and SEQ.get(x) == SEQ.get(d) and SEQ.get(d) is not None and (pd.Timestamp(d) - pd.Timestamp(x)).days <= 3]
    return c[-1] if c else None
side = lambda d: 'we' if BASE[d] in ('토', '일', '평일공휴일', '명절') else 'wd'
# ---------- 1) 판매수 ↔ 늘어난 사람
B = pd.read_csv('checks/bigshow_counts_2025.csv', encoding='utf-8-sig'); B = B[B.d.isin(TK.index)].copy(); B['판매수'] = B.d.map(TK)
B['한 번'] = B.d.map(lambda d: NSH.get(d, 1) == 1)
NOSHOW = {}
for d in days:
    if d not in ST: NOSHOW.setdefault(BASE[d], []).append(INC.loc[d].values)
NOSHOW = {k: np.median(v, axis=0) for k, v in NOSHOW.items()}
def ex_win(d):
    b = NOSHOW.get(BASE[d], NOSHOW['일' if side(d) == 'we' else '월~목']); w = [h for h in range(int(ST[d]) - 3, int(ST[d]) + 4) if 0 <= h < 24]
    return float(np.mean(INC.loc[d, w].values - b[w]))
B['공연앞뒤3시간_증가'] = B.d.map(lambda d: ex_win(d) if d in ST and d in INC.index else np.nan)
B['평일'] = B.d.map(lambda d: side(d) == 'wd')
print('== 1) KSPO DOME 공연 날 판매수와 늘어난 사람(2025년, 판매수 있는 날 %d일, 하루 한 번 공연 %d일)' % (len(B), B['한 번'].sum()))
print('   공연앞뒤3시간_증가 = 시작 3시간 전~3시간 뒤 서울시 올림픽공원 영역의 새벽 대비 증가 − 같은 요일 KSPO DOME 공연 없는 날의 같은 값(평균)')
for lab, sub in (('평일', B['평일']), ('주말', ~B['평일'])):
    x = B[B['한 번'] & sub]; r = np.corrcoef(x['판매수'], x['공연앞뒤3시간_증가'])[0, 1]; q = x['공연앞뒤3시간_증가'] / x['판매수']
    print('   %s %3d일: 공연앞뒤3시간_증가와 상관 %.2f | 표 한 장당 %.2f명 (중간 50%% %.2f~%.2f)' % (lab, len(x), r, q.median(), q.quantile(.25), q.quantile(.75)))
for c in ['공연앞뒤3시간_증가', 'DOME칸_증가', '지하철_3시간_하차증가', '관객_연계', '서울시_증가']:
    x = B[B['한 번'] & B[c].notna()]
    r = np.corrcoef(x['판매수'], x[c])[0, 1]; q = (x[c] / x['판매수'])
    print('   %-16s 상관 %.2f | 표 한 장당 %.2f명 (중간 50%% %.2f~%.2f, %d일)' % (c, r, q.median(), q.quantile(.25), q.quantile(.75), len(x)))
x = B[B['한 번']]; print('   (참고) 판매수 중앙값 %d매, 범위 %d~%d' % (x['판매수'].median(), x['판매수'].min(), x['판매수'].max()))
# ---------- 2) 모델
H = list(range(7, 24)); RELS = range(-8, 7)
def m0_cls(d):
    b = wd[d]; big = d in ST
    if b < 4: return 'wk'
    k = 'fri' if b == 4 else 'sat' if b == 5 else 'hol'
    if G.get(d, '').startswith('평일 공휴일') and not big: k = 'wk'
    return k + ('_show' if big else '')
def fit(train):
    C = {}
    for d in train: C.setdefault(m0_cls(d), []).append(INC.loc[d].values)
    M0 = {k: np.median(v, axis=0) for k, v in C.items()}
    N = {}
    for d in train:
        if d not in ST: N.setdefault(BASE[d], []).append(INC.loc[d].values)
    NB = {k: np.median(v, axis=0) for k, v in N.items() if len(v) >= 3}
    ALLB = {}
    for d in train: ALLB.setdefault(BASE[d], []).append(INC.loc[d].values)
    def nb(d):
        for k in (BASE[d], '일' if side(d) == 'we' else '월~목', '토' if side(d) == 'we' else '금'):
            if k in NB: return NB[k]
        return np.median(ALLB.get(BASE[d], ALLB['월~목']), axis=0)
    per, avg, tks = {}, {}, {}
    for d in train:
        if d not in ST or NSH[d] != 1: continue
        st = int(ST[d]); ex = INC.loc[d].values - nb(d)
        for r in RELS:
            if 0 <= st + r < 24:
                avg.setdefault((side(d), r), []).append(ex[st + r])
                if d in TK: per.setdefault((side(d), r), []).append(ex[st + r] / TK[d])
        if d in TK: tks.setdefault(side(d), []).append(TK[d])
    PER = {k: np.median(v) for k, v in per.items() if len(v) >= 3}; AVG = {k: np.median(v) for k, v in avg.items() if len(v) >= 3}
    TKM = {k: np.median(v) for k, v in tks.items()}
    return M0, nb, PER, AVG, TKM
def shaped(nb, tab, d, scale=1.0):
    p = nb(d).copy(); st = int(ST[d]); s = side(d)
    for r in RELS:
        if 0 <= st + r < 24 and (s, r) in tab: p[st + r] += scale * tab[(s, r)]
    return p
def carry(pred, alpha=0.8):
    out = {d: v.copy() for d, v in pred.items()}
    for d in pred:
        p = prev_run(d)
        if p is None or p not in pred: continue
        r = INC.loc[p].values - pred[p]; sp, sd = int(ST[p]), int(ST[d])
        for rel in range(-6, 6):
            if 0 <= sp + rel < 24 and 0 <= sd + rel < 24: out[d][sd + rel] += alpha * r[sp + rel]
    return out
PR = {k: {} for k in ('M0 사이트 지금', 'A 평균 크기', 'T 판매수 크기', 'T 판매수 ±10%', 'T 판매수 ±20%', 'T 판매수 ±30%')}
rng = np.random.default_rng(0); NOISE = {}
for m in range(3, 13):
    test = [d for d in days if int(d[5:7]) == m and d in ST]; train = [d for d in days if int(d[5:7]) < m]
    M0, nb, PER, AVG, TKM = fit(train)
    for d in test:
        PR['M0 사이트 지금'][d] = M0.get(m0_cls(d), M0['wk'])
        PR['A 평균 크기'][d] = shaped(nb, AVG, d)
        if d in TK:
            PR['T 판매수 크기'][d] = shaped(nb, PER, d, TK[d])
            for e in (10, 20, 30):
                z = NOISE.setdefault((d, e), rng.choice([-1, 1]) * e / 100); PR['T 판매수 ±%d%%' % e][d] = shaped(nb, PER, d, TK[d] * (1 + z))
        else:
            for k in ('T 판매수 크기', 'T 판매수 ±10%', 'T 판매수 ±20%', 'T 판매수 ±30%'): PR[k][d] = PR['A 평균 크기'][d]
PR['M0+같은 공연 전날'] = carry(PR['M0 사이트 지금']); PR['T+같은 공연 전날'] = carry(PR['T 판매수 크기'])
def acc(pr, ds, hours=H):
    e = np.concatenate([np.abs(DAWN[d] + pr[d][hours] - Y.loc[d, hours].values) for d in ds]); a = np.concatenate([Y.loc[d, hours].values for d in ds])
    return 100 * (1 - e.sum() / a.sum()), e.mean()
def win(d): return [h for h in range(int(ST[d]) - 3, int(ST[d]) + 4) if 7 <= h <= 23]
ALL = sorted(PR['M0 사이트 지금']); FIRST = [d for d in ALL if prev_run(d) is None]; LATER = [d for d in ALL if prev_run(d) is not None]
print('\n== 2) KSPO DOME 공연 날 정확도(지난 달들만으로 배움, 3~12월, 07~23시). 칸 = 정확도%(시간당 평균 오차 명)')
print('%-20s | %-16s | %-16s | %-16s | %s' % ('모델', '첫날 %d일' % len(FIRST), '둘째 날 이후 %d일' % len(LATER), '전체 %d일' % len(ALL), '공연 앞뒤 3시간만(전체)'))
for k, pr in PR.items():
    cells = ['%5.1f%%(%5.0f)' % acc(pr, g) for g in (FIRST, LATER, ALL)]
    e = np.concatenate([np.abs(DAWN[d] + pr[d][win(d)] - Y.loc[d, win(d)].values) for d in ALL]); a = np.concatenate([Y.loc[d, win(d)].values for d in ALL])
    print('%-20s | %-16s | %-16s | %-16s | %5.1f%%' % (k, *cells, 100 * (1 - e.sum() / a.sum())))
print('   판매수 없는 날 %d일은 T도 A(평균 크기)로 채움' % sum(1 for d in ALL if d not in TK))
# 크기 배율이 판매수로 얼마나 설명되나: 필요한 배율 k(공연 앞뒤 증가를 맞추는 값) vs 판매수/평균
ks = []
for d in ALL:
    w = win(d); p = PR['A 평균 크기'][d][w]; y = INC.loc[d, w].values
    if d in TK and np.sum(p * p) > 0: ks.append((np.sum(p * y) / np.sum(p * p), TK[d]))
ks = np.array(ks); print('   평균 크기 모양에 필요한 배율 vs 판매수: 상관 %.2f (%d일)' % (np.corrcoef(ks[:, 0], ks[:, 1])[0, 1], len(ks)))
