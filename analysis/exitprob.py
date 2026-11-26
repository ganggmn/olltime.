"""퇴장 '확률 예측표': 퇴장 시작이 어느 10분에 올지 확률로 두고, 그 뒤 주차장에서 빠지는 차(10분당 순유출 = 나간 차 − 들어온 차)를 미리 계산해요.
  ① 퇴장 시작 확률: 2025년 KSPO DOME 저녁(입출차로 잡은 실제 출차 시작, end_detect_2025.json)에서
     P1 같은 시작 시각대 공연들의 '시작 → 출차 시작' 분포 / P2 '적힌 공연 시간 + 늦어지는 몫' 분포 / P0 전부 모은 분포. 10분 커널로 부드럽게.
  ② 출차 모양: 출차 시작 뒤 5분마다 늘어난 순유출의 몫(다른 투어들의 중앙값) × 늘어난 대수(다른 투어 중앙값, 판매수 안 씀)
  ③ 바닥값: 같은 요일 무리(평일/주말·공휴일)의 공연 없는 날, 같은 시각 순유출 중앙값
  예상(t) = 바닥(t) + Σ_s P(s) × 대수 × 모양(t − s).  '혼잡' 확률 = Σ_s P(s) × [바닥 + 대수×모양 ≥ 기준]
과거 시험: 각 저녁을 그 투어를 뺀 나머지로만 만들어(미래·같은 투어 정보 없음) 채점. 점 예측(분포의 중앙값 하나, '시작+적힌 시간+42분' 하나)과 비교.
'아직 안 끝남' 고침: 판단 시각 T까지 주차 감지(10분 6.5% 감소)가 안 울렸으면 '출차 시작 > T − 15분'만 남기고 다시 나눔, 울렸으면 '감지 − (감지−출차 시작 분포)'로 바꿈.
사용: data 폴더에서 python3 ../analysis/exitprob.py backtest   |   python3 ../analysis/exitprob.py build 2026-11-27 19:00 130 > 표"""
import os, sys, json, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from sigtest import boot_diff
P = pickle.load(open(os.path.expanduser('~/past3.pkl'), 'rb')); SHOW = P['show']
HOL = {r[:4] + '-' + r[4:6] + '-' + r[6:] for r in pd.read_csv('holidays.csv', dtype=str).iloc[:, 0]}
wkg = lambda d: '주말·공휴일' if pd.Timestamp(d).weekday() >= 5 or d in HOL else '평일'
def to10(a): a = np.asarray(a, float); n = len(a) // 2 * 2; return a[:n].reshape(-1, 2).sum(1)
hm = lambda t: int(t[:2]) * 60 + int(t[3:5])
E = json.load(open('checks/end_detect_2025.json')); EV = E['1~6월(정할 때 쓴 저녁)']['evenings'] + E['7·10·11월(채점)']['evenings']
df = pd.read_csv('inout_2025_full.csv', usecols=['entry_gate', 'entry_time', 'exit_time'], encoding='utf-8-sig'); df = df[~df.entry_gate.str.contains('CMB')]
en = pd.to_datetime(df.entry_time, errors='coerce').dropna(); ex = pd.to_datetime(df.exit_time, errors='coerce').dropna()
B5 = lambda s: s.dt.floor('5min').value_counts()
NET = (B5(ex).sub(B5(en), fill_value=0)).sort_index()  # 5분 순유출
import calendar
bad = lambda d: d[5:7] in ('08', '09') or (d[5:7] == '11' and int(d[8:]) > 6) or (d[5:7] == '12' and int(d[8:]) > 7) or int(d[8:]) == calendar.monthrange(int(d[:4]), int(d[5:7]))[1]
alld = sorted({str(t.date()) for t in NET.index if str(t.date()).startswith('2025')})
dome = lambda d: [b for b in SHOW.get(d, {}).get('big', []) if 'KSPO' in b['venue']]
noshow = [d for d in alld if not dome(d) and not bad(d) and not SHOW.get(d)]
def series(d):  # 그날 0시부터 5분 순유출 400칸
    idx = pd.date_range(d, periods=400, freq='5min'); return NET.reindex(idx).fillna(0).values  # 다음 날 새벽까지
BASED = {g: np.vstack([series(d) for d in noshow if wkg(d) == g]) for g in ('평일', '주말·공휴일')}  # 공연 없는 날 하나하나
BASE = {g: np.median(v, axis=0) for g, v in BASED.items()}
G5 = np.arange(0, 360, 5)  # 시작 뒤 분(72칸)
NS = len(G5) // 2  # 10분 칸 36개
rows = []
for e in EV:
    d = e['d']; b = dome(d)
    if len(b) != 1 or bad(d): continue
    st = hm(b[0]['t']); run = b[0].get('run'); run = None if run is None or run != run else float(run); s = series(d); bs = BASE[wkg(d)]
    on = float(e["onset"]); k0 = int((st + on) // 5)
    exc = np.clip(s[k0:k0 + 24] - bs[k0:k0 + 24], 0, None)
    if len(exc) < 24 or exc.sum() <= 0: continue
    rows.append(dict(d=d, seq=b[0]['seq'], st=st, run=run, onset=on, fire=e.get('fire'), g=wkg(d), shape=exc / exc.sum(), size=float(exc.sum())))
EVN = pd.DataFrame(rows)
# 기준(시험용): 혼잡 = 공연 없는 저녁 18~24시 10분 순유출의 상위 5%(평소엔 거의 안 넘음), 매우 혼잡 = 2025 출차 시작 뒤 2시간 10분 순유출의 상위 20%
_post = np.concatenate([to10(series(r.d)[int(r.st + r.onset) // 5: int(r.st + r.onset) // 5 + 24]) for r in EVN.itertuples()])
_norm = np.concatenate([to10(v[:, 18 * 12: 24 * 12]).ravel() if v.ndim == 1 else np.concatenate([to10(r[18 * 12: 24 * 12]) for r in v]) for v in BASED.values()])
THR = {'혼잡': float(np.round(np.percentile(_norm, 95), -1)), '매우 혼잡': float(np.round(np.percentile(_post, 80), -1))}
def kde(vals, grid=G5, bw=10):
    v = np.asarray(vals, float); w = np.exp(-0.5 * ((grid[:, None] - v[None]) / bw) ** 2).sum(1); return w / w.sum()
def day_diffs(train):
    out = []
    for _, g in train.sort_values('d').groupby('seq'):
        on = g.onset.values; ds = pd.to_datetime(g.d).values
        for i in range(1, len(g)):
            if (ds[i] - ds[i - 1]) / np.timedelta64(1, 'D') <= 3: out.append(on[i] - on[i - 1])
    return np.array(out)
def onset_dist(train, st, run, how, prev=None):
    run = None if run is None or run != run else run
    if how == 'P3' and prev is not None: return kde(prev + day_diffs(train))
    if how == 'P1':
        same = train[(train.st // 60) == st // 60]; v = (same if len(same) >= 5 else train).onset.values
    elif how == 'P2' and run:
        tr = train[train.run.notna()]; v = (tr.onset - tr.run).values + run
    else: v = train.onset.values
    return kde(v)
def forecast(train, st, run, g, how, pdist=None, prev=None):
    """반환: 퇴장 시작 확률(10분 칸), 기대 순유출(10분), 혼잡·매우 혼잡 확률(10분), 바닥(10분). 규모·모양은 다른 투어 저녁들 하나하나를 후보로(같은 무게)."""
    p5 = onset_dist(train, st, run, how, prev) if pdist is None else pdist; p = to10(p5); p = p / p.sum() if p.sum() > 0 else p
    base = to10(BASE[g][int(st) // 5: int(st) // 5 + 2 * NS])
    C = np.vstack([to10(sz * sh) for sz, sh in zip(train['size'], train['shape'])])  # 후보마다 출차 시작 뒤 12칸(120분)
    # 칸 m의 혼잡 확률 = Σ_i P(출차 시작 = i) × (후보 저녁 중 바닥[m] + 늘어난 차[m−i] ≥ 기준인 몫).
    # 출차 시작 전(m < i)이나 2시간이 지난 뒤(m − i ≥ 12)는 늘어난 차 0, 즉 바닥만으로 판단. (2026-11-27 고침: 처음 판은 이 두 경우를 빠뜨렸음)
    # 바닥도 하나로 두지 않고, 같은 요일 무리 공연 없는 날 하나하나를 후보로(후보 저녁과 짝지어 300쌍, 씨앗 고정)
    J = C.shape[1]; exp = base.copy(); pc = np.zeros(NS); pv = np.zeros(NS)
    BD = np.vstack([to10(r[int(st) // 5: int(st) // 5 + 2 * NS]) for r in BASED[g]])
    rng = np.random.default_rng(int(st) * 7 + len(train)); kb = rng.integers(0, len(BD), 300); kc = rng.integers(0, len(C), 300)
    Bk = BD[kb]; Ck = np.hstack([C[kc], np.zeros((300, NS))])  # j ≥ 12면 0
    for i in range(NS):
        if p[i] <= 0: continue
        for j in range(J): 
            if i + j < NS: exp[i + j] += p[i] * C[:, j].mean()
        add = np.zeros((300, NS)); L = NS - i; add[:, i:] = Ck[:, :L]
        tot = Bk + add; pc += p[i] * (tot >= THR['혼잡']).mean(0); pv += p[i] * (tot >= THR['매우 혼잡']).mean(0)
    rest = max(0.0, 1 - p.sum()); pc += rest * (Bk >= THR['혼잡']).mean(0); pv += rest * (Bk >= THR['매우 혼잡']).mean(0)
    return p, exp, pc, pv, base
def censor(p, T, fired_at=None, lagdist=None):
    q = p.copy()
    if fired_at is None: q[G5 <= T - 15] = 0
    else:
        q = np.zeros_like(p)
        for lag, w in lagdist: q += w * kde([fired_at - lag])
    return q / q.sum() if q.sum() > 0 else p
W0, W1 = 9, 33  # 채점 칸: 시작 뒤 90~330분(10분 칸 9~32)
def score_rows(r, p, exp, pc, pv):
    act = to10(series(r.d)[int(r.st) // 5: int(r.st) // 5 + 2 * NS]); o = int(r.onset // 10)
    cs = np.cumsum(p); lo, hi = np.searchsorted(cs, 0.1), np.searchsorted(cs, 0.9)
    k = np.arange(W0, W1)
    return dict(logp=float(np.log(max(p[o], 1e-3))), cover80=bool(lo <= o <= hi), width80=int(10 * (hi - lo + 1)),
                mae=float(np.mean(np.abs(exp[k] - act[k]))), sumabs=float(np.sum(np.abs(exp[k] - act[k]))), sumy=float(np.sum(np.abs(act[k]))),
                brier_c=float(np.mean((pc[k] - (act[k] >= THR['혼잡'])) ** 2)), brier_v=float(np.mean((pv[k] - (act[k] >= THR['매우 혼잡'])) ** 2))), act[k], exp[k], pc[k], pv[k]
if __name__ == '__main__' and sys.argv[1] == 'backtest':
    print('2025 저녁 %d개, 투어 %d개, 적힌 공연 시간 있음 %d개 | 기준: 혼잡 ≥ %.0f대/10분, 매우 혼잡 ≥ %.0f대/10분(혼잡 = 공연 없는 저녁 18~24시 상위 5%%, 매우 혼잡 = 출차 시작 뒤 2시간의 상위 20%%)' % (len(EVN), EVN.seq.nunique(), EVN.run.notna().sum(), THR['혼잡'], THR['매우 혼잡']))
    res = []; SL = []
    for r in EVN.itertuples():
        train = EVN[EVN.seq != r.seq]
        same = train[(train.st // 60) == r.st // 60]; med = float(np.median((same if len(same) >= 5 else train).onset))
        cands = {'P0 전부': ('P0', None), 'P1 시작 시각별': ('P1', None), 'P2 적힌 시간+지연': ('P2', None),
                 '점: 시작 시각별 중앙값': ('P0', kde([med], bw=0.1)), '점: 예정+42분': ('P0', kde([(r.run if r.run == r.run else 150) + 42], bw=0.1)),
                 '바닥만(공연 몫 없음)': ('P0', np.zeros(len(G5))), '정답 시작을 안다면': ('P0', kde([r.onset], bw=0.1))}
        mine = EVN[(EVN.seq == r.seq) & (EVN.d < r.d)].sort_values('d')
        prev = float(mine.onset.iloc[-1]) if len(mine) and (pd.Timestamp(r.d) - pd.Timestamp(mine.d.iloc[-1])).days <= 3 else None
        r_has_prev = prev is not None
        if r_has_prev: cands['P3 전날 같은 공연'] = ('P3', None); cands['점: 전날 출차 시작'] = ('P0', kde([prev], bw=0.1))
        else: cands.pop('P3 전날 같은 공연', None); cands.pop('점: 전날 출차 시작', None)
        for name, (how, pd_) in cands.items():
            p, exp, pc, pv, base = forecast(train, r.st, r.run, r.g, how, pdist=pd_, prev=prev)
            sc, a, e, c, v = score_rows(r, p, exp, pc, pv); res.append(dict(d=r.d, seq=r.seq, how=name, has_run=r.run == r.run, has_prev=r_has_prev, **sc))
            for kk in range(len(a)): SL.append(dict(seq=r.seq, how=name, has_run=r.run == r.run, has_prev=r_has_prev, k=kk, y=a[kk], f=e[kk], pc=c[kk], pv=v[kk]))
    R = pd.DataFrame(res); SL = pd.DataFrame(SL)
    def table(R, SL, title):
        print('\n== ' + title)
        print('  %-20s %7s %7s %6s %8s %7s %8s %8s' % ('방식', '로그점수', '80%적중', '폭', '10분MAE', '정확도', '혼잡Brier', '매우Brier'))
        full = R.d.nunique() == EVN.d.nunique()
        for name in R.how.unique():
            x = R[R.how == name]
            if full and name in ('P3 전날 같은 공연', '점: 전날 출차 시작'): continue  # 41저녁에만 있음 → 아래 표에서
            if name == '바닥만(공연 몫 없음)': print('  %-20s %7s %7s %6s %7.1f대 %6.1f%% %8.3f %8.3f' % (name, '-', '-', '-', x.mae.mean(), 100 * (1 - x.sumabs.sum() / x.sumy.sum()), x.brier_c.mean(), x.brier_v.mean())); continue
            print('  %-20s %7.2f %6.0f%% %5.0f분 %7.1f대 %6.1f%% %8.3f %8.3f' % (name, x.logp.mean(), 100 * x.cover80.mean(), x.width80.median(), x.mae.mean(), 100 * (1 - x.sumabs.sum() / x.sumy.sum()), x.brier_c.mean(), x.brier_v.mean()))
        print('  (로그점수 기준: 36칸 고르게 나누면 %.2f)' % np.log(1 / 36))
    def cmp(SL, a_, b_, col='f'):
        A, Bq = SL[SL.how == a_].reset_index(drop=True), SL[SL.how == b_].reset_index(drop=True)
        rr = boot_diff((A.f - A.y).abs(), (Bq.f - Bq.y).abs(), A.y.abs(), A.seq)
        # 혼잡 Brier 차이(투어 묶음 붓스트랩)
        bA = (A.pc - (A.y >= THR['혼잡'])) ** 2; bB = (Bq.pc - (Bq.y >= THR['혼잡'])) ** 2; g = A.seq.values; us = np.unique(g); rng = np.random.default_rng(0); dd = []
        for _ in range(2000):
            pick = rng.choice(us, len(us)); m = np.concatenate([np.where(g == u)[0] for u in pick]); dd.append(bA.values[m].mean() - bB.values[m].mean())
        lo, hi = np.percentile(dd, [2.5, 97.5])
        print('  [%s] vs [%s]: 정확도 %+.1f%%p (95%% %+.1f ~ %+.1f) | 혼잡 Brier %+.3f (95%% %+.3f ~ %+.3f, 음수가 나음)' % (a_, b_, rr['diff'], *rr['ci95'], bA.mean() - bB.mean(), lo, hi))
    table(R, SL, '과거 시험 — 전체 71저녁(그 투어를 뺀 나머지로 만든 표, 채점은 시작 뒤 90~330분 10분 칸)')
    for a_, b_ in (('P0 전부', '점: 시작 시각별 중앙값'), ('P1 시작 시각별', '점: 시작 시각별 중앙값'), ('P1 시작 시각별', 'P0 전부'), ('P0 전부', '바닥만(공연 몫 없음)')): cmp(SL, a_, b_)
    Rr, SLr = R[R.has_run], SL[SL.has_run]
    table(Rr, SLr, '적힌 공연 시간이 있는 %d저녁만' % Rr.d.nunique())
    for a_, b_ in (('P2 적힌 시간+지연', '점: 예정+42분'), ('P2 적힌 시간+지연', 'P0 전부'), ('P2 적힌 시간+지연', 'P1 시작 시각별')): cmp(SLr, a_, b_)
    Rp, SLp = R[R.has_prev], SL[SL.has_prev]
    table(Rp, SLp, '같은 공연 전날(3일 안)이 있는 %d저녁만 — 둘째 날부터' % Rp.d.nunique())
    print('  이틀 연속 출차 시작 차이(전부): 중앙값 %+.0f분, 10~90%% %+.0f ~ %+.0f분, n=%d' % (np.median(day_diffs(EVN)), *np.percentile(day_diffs(EVN), [10, 90]), len(day_diffs(EVN))))
    for a_, b_ in (('P3 전날 같은 공연', 'P0 전부'), ('P3 전날 같은 공연', '점: 전날 출차 시작'), ('P3 전날 같은 공연', '정답 시작을 안다면')): cmp(SLp, a_, b_)
    for name in ('P0 전부', 'P2 적힌 시간+지연'):
        for col, lab in (('pc', '혼잡'), ('pv', '매우 혼잡')):
            s_ = SL[SL.how == name].copy(); s_['bin'] = pd.cut(s_[col], [-0.01, 0.1, 0.3, 0.5, 0.7, 1.0])
            print('  %s "%s" 눈금: ' % (name, lab) + ' | '.join('예측 %.2f→실제 %.2f(%d칸)' % (v[col].mean(), (v.y >= THR[lab]).mean(), len(v)) for k, v in s_.groupby('bin', observed=True)))
    print('\n== "아직 안 끝남" 고침(P1, 판단 시각 T 이후 칸만)')
    U = []
    for r in EVN.itertuples():
        train = EVN[EVN.seq != r.seq]; lagd = list(zip((train.fire - train.onset).dropna().values, np.ones(train.fire.notna().sum()) / train.fire.notna().sum()))
        p5 = onset_dist(train, r.st, r.run, 'P1'); act = to10(series(r.d)[int(r.st) // 5: int(r.st) // 5 + 2 * NS])
        _, e0, _, _, _ = forecast(train, r.st, r.run, r.g, 'P1', pdist=p5)
        for T in (120, 150, 180, 210):
            fired = r.fire if (r.fire == r.fire and r.fire is not None and r.fire <= T) else None
            q = censor(p5, T, fired, lagd); _, e1, _, _, _ = forecast(train, r.st, r.run, r.g, 'P1', pdist=q)
            for kk in range(max(T // 10, W0), W1): U.append(dict(seq=r.seq, T=T, fired=fired is not None, y=act[kk], prior=e0[kk], post=e1[kk]))
    U = pd.DataFrame(U)
    for T, x in U.groupby('T'):
        rr = boot_diff((x.post - x.y).abs(), (x.prior - x.y).abs(), x.y.abs(), x.seq)
        print('  T=시작+%d분 (감지가 이미 울린 저녁 %2.0f%%): 미리 만든 표 %.1f%% → 고친 표 %.1f%% (차이 %+.1f%%p, 95%% %+.1f ~ %+.1f, 99%% %+.1f ~ %+.1f)' % (T, 100 * x.groupby('seq').fired.max().mean(), rr['old'], rr['new'], rr['diff'], *rr['ci95'], *rr['ci99']))
    R.to_csv('checks/exitprob_backtest.csv', index=False); json.dump(dict(THR=THR), open('checks/exitprob_backtest.json', 'w'), ensure_ascii=False)
if __name__ == '__main__' and sys.argv[1] == 'build':
    d, t = sys.argv[2], sys.argv[3]; run = float(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] not in ('', '0') else None; how = sys.argv[5] if len(sys.argv) > 5 else 'P2'
    prev = float(sys.argv[6]) if len(sys.argv) > 6 else None
    st = hm(t); p, exp, pc, pv, base = forecast(EVN, st, run, wkg(d), how, prev=prev)
    cs = np.cumsum(p); lo, md, hi = (int(np.searchsorted(cs, q)) for q in (0.1, 0.5, 0.9))
    clock = lambda k: '%02d:%02d' % ((st + 10 * k) // 60 % 24, (st + 10 * k) % 60)
    tab = [dict(slot='%02d:%02d' % ((st + 10 * k) // 60 % 24, (st + 10 * k) % 60), p_onset=round(float(p[k]), 3), exp_net=round(float(exp[k])), base=round(float(base[k])), p_busy=round(float(pc[k]), 3), p_vbusy=round(float(pv[k]), 3)) for k in range(NS)]
    print(json.dumps(dict(day=d, start=t, runtime=run, how=how, prev_onset_min=prev, weekday_group=wkg(d), n_train=len(EVN), thr=THR,
                          onset_80=[clock(lo), clock(hi + 1)], onset_median_slot=clock(md), size_cars_median=float(np.median(EVN['size'])), table=tab), ensure_ascii=False))
# ---------- 2026 실측(KSPO 주차 parking_sum)에 맞추는 부분 ----------
# parking_sum은 2025 입출차(CMB 뺌)보다 잡는 주차장 범위가 좁아요. 공연 없는 평일 하루 변동폭 비율로 크기를 맞춤(11/23~26 대 2025 공연 없는 평일, 아래에서 고정).
K_SCALE = 1335 / 2056
def load_live_park(path):
    d = pd.read_csv(path); d['t'] = pd.to_datetime(d.collected_at); d = d.dropna(subset=['parking_sum'])
    return d.set_index('t').parking_sum.astype(float).sort_index().resample('5min').last().interpolate()
def live_net10(park, day, st):
    t0 = pd.Timestamp(day) + pd.Timedelta(minutes=st); idx = pd.date_range(t0, periods=NS + 1, freq='10min')
    v = park.reindex(park.index.union(idx)).interpolate().reindex(idx).values; return v[:-1] - v[1:]  # 칸 [t, t+10) 동안 줄어든 대수
def table_json(d, t, run, how, prev=None):
    st = hm(t); p, exp, pc, pv, base = forecast(EVN, st, run, wkg(d), how, prev=prev)
    # 2026 크기로: 기준도 같은 비율로 줄임
    thr26 = {k: v * K_SCALE for k, v in THR.items()}
    cs = np.cumsum(p); lo, md, hi = (int(np.searchsorted(cs, q)) for q in (0.1, 0.5, 0.9))
    clock = lambda k: '%02d:%02d' % ((st + 10 * k) // 60 % 24, (st + 10 * k) % 60)
    tab = [dict(slot=clock(k), p_onset=round(float(p[k]), 4), exp_net_2026=round(float(exp[k] * K_SCALE), 1), base_2026=round(float(base[k] * K_SCALE), 1),
                p_busy=round(float(pc[k]), 4), p_vbusy=round(float(pv[k]), 4)) for k in range(NS)]
    return dict(day=d, start=t, runtime=run, how=how, prev_onset_min=prev, weekday_group=wkg(d), n_train_evenings=len(EVN), n_train_tours=int(EVN.seq.nunique()),
                k_scale=K_SCALE, thr_2025=THR, thr_2026=thr26, onset_80=[clock(lo), clock(hi + 1)], onset_median_slot=clock(md), table=tab)
if __name__ == '__main__' and sys.argv[1] == 'prereg':
    out = dict(
        what='조용필 KSPO DOME 11/27(금 19:00)·28(토 18:00)·29(일 17:00) 퇴장 확률표 — 공연 전에 고정',
        made_at=pd.Timestamp.now(tz='Asia/Seoul').isoformat(timespec='minutes'),
        script='analysis/exitprob.py', backtest='checks/exitprob_backtest.csv (2025 71저녁, 투어 29개, 그 투어를 뺀 나머지로 만든 표)',
        rules=dict(
            day1='P0: 2025 모든 저녁의 "시작 → 출차 시작(분)"을 10분 커널로 부드럽게. 과거 시험에서 시작 시각별·적힌 시간 방식보다 나빠지지 않은 가장 단순한 것.',
            day1_secondary='P2: 적힌 공연 시간 130분 + 2025 "출차 시작 − 적힌 시간" 분포(참고용, 채점은 같이 함)',
            day2_3='P3: 전날 이 공연의 실제 출차 시작(시작 뒤 분, end_detect_live.park_onset) + 2025 같은 공연 이틀 연속 차이 분포. 11/28·29 새벽에 전날 정답만 넣어 만들고 해시를 남김.',
            shape_size='출차 시작 뒤 2시간 모양·크기: 2025 저녁 하나하나를 후보로(같은 무게), 크기 중앙값 %.0f대(2025 단위), 판매수 안 씀' % np.median(EVN['size']),
            baseline='같은 요일 무리(평일 / 주말·공휴일) 공연 없는 날의 같은 시각 순유출 중앙값',
            scale='2026 parking_sum 단위 = 2025 × %.3f (공연 없는 평일 하루 변동폭 1335 / 2056)' % K_SCALE,
            thresholds='혼잡 ≥ %.0f대/10분(공연 없는 저녁 18~24시 10분 순유출의 상위 5%%), 매우 혼잡 ≥ %.0f대/10분(2025 출차 시작 뒤 2시간의 상위 20%%), 2025 단위. 2026 단위는 × K. 바닥도 공연 없는 날 하나하나를 후보로 둠. 실제 서비스 기준은 운영자가 정함 — 이건 시험용.' % (THR['혼잡'], THR['매우 혼잡']),
            update='"아직 안 끝남" 고침: 판단 시각 T(시작+150·180분)까지 주차 감지(10분에 6.5%% 감소, end_detect_prereg)가 안 울렸으면 출차 시작 > T−15분만 남기고 다시 나눔, 울렸으면 감지 − (2025 감지−출차 시작) 분포로 바꿈. T까지의 자료만 쓰므로 공연 뒤에 계산해도 됨.'),
        scoring=dict(
            truth='end_detect_live.park_onset(그날 parking_sum) — 이미 고정된 정의',
            primary='① 출차 시작 칸 로그점수: P0 표 vs 점 두 개(예정 종료 + 42분, 시작 시각별 중앙값) — 점은 맞은 칸 1, 나머지 0.001 ② 80% 범위에 들었는지',
            secondary='③ 시작+90~330분 10분 칸 "혼잡" Brier(2026 기준) P0 vs 점 ④ 10분 순유출 평균 절대오차 ⑤ 고친 표(T=150·180) vs 미리 만든 표',
            caution='세 저녁뿐이라 통계로 이겼다 졌다를 말할 수 없음 — 2025 과거 시험과 같은 방향인지만 봄'),
        point_forecasts=dict(sched_plus_42={'2026-11-27': '19:00+130+42=21:52 → 21:50 칸', '2026-11-28': '18:00+172 → 20:52 → 20:50 칸', '2026-11-29': '17:00+172 → 19:52 → 19:50 칸'}),
        tables={'2026-11-27 P0': table_json('2026-11-27', '19:00', 130, 'P0'), '2026-11-27 P2': table_json('2026-11-27', '19:00', 130, 'P2'),
                '2026-11-28 P0(전날 없을 때 예비)': table_json('2026-11-28', '18:00', 130, 'P0'), '2026-11-29 P0(전날 없을 때 예비)': table_json('2026-11-29', '17:00', 130, 'P0')})
    for k in ('2026-11-28', '2026-11-29'):
        st = hm({'2026-11-28': '18:00', '2026-11-29': '17:00'}[k]); same = EVN[(EVN.st // 60) == st // 60]
        out['point_forecasts'].setdefault('start_hour_median', {})[k] = float(np.median((same if len(same) >= 5 else EVN).onset))
    same = EVN[(EVN.st // 60) == 19]; out['point_forecasts'].setdefault('start_hour_median', {})['2026-11-27'] = float(np.median((same if len(same) >= 5 else EVN).onset))
    json.dump(out, open('checks/exitprob_prereg_20261127.json', 'w'), ensure_ascii=False, indent=1); print('saved')
if __name__ == '__main__' and sys.argv[1] == 'next':  # python3 exitprob.py next 2026-11-28 18:00 <전날 day> <전날 start> parking.csv
    d, t, pd_, pt, pk = sys.argv[2:7]; import importlib.util
    spec = importlib.util.spec_from_file_location('edl', os.path.join(HERE, 'end_detect_live.py')); edl = importlib.util.module_from_spec(spec); spec.loader.exec_module(edl)
    park = edl.load_park(pk) if 'time_kst' in open(pk).readline() else load_live_park(pk); s0 = pd.Timestamp(f'{pd_} {pt}')
    prev = (edl.park_onset(park, s0) - s0) / pd.Timedelta(minutes=1)
    out = table_json(d, t, 130, 'P3', prev=float(prev)); out['prev_day'] = pd_; out['made_at'] = pd.Timestamp.now(tz='Asia/Seoul').isoformat(timespec='minutes')
    fn = 'checks/exitprob_%s.json' % d.replace('-', ''); json.dump(out, open(fn, 'w'), ensure_ascii=False, indent=1); print(fn, '전날 출차 시작 시작+%.0f분' % prev, '80%', out['onset_80'], '중앙', out['onset_median_slot'])
if __name__ == '__main__' and sys.argv[1] == 'score':  # python3 exitprob.py score 2026-11-27 19:00 130 <표 json> <key or -> parking.csv
    d, t, run, fn, key, pk = sys.argv[2:8]; run = float(run); st = hm(t); import importlib.util
    spec = importlib.util.spec_from_file_location('edl', os.path.join(HERE, 'end_detect_live.py')); edl = importlib.util.module_from_spec(spec); spec.loader.exec_module(edl)
    J = json.load(open(fn)); T = J['tables'][key] if key != '-' else J
    park = load_live_park(pk); s0 = pd.Timestamp(f'{d} {t}'); on = (edl.park_onset(park, s0) - s0) / pd.Timedelta(minutes=1); o = int(on // 10)
    p = np.array([r['p_onset'] for r in T['table']]); exp = np.array([r['exp_net_2026'] for r in T['table']]); pc = np.array([r['p_busy'] for r in T['table']])
    act = live_net10(park, d, st); thr = T['thr_2026']['혼잡']; k = np.arange(W0, W1)
    cs = np.cumsum(p); lo, hi = np.searchsorted(cs, 0.1), np.searchsorted(cs, 0.9)
    pt_sched = int(((run + 42) // 10)); pt_med = int(J.get('point_forecasts', {}).get('start_hour_median', {}).get(d, 175) // 10) if key != '-' else None
    res = dict(day=d, onset_after_start_min=float(on), onset_slot=T['table'][o]['slot'], in_80=bool(lo <= o <= hi), range_80=T['onset_80'],
               logp_table=float(np.log(max(p[o], 1e-3))), logp_sched42=float(np.log(1.0 if o == pt_sched else 1e-3)),
               brier_busy_table=float(np.mean((pc[k] - (act[k] >= thr)) ** 2)), mae_net_table=float(np.mean(np.abs(exp[k] - act[k]))))
    # 점 예측의 혼잡 Brier·MAE(같은 모양·크기로)
    for name, slot in (('sched42', pt_sched), ('hour_median', pt_med)):
        if slot is None: continue
        pp = np.zeros(len(G5)); pp[min(slot * 2, len(G5) - 1)] = 1; _, e2, c2, _, _ = forecast(EVN, st, run, wkg(d), 'P0', pdist=pp)
        res['brier_busy_' + name] = float(np.mean((c2[k] - (act[k] * 1 >= thr)) ** 2)); res['mae_net_' + name] = float(np.mean(np.abs(e2[k] * K_SCALE - act[k])))
        if name == 'hour_median': res['logp_hour_median'] = float(np.log(1.0 if o == slot else 1e-3))
    res['actual_net10_2026'] = [round(float(x), 1) for x in act]
    print(json.dumps(res, ensure_ascii=False, indent=1))
