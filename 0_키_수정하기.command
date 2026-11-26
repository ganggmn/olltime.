#!/bin/bash
# 더블클릭하면 .env(인증키 파일)를 텍스트 편집기로 열어요
cd "$(dirname "$0")"
open -e .env
exit 0
