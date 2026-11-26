#!/bin/bash
# 더블클릭하면: 올림픽공원 실시간 주차 대수(동2·남2·북2 합계)를 10분마다 수집. 멈추려면 Ctrl+C 또는 창 닫기
cd "$(dirname "$0")"
caffeinate -i python3 collect_parking.py
