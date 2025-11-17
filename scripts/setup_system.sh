#!/bin/bash

echo "--- 1. 시스템 전역 Python 3.10 및 도구 설치 시작 ---"

if ! command -v python3.10 &> /dev/null
then
    echo "Installing Python 3.10, curl, and development dependencies..."
    # 1. 패키지 목록 업데이트
    sudo apt update
    sudo apt install software-properties-common -y
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    # 4. Python 3.10, 개발 도구 및 curl 설치
    sudo apt install python3.10 python3.10-dev curl -y
else
    echo "Python 3.10 is already installed. Skipping system setup."
fi

echo "--- 1. 시스템 설정 완료 ---"