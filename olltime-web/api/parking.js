/* GET /api/parking: 올림픽공원 동2·남2·북2문 주차장에 지금 있는 차 대수.
   한국체육산업개발이 누리집에 공개한 공용 키를 써요. 10분 동안 CDN에 저장해요. */
const URL = 'https://www.ksponco.or.kr/online/main/parkingorsApi.do?apiKey=PARKING21803504';

export default async function handler(req, res) {
  try {
    const r = await fetch(URL, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    let body = await r.json();
    if (Array.isArray(body)) body = body[0] || {};
    const code = String(body.code || body.resultCode || '0000');
    const sum = Number.parseInt(body.parking_sum, 10);
    if (code !== '0000' || !Number.isFinite(sum)) {
      res.setHeader('Cache-Control', 's-maxage=60');
      return res.status(200).json({ ok: false, code, note: code === '9999' ? '점검 중' : '값 없음' });
    }
    res.setHeader('Cache-Control', 's-maxage=600, stale-while-revalidate=1200');
    return res.status(200).json({ ok: true, sum, at: new Date().toISOString() });
  } catch (e) {
    res.setHeader('Cache-Control', 's-maxage=30');
    return res.status(502).json({ ok: false, error: String(e && e.message || e) });
  }
}
