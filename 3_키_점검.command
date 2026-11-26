#!/bin/bash
# 더블클릭하면 각 인증키로 API를 3건씩만 불러서 되는지 확인해요 (키는 화면에 안 나와요)
cd "$(dirname "$0")"
python3 check_keys.py
