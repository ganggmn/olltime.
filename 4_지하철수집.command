#!/bin/bash
# 더블클릭하면: 올림픽공원 주변 3개 역 실시간 지하철 도착정보를 매일 14:30~01:00에 2분마다 수집(켜 두면 며칠이고 그 시간만). 멈추려면 Ctrl+C 또는 창 닫기
cd "$(dirname "$0")"
caffeinate -i python3 collect_subway.py
