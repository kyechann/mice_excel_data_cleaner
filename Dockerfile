# 1. 파이썬 3.12 슬림 버전 사용 (가볍고 빠름)
FROM python:3.12-slim

# 2. 작업 폴더 설정
WORKDIR /app

# 3. 필수 라이브러리 설치를 위해 파일 복사
COPY requirements.txt .

# 4. 라이브러리 설치
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. Streamlit 기본 포트 개방
EXPOSE 8501

# 7. 실행 명령어 (서버 주소 0.0.0.0으로 설정해야 외부 접속 가능)
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]