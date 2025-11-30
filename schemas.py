"""
schemas.py

- API 요청/응답에 사용되는 Pydantic 모델 정의
"""

from pydantic import BaseModel
from typing import List


# =======================================
# 교수별 선호 요일 설정 요청 모델
#  - /preferred-days POST 요청 바디에 사용
# =======================================
class PreferredDaysRequest(BaseModel):
    prof: str           # 교수 이름
    days: List[str]     # 예: ["월", "수"]
