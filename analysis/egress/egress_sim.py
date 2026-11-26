"""KSPO DOME 공연 끝 → 관람석 출구 → 건물 밖 → 공원 경계(역 쪽 문)·주차장까지 퇴장 시뮬레이션(탐색).
좌석·출구 위치와 출구 폭: 한국체육산업개발 '올림픽공원 공연장 실감형 콘텐츠'(kspodome_dae, SketchUp 내보내기) → boxes.csv, seats.csv, exits_raw.csv
사람: 여성 키 159.6cm, 남성 172.5cm(제8차 사이즈코리아) → 몸 너비를 키에 비례한다고 보고 여성 0.925배.
      걷는 속도 여성 1.32, 남성 1.41 m/s(이스탄불 관찰 연구). 붐비는 줄(출구 대기)에서는 성별 속도 차이 없음(단일 줄 실험).
출구 통과: 사람마다 (자기 몸 너비 비율)/(문 폭 × q) 초가 걸림. q(남성 기준 1m당 1초에 지나가는 사람)는 가정값 1.3, 1.0~1.5로 바꿔 봄.
모든 값은 가정이 섞인 어림이라 '얼마나 걸릴 수 있나'의 범위를 보려는 것."""
import numpy as np, pandas as pd, json, sys
S = pd.read_csv('data/seats.csv'); X = pd.read_csv('data/exits_raw.csv', index_col=0)
X = X[~((X.mats == 'turnel_basic_wihte'))]  # 남쪽 무대 쪽 터널만 있는 곳(뒤편 통로) 뺌
X['grp'] = np.select([X.z1 <= 1.5, (X.z0 < 0) & (X.z1 <= 7.5), X.z0 >= 10.0], ['floor', 'floor', 'upper'], 'lower')
DEFW = {'floor': 3.0, 'lower': 2.4, 'upper': 1.8}
X['w'] = [w if (w == w and w >= 1.2) else DEFW[g] for w, g in zip(X.door_w, X.grp)]
TIER2GRP = {'바닥석(접이식)': ['floor', 'lower'], '아래층': ['lower'], '위층': ['upper']}
H_F, H_M = 159.6, 172.5; WREL = {1: H_F / H_M, 0: 1.0}; VFREE = {1: 1.32, 0: 1.41}
def run(N=10000, pf=0.74, q=1.3, W_out=40.0, start='all0', seed=0, car_share=0.15, sub_share=0.60, ppl_car=2.2, gate_cpm=26.0, aisle=0.6, outdoor=0.8, ret=False,
        mu=3.0, early=0.15, linger=0.0, linger_mu=20.0):
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(S), N, replace=N > len(S)); s = S.iloc[idx].reset_index(drop=True)
    fem = (rng.random(N) < pf).astype(int); wrel = np.where(fem == 1, WREL[1], WREL[0]); v = np.where(fem == 1, VFREE[1], VFREE[0]) * rng.normal(1, 0.1, N).clip(0.7, 1.3)
    if start == 'all0': t0 = np.zeros(N)
    elif start == 'real':  # 앙코르 중 먼저 나가는 15%(끝나기 10분 전~끝), 나머지는 끝난 뒤 평균 3분(감마)
        e_ = rng.random(N) < 0.15; t0 = np.where(e_, -rng.uniform(0, 600, N), rng.gamma(2.0, 90.0, N))
    else:  # 'param': 먼저 나감 early(끝나기 10분 전~끝), 남아 있다 늦게 감 linger(지수, 평균 linger_mu분), 나머지 감마(모양 2, 평균 mu분)
        u0 = rng.random(N)
        t0 = np.where(u0 < early, -rng.uniform(0, 600, N), np.where(u0 < early + linger, rng.exponential(linger_mu * 60, N), rng.gamma(2.0, max(mu, 1e-3) * 30.0, N)))
    # 가장 가까운 출구(같은 층 무리), 거리 = 수평 × 1.2 + 높이 차 × 2(계단)
    ex = np.full(N, -1); dist = np.zeros(N)
    for tier, grps in TIER2GRP.items():
        m = (s.tier == tier).values
        if not m.any(): continue
        E = X[X.grp.isin(grps)]
        dh = np.hypot(s.x.values[m, None] - E.x.values[None], s.y.values[m, None] - E.y.values[None]) * 1.2
        dz = np.abs(s.z.values[m, None] - ((E.z0 + E.z1) / 2).values[None]) * 2.0
        d = dh + dz; j = d.argmin(axis=1); ex[m] = E.index.values[j]; dist[m] = d[np.arange(m.sum()), j]
    t_arr = t0 + dist / (v * aisle)
    # 관람석 출구 줄
    t_bowl = np.zeros(N); W = X.w.to_dict()
    for e in np.unique(ex):
        k = np.where(ex == e)[0]; o = k[np.argsort(t_arr[k])]; last = -1e9
        for i in o:
            last = max(t_arr[i], last) + wrel[i] / (W[e] * q); t_bowl[i] = last
    # 복도 30m → 건물 바깥문(합친 폭 W_out)
    t_o = t_bowl + 30 / (v * 0.8); o = np.argsort(t_o); t_bld = np.zeros(N); last = -1e9
    for i in o:
        last = max(t_o[i], last) + wrel[i] / (W_out * q); t_bld[i] = last
    # 밖에서 걷기: 지하철(올림픽공원역 쪽 동2문, 600m), 차(주차장 450/570/700/930m), 그 밖(570~930m)
    u = rng.random(N); mode = np.where(u < sub_share, 'sub', np.where(u < sub_share + car_share, 'car', 'oth'))
    dout = np.where(mode == 'sub', 600.0, np.where(mode == 'car', rng.choice([450, 570, 700, 930], N, p=[.4, .3, .2, .1]), rng.choice([570, 930], N)))
    t_dest = t_bld + dout / (v * outdoor)
    # 차: 한 대에 ppl_car명, 마지막 사람이 오면 2분 뒤 출발, 1~2분 운전, 게이트 전체 1분에 gate_cpm대
    c = np.where(mode == 'car')[0]; rng.shuffle(c); ncar = max(1, int(len(c) / ppl_car)); groups = np.array_split(c, ncar)
    t_ready = np.array([t_dest[g].max() for g in groups]) + 120 + rng.uniform(60, 120, ncar)
    t_ready.sort(); t_car = np.zeros(ncar); last = -1e9
    for i, t in enumerate(t_ready):
        last = max(t, last) + 60 / gate_cpm; t_car[i] = last
    q_ = lambda a, p: float(np.percentile(a, p)) / 60
    out = dict(N=N, pf=pf, q=q, W_out=W_out, start=start,
               bowl50=q_(t_bowl, 50), bowl90=q_(t_bowl, 90), bowl100=q_(t_bowl, 100), bld50=q_(t_bld, 50), bld90=q_(t_bld, 90), bld100=q_(t_bld, 100),
               sub50=q_(t_dest[mode == 'sub'], 50), sub90=q_(t_dest[mode == 'sub'], 90), car_first=float(t_car.min()) / 60, car50=q_(t_car, 50), car90=q_(t_car, 90), ncar=ncar)
    if ret: out.update(t_bowl=t_bowl, t_bld=t_bld, t_dest=t_dest, mode=mode, t_car=t_car, t0=t0, ex=ex, fem=fem)
    return out
if __name__ == '__main__':
    print('출구: 바닥 %d곳(폭 합 %.0fm), 아래층 %d곳(%.0fm), 위층 %d곳(%.0fm)' % tuple(v for g in ['floor', 'lower', 'upper'] for v in (int((X.grp == g).sum()), X[X.grp == g].w.sum())))
    rows = []
    for start in ['all0', 'real']:
        for N in [7744, 10000, 14000]:
            for pf in [0.0, 0.5, 0.74, 1.0]:
                rows.append(run(N=N, pf=pf, start=start))
        for q in [1.0, 1.5]: rows.append(run(N=10000, pf=0.74, q=q, start=start))
        for W in [20.0, 80.0]: rows.append(run(N=10000, pf=0.74, W_out=W, start=start))
    R = pd.DataFrame(rows); R.round(2).to_csv('data/egress_runs.csv', index=False)
    pd.set_option('display.width', 250); print(R.round(1).to_string(index=False))
