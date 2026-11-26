"""KSPO DOME 실감형 콘텐츠(DAE)에서 재질별로 세계 좌표 상자(최소·최대)를 뽑아요. 단위: 원본 inch → m."""
import sys, time, json, collections, numpy as np, collada
t0 = time.time()
m = collada.Collada(sys.argv[1], ignore=[collada.common.DaeUnsupportedError, collada.common.DaeBrokenRefError])
print('loaded %.0fs' % (time.time() - t0), flush=True)
U = 0.0254
rows = []; cnt = collections.Counter()
for bg in m.scene.objects('geometry'):
    for bp in bg.primitives():
        mat = bp.material.name if bp.material is not None and hasattr(bp.material, 'name') else str(getattr(bp, 'material', None))
        v = bp.vertex
        if v is None or len(v) == 0: continue
        idx = np.unique(bp.vertex_index.ravel()) if hasattr(bp, 'vertex_index') and bp.vertex_index is not None else None
        vv = v[idx] if idx is not None and len(idx) else v
        lo = vv.min(axis=0) * U; hi = vv.max(axis=0) * U
        rows.append((mat, *np.round(lo, 3), *np.round(hi, 3), len(idx) if idx is not None else len(v)))
        cnt[mat] += 1
print('primitives %d, %.0fs' % (len(rows), time.time() - t0), flush=True)
import pandas as pd
D = pd.DataFrame(rows, columns=['mat', 'x0', 'y0', 'z0', 'x1', 'y1', 'z1', 'nv'])
D.to_csv(sys.argv[2], index=False)
print(D.groupby('mat').agg(n=('nv', 'size'), x0=('x0', 'min'), x1=('x1', 'max'), y0=('y0', 'min'), y1=('y1', 'max'), z0=('z0', 'min'), z1=('z1', 'max')).round(1).sort_values('n', ascending=False).to_string())
