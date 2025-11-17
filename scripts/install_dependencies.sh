#!/bin/bash
# CodeDeploy 훅: AfterInstall (코드가 복사된 후 실행)

echo "--- 2. 애플리케이션 의존성 설치 시작 ---"

DEPLOY_DIR="/home/ubuntu/EclipseMainServer"
VENV_PATH="$DEPLOY_DIR/venv"
PYTHON_BIN="$VENV_PATH/bin/python3.10" # 생성할 venv 내부의 Python 실행 파일

# 1. 작업 디렉토리로 이동 (필수: requirements.txt 파일 접근을 위함)
cd $DEPLOY_DIR

# 2. 가상 환경(venv) 생성 (--without-pip 옵션 사용)
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating Python virtual environment with --without-pip..."
    # /usr/bin/python3.10은 1단계에서 설치한 시스템 Python을 사용
    /usr/bin/python3.10 -m venv venv --without-pip
fi

# 3. 가상 환경 내부에 수동으로 pip 설치
echo "Manually installing pip inside the virtual environment..."
# curl을 사용하여 get-pip.py를 다운로드하고, 가상 환경 내부의 Python 실행 파일로 pip을 설치
curl -sL https://bootstrap.pypa.io/get-pip.py | $PYTHON_BIN

# 4. 의존성 설치
echo "Installing dependencies from requirements.txt..."
# 가상 환경 내부의 pip 실행 파일 경로를 직접 사용하여 설치합니다.
$VENV_PATH/bin/pip install -r requirements.txt

echo "--- 2. 의존성 설치 완료 ---"