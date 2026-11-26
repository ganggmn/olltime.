#!/bin/bash
# 더블클릭하면: 올림픽공원 주변 버스 정류장·지하철역의 최근 40일 하루 승하차 인원을 받아서 요약해요 (5~10분)
cd "$(dirname "$0")"
python3 fetch_ridership.py 40
echo
read -n 1 -s -r -p "끝났어요. 아무 키나 누르면 창이 닫혀요."
