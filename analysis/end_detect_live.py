"""공연 종료 감지기(실시간판)와 채점. 규칙은 analysis/end_detect_prereg.json에 고정한 그대로예요.
사용: python3 analysis/end_detect_live.py 2026-11-27 19:00 130 <주차 5분 CSV> <서울시 원본 raw_YYYYMMDD.jsonl.gz>
  주차 CSV: time_kst,parking_sum (5분). 서울시 원본: 수집기가 남긴 줄마다 response.CITYDATA.LIVE_PPLTN_STTS[0].PPLTN_TIME과 범위.
판단에 쓰는 값은 그 시각에 실제로 손에 있었던 것만이에요: 주차는 그 시각까지, 서울시 인구는 기준 시각이 30분 넘게 지난 것만."""
import sys, json, gzip, numpy as np, pandas as pd
PRE = json.load(open(__file__.replace('end_detect_live.py', 'end_detect_prereg.json'), encoding='utf-8'))
R = PRE['rule']; G = PRE['nowcast']
def load_pop(path):
    rows = []
    for line in gzip.open(path, 'rt', encoding='utf-8'):
        try: p = json.loads(line)['response']['CITYDATA']['LIVE_PPLTN_STTS'][0]
        except Exception: continue
        rows.append((pd.Timestamp(p['PPLTN_TIME']), (float(p['AREA_PPLTN_MIN']) + float(p['AREA_PPLTN_MAX'])) / 2))
    return pd.DataFrame(rows, columns=['t', 'mid']).drop_duplicates('t').set_index('t').mid.sort_index()
def load_park(path):
    d = pd.read_csv(path); d['t'] = pd.to_datetime(d.time_kst); return d.set_index('t').parking_sum.sort_index().resample('5min').last().interpolate()
def fire_time(park, start, sched_end, upto):
    e0 = max(start + pd.Timedelta(minutes=R['earliest_after_start_min']), sched_end - pd.Timedelta(minutes=R['earliest_before_sched_min']))
    s = park[:upto]
    for t in s.index:
        if t < e0: continue
        prev = s.get(t - pd.Timedelta(minutes=10))
        if prev is not None and not np.isnan(prev) and prev - s[t] >= R['rel_drop_10min'] * max(prev, 1): return t
    return None
def g(tau):
    return float(np.interp(tau, G['g_tau_min'], G['g_frac'], left=G['g_frac'][0], right=1.0))
def nowcast(pop, park, start, sched_end, T, which):
    """T 시각에 '지금 공원 인원'을 어림. N0 = 손에 있는 가장 최근 서울시 값, N1 = 감지한 종료로, N2 = 예정 종료로 퇴장 모양을 얹음"""
    known = pop[:T - pd.Timedelta(minutes=PRE['seoul_lag_min'])]
    if not len(known): return np.nan
    last = known.iloc[-1]
    if which == 'N0': return last
    if which == 'N1':
        f = fire_time(park, start, sched_end, T)
        if f is None: return last
        end = f - pd.Timedelta(minutes=R['end_before_fire_min'])
    else:
        if T < sched_end: return last
        end = sched_end
    plat = known[start + pd.Timedelta(minutes=30): end - pd.Timedelta(minutes=10)]
    P = float(np.median(plat)) if len(plat) else float(last)
    D = P * (1 - G['post_ratio'])
    return P - D * g((T - end) / pd.Timedelta(minutes=1))
def park_onset(park, start):
    """사후 정답: 10분 동안 줄어든 대수가 가장 큰 칸에서 거꾸로 걸어가, 그 30% 아래로 내려가기 직전 칸의 10분 앞"""
    s = park[start + pd.Timedelta(minutes=60): start + pd.Timedelta(hours=6)]; dr = (s.shift(2) - s)
    ip = dr.idxmax(); thr = 0.3 * dr[ip]; i = list(dr.index).index(ip)
    while i - 1 >= 0 and dr.iloc[i - 1] >= thr: i -= 1
    return dr.index[i] - pd.Timedelta(minutes=10)
def score(day, start_hm, runtime, park_csv, pop_gz):
    start = pd.Timestamp(f'{day} {start_hm}'); sched_end = start + pd.Timedelta(minutes=runtime or PRE['default_runtime_min'])
    pop = load_pop(pop_gz); park = load_park(park_csv)
    f = fire_time(park, start, sched_end, start + pd.Timedelta(hours=6)); on = park_onset(park, start)
    plat = pop[start + pd.Timedelta(minutes=30): on - pd.Timedelta(minutes=10)]; P = float(np.median(plat))
    after = pop[start + pd.Timedelta(minutes=60):]; dropt = after[after <= P - 2000].index.min()
    out = dict(day=day, start=start_hm, sched_end=str(sched_end.time())[:5], park_onset=str(on.time())[:5], fire=None if f is None else str(f.time())[:5],
               est_end=None if f is None else str((f - pd.Timedelta(minutes=R['end_before_fire_min'])).time())[:5],
               pop_drop_stamp=None if pd.isna(dropt) else str(dropt.time())[:5], pop_drop_seen=None if pd.isna(dropt) else str((dropt + pd.Timedelta(minutes=PRE['seoul_lag_min'])).time())[:5])
    out['est_end_minus_onset_min'] = None if f is None else ((f - pd.Timedelta(minutes=R['end_before_fire_min'])) - on) / pd.Timedelta(minutes=1)
    out['sched_end_minus_onset_min'] = (sched_end - on) / pd.Timedelta(minutes=1)
    out['lead_vs_pop_min'] = None if (f is None or pd.isna(dropt)) else ((dropt + pd.Timedelta(minutes=PRE['seoul_lag_min'])) - f) / pd.Timedelta(minutes=1)
    Ts = pd.date_range(on - pd.Timedelta(minutes=15), on + pd.Timedelta(minutes=90), freq='5min'); res = {}
    for w in ('N0', 'N1', 'N2'):
        e = []; a = []
        for T in Ts:
            if T not in pop.index: continue
            p = nowcast(pop, park, start, sched_end, T, w); e.append(abs(p - pop[T])); a.append(pop[T])
        res[w] = dict(acc=round(100 * (1 - sum(e) / sum(a)), 1), mae=round(float(np.mean(e))), n=len(e))
    out['nowcast'] = res
    return out
if __name__ == '__main__':
    day, hm, rt, pk, pg = sys.argv[1:6]
    print(json.dumps(score(day, hm, int(rt) if rt not in ('', '0', 'None') else None, pk, pg), ensure_ascii=False, indent=1))
