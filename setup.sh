#!/bin/bash

# 에러 발생 시 중단
set -e

echo "노이즈 모니터 설치를 시작합니다..."

# 1. 시스템 패키지 업데이트 및 필수 라이브러리 설치
echo "시스템 패키지를 설치 중입니다 (sudo 권한 필요)..."
sudo apt update
sudo apt install -y libportaudio2 portaudio19-dev python3-venv python3-pip python3-tk

# 2. 가) 가상환경 생성
if [ ! -d "venv" ]; then
    echo "가상환경(venv)을 생성합니다..."
    python3 -m venv venv
else
    echo "이미 가상환경이 존재합니다."
fi

# 3. 가상환경 활성화 및 패키지 설치
echo "파이썬 패키지를 설치 중입니다..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 4. .env 파일 체크
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo ".env.example 파일을 복사하여 .env 파일을 만듭니다. 나중에 API 키를 설정해주세요."
        cp .env.example .env
    else
        echo ".env.example 파일이 없습니다. 설정을 수동으로 확인해주세요."
    fi
fi

echo ""
echo "모든 설치가 완료되었습니다!"
echo "실행하려면 아래 명령어를 입력하세요:"
echo "   source venv/bin/activate"
echo "   python3 main.py both"
