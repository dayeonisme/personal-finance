#!/bin/zsh
cd "$(dirname "$0")"

# 이미 실행 중이면 바로 브라우저만 열기
if lsof -ti:8501 > /dev/null 2>&1; then
    open "http://127.0.0.1:8501"
    exit 0
fi

# 서버 시작
.venv/bin/streamlit run dashboard/app.py \
    --server.address 127.0.0.1 \
    --server.port 8501 \
    --server.headless true &

# 서버 준비될 때까지 대기 후 브라우저 열기
sleep 2
open "http://127.0.0.1:8501"

# 서버 로그 유지 (터미널 창 닫으면 서버도 종료)
wait
