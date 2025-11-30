"""
router.py

- FastAPI 엔드포인트 정의
- HTML 화면 + JSON API + ICS 다운로드까지 모두 이 파일에서 처리
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from io import StringIO
import pandas as pd

from .models import state
from .schemas import PreferredDaysRequest
from .service import (
    assign_timetable,
    compute_vacancy_stats,
    generate_ics_from_free_slots,
)

# =======================================
# 라우터 객체 생성
#  - prefix 없음: "/" 부터 바로 사용
#  - tags=["scheduler"]: Swagger 문서 그룹 이름
# =======================================
router = APIRouter(tags=["scheduler"])


# ====================================================
# 1. 메인 화면 (HTML) – 업로드 상태 + 기능 버튼들
# ====================================================
@router.get("/", response_class=HTMLResponse)
async def index():
    """
    메인 페이지
    - CSV 업로드 폼
    - 자동배정 실행 버튼
    - 공실 분석 페이지 링크
    - ICS 다운로드 폼
    """
    if state.original_df is None:
        status_html = "<p><b>현재: 업로드된 CSV 없음</b></p>"
    else:
        status_html = f"<p><b>현재: CSV 로드 완료 (행 수: {state.original_df.shape[0]}행)</b></p>"

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>강의실 자동배정 시스템 (FastAPI)</title>
    </head>
    <body>
        <h1>강의실 자동배정 시스템 (FastAPI)</h1>
        {status_html}

        <h2>1. CSV 업로드</h2>
        <form action="/upload-csv" enctype="multipart/form-data" method="post">
            <input name="file" type="file" />
            <input type="submit" value="업로드" />
        </form>
        <p>※ 업로드 후 자동으로 이 페이지로 돌아옵니다.</p>

        <h2>2. 자동 배정 실행</h2>
        <form action="/assign-html" method="post">
            <button type="submit">자동 배정 실행 및 결과 보기</button>
        </form>

        <h2>3. 공실 분석 / 대여 가능 시간</h2>
        <a href="/vacancy-html" target="_blank">공실 분석 및 대여 시간 HTML 보기</a><br><br>

        <h3>4. Google Calendar용 ICS 파일 다운로드</h3>
        <form action="/free-slots-ics" method="get" target="_blank">
            <label>기준 주의 월요일 날짜 (YYYY-MM-DD): </label>
            <input type="text" name="base_monday" value="2025-03-03" />
            <button type="submit">ICS 파일 다운로드</button>
        </form>

        <hr>
        <a href="/docs" target="_blank">Swagger API 문서 (/docs)</a>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# ====================================================
# 2. CSV 업로드 (업로드 후 다시 / 로 리다이렉트)
# ====================================================
@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """
    CSV 파일 업로드 엔드포인트
    - 업로드된 CSV를 pandas DataFrame으로 읽어 상태(state.original_df)에 저장
    - 기존 배정 결과(state.result_df)는 초기화
    """
    try:
        content = await file.read()
        df = pd.read_csv(StringIO(content.decode("utf-8")))
        state.original_df = df
        state.result_df = None  # 새 CSV 업로드 시 이전 배정 결과 초기화
        print("[INFO] CSV 업로드 완료, 행 수:", df.shape[0])

        # 업로드 후 메인 페이지로 리다이렉트
        resp = RedirectResponse(url="/", status_code=303)
        return resp
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV 읽기 실패: {e}")


# ====================================================
# 3. 교수 선호요일 설정 (JSON API)
# ====================================================
@router.post("/preferred-days")
async def set_preferred_days(req: PreferredDaysRequest):
    """
    교수별 선호 요일 설정
    - body: { "prof": "홍길동", "days": ["월", "수"] }
    - state.preferred_days 에 저장
    """
    prof = req.prof.strip()
    if not prof:
        raise HTTPException(status_code=400, detail="교수명이 비어 있습니다.")
    for d in req.days:
        if d not in ["월", "화", "수", "목", "금"]:
            raise HTTPException(status_code=400, detail=f"잘못된 요일: {d}")
    state.preferred_days[prof] = req.days
    return {"status": "ok", "prof": prof, "days": req.days}


@router.get("/preferred-days")
async def get_preferred_days():
    """
    현재 설정되어 있는 교수별 선호 요일 조회
    """
    return state.preferred_days


# ====================================================
# 4. 자동배정 – JSON API (Swagger 테스트용)
# ====================================================
@router.post("/assign")
async def run_assign_api():
    """
    자동배정 실행 (JSON 응답)
    - state.original_df 에 CSV가 로드되어 있어야 함
    """
    if state.original_df is None:
        raise HTTPException(status_code=400, detail="CSV가 먼저 업로드되어야 합니다.")
    result_df = assign_timetable(state.original_df, state.preferred_days)
    state.result_df = result_df
    return {
        "status": "ok",
        "count": int(result_df.shape[0]),
        "data": result_df.to_dict(orient="records"),
    }


# ====================================================
# 5. 자동배정 – HTML 결과보기
# ====================================================
@router.post("/assign-html", response_class=HTMLResponse)
async def run_assign_html():
    """
    자동배정 실행 후 결과를 HTML 테이블로 반환
    - 메인 페이지에서 버튼으로 호출
    """
    if state.original_df is None:
        return HTMLResponse(
            "<h2>CSV가 먼저 업로드되어야 합니다.</h2><a href='/'>메인으로 돌아가기</a>",
            status_code=400,
        )

    result_df = assign_timetable(state.original_df, state.preferred_days)
    state.result_df = result_df

    if result_df.empty:
        table_html = "<p>배정된 수업이 없습니다.</p>"
    else:
        table_html = result_df.to_html(index=False, justify="center")

    html = f"""
    <html>
    <head><meta charset="utf-8"><title>자동 배정 결과</title></head>
    <body>
        <h1>자동 배정 결과</h1>
        {table_html}
        <br><a href="/">메인으로 돌아가기</a>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# ====================================================
# 6. 공실 분석 – JSON API
# ====================================================
@router.get("/vacancy")
async def get_vacancy_api():
    """
    공실 분석 결과를 JSON으로 응답
    - room_stats : 강의실별 공실률 정보
    - free_slots : 대여 가능 시간 슬롯 리스트
    """
    if state.result_df is None or state.result_df.empty:
        raise HTTPException(
            status_code=400,
            detail="먼저 자동 배정을 실행해 주세요 (/assign 또는 /assign-html).",
        )
    room_stats, free_slots = compute_vacancy_stats(state.result_df)
    return {"room_stats": room_stats, "free_slots": free_slots}


# ====================================================
# 7. 공실 분석 – HTML + ICS 생성 폼
# ====================================================
@router.get("/vacancy-html", response_class=HTMLResponse)
async def vacancy_html():
    """
    공실 분석 / 대여 가능 시간을 HTML 테이블로 보여주는 페이지
    - 하단에 ICS 다운로드 폼도 함께 표시
    """
    if state.result_df is None or state.result_df.empty:
        return HTMLResponse(
            "<h2>먼저 자동 배정을 실행해 주세요.</h2><a href='/'>메인으로</a>",
            status_code=400,
        )

    room_stats, free_slots = compute_vacancy_stats(state.result_df)

    df_room = pd.DataFrame(room_stats)
    df_free = pd.DataFrame(free_slots)

    room_html = df_room.to_html(index=False, justify="center")
    free_html = df_free.to_html(index=False, justify="center")

    html = f"""
    <html>
    <head><meta charset="utf-8"><title>공실 분석 및 대여 가능 시간</title></head>
    <body>
        <h1>공실 분석</h1>
        {room_html}
        <h1>대여 가능 시간 (슬롯)</h1>
        {free_html}

        <h3>Google Calendar용 ICS 파일 다운로드</h3>
        <form action="/free-slots-ics" method="get" target="_blank">
            <label>기준 주의 월요일 날짜 (YYYY-MM-DD): </label>
            <input type="text" name="base_monday" value="2025-03-03" />
            <button type="submit">ICS 파일 다운로드</button>
        </form>

        <br><a href="/">메인으로 돌아가기</a>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


# ====================================================
# 8. 대여 가능 시간 ICS (Google Calendar용)
# ====================================================
@router.get("/free-slots-ics")
async def get_free_slots_ics(base_monday: str = "2025-03-03"):
    """
    대여 가능 시간 슬롯을 Google Calendar용 ICS 파일로 다운로드

    - base_monday: 기준 주의 월요일 날짜 (YYYY-MM-DD)
    - 브라우저에서 자동으로 .ics 파일 다운로드
    """
    if state.result_df is None or state.result_df.empty:
        raise HTTPException(status_code=400, detail="먼저 자동 배정을 실행해 주세요.")

    _, free_slots = compute_vacancy_stats(state.result_df)

    try:
        ics_content, filename = generate_ics_from_free_slots(free_slots, base_monday)
    except ValueError:
        raise HTTPException(status_code=400, detail="base_monday 형식은 YYYY-MM-DD 이어야 합니다.")

    return StreamingResponse(
        StringIO(ics_content),
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
