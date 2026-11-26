"""퇴장 시뮬레이션을 2025년 주차 출차(5분, KSPO DOME 저녁 54개)에 맞추고, 앞서 정한 값들과 비교해요(탐색).
맞추는 것: 출차 시작 뒤 120분 동안 늘어난 출차의 누적 %(5분마다). 차 수는 실측 티켓 1,000장당 96대, 게이트는 실측 최고 5분 133대 − 평소 30대.
바꿔 보는 것: 끝난 뒤 일어나는 평균 시간 mu, 먼저 나가는 몫 early, 늦게까지 남는 몫 linger(평균 linger_mu분).
비교하는 것: ① 감지(10분 6.5% 감소) − 출차 시작(2025 실측 중앙 15분, 감지기에 고정한 값) ② 5분 최고 출차 ③ 감지기 퇴장 모양 g(11/22로 정한 값)
사용: analysis/egress 폴더에서 python3 calibrate.py → data/calibrate.json"""
import json, itertools, numpy as np, pandas as pd
from egress_sim import run
O = json.load(open('data/egress_obs.json')); OBS = np.array(O['cum_median']); N = int(O['tickets_med'])
CPT = O['cars_per_1000_med'] / 1000; BASE5 = O['base5_med']; GATE = (O['peak5_med'] - BASE5) / 5; OCC = O['occ_on_med']; PPL = 2.2
PRE = json.load(open('../end_detect_prereg.json')); GT, GF = PRE['nowcast']['g_tau_min'], PRE['nowcast']['g_frac']
def onset(ex5):
    s = pd.Series(ex5); r = s + s.shift(1); ip = int(r.idxmax()); b10 = 2 * float(np.median(ex5[:6])); thr = b10 + 0.3 * (r[ip] - b10); i = ip
    while i - 1 >= 1 and r[i - 1] >= thr: i -= 1
    return i - 2
def sim(mu, early, linger, lmu, gate=GATE, seed=0, full=False, n=N, pf=0.74):
    r = run(N=n, pf=pf, start='param', mu=mu, early=early, linger=linger, linger_mu=lmu, seed=seed, car_share=CPT * PPL, sub_share=0.59, ppl_car=PPL, gate_cpm=gate, ret=True)
    tc = r['t_car'] / 60  # 끝난 뒤 분
    edges = np.arange(-60, 361, 5); ex5 = np.histogram(tc, edges)[0] + BASE5
    on = min(max(onset(ex5), 1), len(ex5) - 24); base = ex5[max(0, on - 6):on].mean(); post = np.clip(ex5[on:on + 24] - base, 0, None); cum = np.cumsum(post) / post.sum()
    t_on = edges[on]  # 출차 시작(끝난 뒤 분)
    # 감지: 10분 동안 나간 차 ≥ 6.5% × 그때 주차 대수(출차 시작 때 OCC에서 시작)
    tcs = np.sort(tc); fire = np.nan
    for t in np.arange(t_on, 240, 5):
        out10 = ((tcs > t - 10) & (tcs <= t)).sum(); occ = OCC - ((tcs > t_on) & (tcs <= t - 10)).sum()
        if out10 >= 0.065 * occ: fire = t; break
    res = dict(mu=mu, early=early, linger=linger, lmu=lmu, gate=round(gate, 1), sse=float(((cum - OBS) ** 2).sum()), onset_after_end=float(t_on), fire_after_end=float(fire),
               fire_minus_onset=float(fire - t_on), peak5=int(ex5.max()))
    if full:
        # 공원 경계를 나간 몫(지하철·그 밖: 목적지 도착, 차: 주차장 출차) vs 감지기 g(τ), τ = 시각 − (감지 − 15분)
        left = np.where(r['mode'] == 'car', np.nan, r['t_dest'] / 60)
        carp = np.repeat(np.sort(tc), int(round(PPL)))[: (r['mode'] == 'car').sum()]
        allt = np.r_[left[~np.isnan(left)], carp]; est_end = fire - 15
        res['g_sim'] = [float((allt <= est_end + t).mean()) for t in GT]; res['g_pre'] = GF; res['cum'] = cum.round(3).tolist()
        res['bowl90'] = float(np.percentile(r['t_bowl'], 90) / 60); res['sub50'] = float(np.percentile(r['t_dest'][r['mode'] == 'sub'], 50) / 60)
    return res
if __name__ == '__main__':
    rows = [sim(mu, e, l, lm, gate=g) for g, mu, e, l, lm in itertools.product([12.0, 14.0, 16.0, 18.0, GATE], [0, 2, 4, 6, 8, 10, 12, 15, 20, 25, 30], [0.0, 0.1, 0.2],
            [0.0, 0.1, 0.2, 0.3, 0.4, 0.5], [15, 30, 45, 60]) if not (l == 0 and lm != 15)]
    R = pd.DataFrame(rows).sort_values('sse'); print('맞춘 조합 %d개 중 가장 잘 맞는 10개' % len(R)); print(R.head(10).round(3).to_string(index=False))
    b = R.iloc[0]; best = sim(b.mu, b.early, b.linger, b.lmu, gate=b.gate, full=True)
    for g in [b.gate * 0.85, b.gate * 1.15]:
        print('게이트 %.1f대/분일 때:' % g, {k: round(v, 3) if isinstance(v, float) else v for k, v in sim(b.mu, b.early, b.linger, b.lmu, gate=g).items() if k in ('sse', 'fire_minus_onset', 'onset_after_end', 'fire_after_end', 'peak5')})
    seeds = [sim(b.mu, b.early, b.linger, b.lmu, gate=b.gate, seed=s) for s in range(10)]
    best['fire_minus_onset_seeds'] = [x['fire_minus_onset'] for x in seeds]; best['onset_after_end_seeds'] = [x['onset_after_end'] for x in seeds]
    for pf in [0.0, 1.0]: best['pf%.0f' % pf] = {k: v for k, v in sim(b.mu, b.early, b.linger, b.lmu, gate=b.gate, pf=pf).items() if k in ('fire_minus_onset', 'onset_after_end', 'fire_after_end')}
    for n in [7744, 14000]: best['n%d' % n] = {k: v for k, v in sim(b.mu, b.early, b.linger, b.lmu, gate=b.gate, n=n).items() if k in ('fire_minus_onset', 'onset_after_end', 'fire_after_end', 'peak5')}
    print('실측 감지 − 출차 시작(같은 정의) 중앙 %.0f분(10~90%% %.0f~%.0f)' % (O['fire_minus_onset_med'], *O['fire_minus_onset_q']))
    print({k: best[k] for k in ['mu', 'early', 'linger', 'lmu', 'gate', 'sse', 'onset_after_end', 'fire_after_end', 'fire_minus_onset', 'peak5', 'bowl90', 'sub50']})
    print('씨앗 10개: 감지−출차 시작', best['fire_minus_onset_seeds'], '| 출차 시작−끝', best['onset_after_end_seeds'])
    print('여성 0%:', best['pf0'], '| 여성 100%:', best['pf1']); print('7,744명:', best['n7744'], '| 14,000명:', best['n14000'])
    print('g 시뮬:', [round(x, 2) for x in best['g_sim']]); print('g 감지기:', best['g_pre'])
    print('실측 누적:', (100 * OBS).round().astype(int).tolist()); print('맞춘 누적:', (100 * np.array(best['cum'])).round().astype(int).tolist())
    json.dump(dict(obs=O, best=best, top=R.head(20).to_dict('records')), open('data/calibrate.json', 'w'), ensure_ascii=False, indent=1, default=float)
