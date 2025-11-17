#!/bin/bash
DEPLOY_DIR="/home/ubuntu/EclipseMainServer"
UVICORN_PATH="$DEPLOY_DIR/venv/bin/uvicorn" # 가상 환경 내부의 Uvicorn 절대 경로
lsof -t -i:8080 | xargs -r kill -9
sudo -u ubuntu $UVICORN_PATH src.main:app --host 0.0.0.0 --port 8080 --workers 4 --daemon --chdir $DEPLOY_DIR

echo "Uvicorn started."