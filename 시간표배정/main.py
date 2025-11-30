"""
main.py

- FastAPI 애플리케이션 생성
- 라우터 등록 (scheduler.router)
"""

from fastapi import FastAPI
from scheduler.router import router as scheduler_router

# =======================================
# FastAPI 앱 생성
# =======================================
app = FastAPI(
    title="강의실 자동배정 & 공실 분석 API",
    description="CSV 강의 정보 기반 자동배정 + 공실 분석 + ICS 생성 서비스",
    version="1.0.0",
)

# =======================================
# 라우터 등록
#  - 모든 엔드포인트는 scheduler/router.py 에 정의
# =======================================
app.include_router(scheduler_router)

# 여기서 미들웨어, CORS, 이벤트 훅(on_startup 등)을 추가해도 됨
