# 1. 파이썬 3.12 슬림 버전 사용 (가볍고 빠름)
FROM python:3.11-slim

# 2. 작업 폴더 설정
WORKDIR /app

# (Debian/슬림 계열 기준 예시)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libpng-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. 파이썬 패키지 설치
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel Cython setuptools-scm \
    && pip install --no-cache-dir numpy \
    && pip install --no-cache-dir --no-build-isolation -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. Streamlit 기본 포트 개방
EXPOSE 8501

# 7. 실행 명령어 (서버 주소 0.0.0.0으로 설정해야 외부 접속 가능)
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]