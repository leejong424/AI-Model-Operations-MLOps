"""
models.py

- 서버 메모리에 저장되는 전역 상태(AppState) 정의
- DB를 쓰지 않고, 업로드된 CSV와 배정 결과를 DataFrame 형태로 유지
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd


# =======================================
# AppState: 애플리케이션 전역 상태
# =======================================
@dataclass
class AppState:
    """
    original_df : 업로드된 원본 CSV 데이터
    result_df   : 시간표 자동 배정 결과
    preferred_days : 교수별 선호 요일 설정 (예: {"홍길동": ["월", "수"]})
    """

    original_df: Optional[pd.DataFrame] = None
    result_df: Optional[pd.DataFrame] = None
    preferred_days: Dict[str, List[str]] = field(default_factory=dict)


# =======================================
# 전역 상태 인스턴스
#  - router / service 모듈에서 import 해서 사용
# =======================================
state = AppState()
