import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# 수정 — 이 파일 기준으로 상위 폴더까지 올라가며 .env 탐색
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


# 환경 변수 로드
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# 명세서 기준: utf8mb4 인코딩 적용 (한글/이모지 보호) [cite: 111, 140, 220]
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# 엔진 설정: 연결 유실 방지 및 다중 접속 최적화
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True, # 연결 유효성 체크
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)

# 세션 관리 설정
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 기본 클래스
Base = declarative_base()

# FastAPI 의존성 주입용 DB 세션 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()