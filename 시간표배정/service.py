"""
service.py

- 비즈니스 로직 모듈
- 주요 기능:
  1) assign_timetable : CSV → 강의실/시간 자동 배정
  2) compute_vacancy_stats : 배정 결과 → 공실/대여 가능 시간 계산
  3) generate_ics_from_free_slots : 대여 가능 시간을 ICS 문자열로 변환
"""

from typing import Dict, List, Tuple
import pandas as pd
import random
import re
from datetime import datetime, timedelta


# =======================================
# 기본 설정값 (강의실 / 요일 / 시간블록)
# =======================================
ROOMS_MAIN = ["1215", "1216", "1217", "1418"]   # 기본 강의실 목록
EXTRA_ROOM_NAME = "외부강의실1"                 # 필요 시 추가로 사용하는 외부 강의실

DAYS = ["월", "화", "수", "목", "금"]            # 수업 요일

# 3교시씩 묶인 시간 블록
# 예: (1,3) → 1~3교시, (4,6) → 4~6교시
BLOCKS: List[Tuple[int, int]] = [
    (1, 3),   # 1~3교시
    (4, 6),   # 4~6교시
    (7, 9),   # 7~9교시
]


# =====================================================
# 1. 시간표 자동 배정
# =====================================================
def assign_timetable(
    df: pd.DataFrame,
    preferred_day_dict: Dict[str, List[str]],
) -> pd.DataFrame:
    """
    CSV DataFrame을 입력받아 자동으로 시간표(배정 결과 DataFrame)를 생성

    - 실습/이론 분리 후 실습을 먼저 배정
    - 교수 선호 요일(웹 + CSV) 반영
    - 강의실/교수 중복을 방지하며 (요일 → 강의실 → 시간블록) 순서로 배정
    """
    rooms = ROOMS_MAIN.copy()
    schedule = {}        # (day, period, room) -> (subj, prof)
    prof_schedule = {}   # (prof, day, period) -> True (교수 스케줄 중복 방지)
    assigned_rows = []

    # ---------------------------------------
    # 1) 실습/이론 과목 분리 후 순서 섞기
    # ---------------------------------------
    if "강의유형구분" in df.columns:
        # "실습"인 과목 우선 배정
        pr_mask = df["강의유형구분"].astype(str).str.strip() == "실습"
        df_prac = df[pr_mask].sample(frac=1)
        df_theo = df[~pr_mask].sample(frac=1)
        df_sorted = pd.concat([df_prac, df_theo]).reset_index(drop=True)
    else:
        df_sorted = df.sample(frac=1).reset_index(drop=True)

    # ---------------------------------------
    # 2) 각 과목을 한 개씩 배정 시도
    # ---------------------------------------
    for _, row in df_sorted.iterrows():
        subj = str(row.get("교과목명", "")).strip()
        prof = str(row.get("강좌담당교수", row.get("강좌대표교수", ""))).strip()

        # ---------------------------
        # (a) 실습 여부 판단
        # ---------------------------
        is_prac = False
        if "강의유형구분" in df.columns:
            is_prac = str(row["강의유형구분"]).strip() == "실습"

        # 실습이면 실습실 우선, 아니면 일반 강의실 우선
        if is_prac:
            preferred_rooms = ["1216", "1217"]  # 실습실
        else:
            preferred_rooms = ["1215", "1418"]  # 이론 강의실

        other_rooms = [r for r in rooms if r not in preferred_rooms]
        room_order = preferred_rooms + other_rooms

        # ---------------------------
        # (b) 교수 선호요일 결정
        #     1순위: 웹에서 설정한 값(state.preferred_days)
        #     2순위: CSV의 '선호요일' 컬럼
        # ---------------------------
        gui_pref = preferred_day_dict.get(prof, None)
        if gui_pref:
            preferred_days = gui_pref[:]
        else:
            preferred_days = []
            if "선호요일" in df.columns:
                raw = str(row.get("선호요일", "")).strip()
                if raw:
                    tokens = re.split(r"[,\s/]+", raw)
                    preferred_days = [t for t in tokens if t in DAYS]

        # 요일 우선순위 리스트 생성
        if preferred_days:
            pref = preferred_days[:]
            random.shuffle(pref)
            other = [d for d in DAYS if d not in preferred_days]
            random.shuffle(other)
            day_order_list = pref + other
        else:
            day_order_list = DAYS[:]
            random.shuffle(day_order_list)

        placed = False  # 배정 성공 여부

        # 외부강의실을 rooms 및 room_order에 포함
        if EXTRA_ROOM_NAME not in rooms:
            rooms.append(EXTRA_ROOM_NAME)
        if EXTRA_ROOM_NAME not in room_order:
            room_order.append(EXTRA_ROOM_NAME)

        # ---------------------------------------
        # 3) (요일 → 강의실 → 시간블록) 순으로 빈자리 탐색
        # ---------------------------------------
        for day in day_order_list:
            if placed:
                break

            room_list = room_order[:]
            random.shuffle(room_list)

            for room in room_list:
                if placed:
                    break

                blocks_random = BLOCKS[:]
                random.shuffle(blocks_random)

                for (start, end) in blocks_random:
                    periods = list(range(start, end + 1))
                    conflict = False

                    # ---------------------------
                    # (1) 강의실/교수 중복 체크
                    # ---------------------------
                    for p in periods:
                        # 강의실 중복
                        if (day, p, room) in schedule:
                            conflict = True
                            break
                        # 교수 스케줄 중복
                        if (prof, day, p) in prof_schedule:
                            conflict = True
                            break

                    if conflict:
                        continue

                    # ---------------------------
                    # (2) 해당 블록에 실제 배정
                    # ---------------------------
                    for p in periods:
                        schedule[(day, p, room)] = (subj, prof)
                        prof_schedule[(prof, day, p)] = True

                    assigned_rows.append([subj, prof, day, start, end, room])
                    placed = True
                    break

        # ---------------------------------------
        # 4) 어떠한 블록에도 배정되지 못한 경우
        # ---------------------------------------
        if not placed:
            print(f"[WARN] '{subj}' 과목 배정 불가 (공간/조건 부족)")

    # ---------------------------------------
    # 5) 결과 DataFrame 생성 및 정렬
    # ---------------------------------------
    result_df = pd.DataFrame(
        assigned_rows,
        columns=["교과목명", "담당교수", "요일", "시작교시", "종료교시", "배정강의실"],
    )

    if result_df.empty:
        return result_df

    # 요일 → 강의실 → 시작교시 순으로 정렬
    day_map = {d: i for i, d in enumerate(DAYS)}
    room_map = {r: i for i, r in enumerate(ROOMS_MAIN + [EXTRA_ROOM_NAME])}

    result_df["d_order"] = result_df["요일"].map(day_map)
    result_df["r_order"] = result_df["배정강의실"].map(room_map)

    result_df = result_df.sort_values(
        by=["d_order", "r_order", "시작교시"]
    ).drop(columns=["d_order", "r_order"])

    return result_df


# =====================================================
# 2. 공실 분석 및 대여 가능한 슬롯 계산
# =====================================================
def compute_vacancy_stats(result_df: pd.DataFrame):
    """
    자동 배정 결과(result_df)를 받아:

    - 강의실별 공실률(room_stats)
    - 요일/강의실/블록 단위의 대여 가능 시간(free_slots)

    을 계산하여 반환
    """
    rooms_all = ROOMS_MAIN + [EXTRA_ROOM_NAME]

    # ---------------------------------------
    # 1) 이미 배정된 블록 수집
    # ---------------------------------------
    used_slots = set()
    for _, row in result_df.iterrows():
        used_slots.add(
            (row["요일"], row["배정강의실"], int(row["시작교시"]), int(row["종료교시"]))
        )

    room_stats = []
    free_slots = []

    used_counts = result_df["배정강의실"].value_counts().to_dict()
    total_slots_per_room = len(DAYS) * len(BLOCKS)

    # ---------------------------------------
    # 2) 강의실별 공실률 계산
    # ---------------------------------------
    for room in rooms_all:
        used = used_counts.get(room, 0)
        free = total_slots_per_room - used
        free_rate = (free / total_slots_per_room * 100.0) if total_slots_per_room > 0 else 0.0

        room_stats.append(
            {
                "room": room,
                "total": total_slots_per_room,
                "used": used,
                "free": free,
                "free_rate": free_rate,
            }
        )

    # ---------------------------------------
    # 3) 대여 가능 슬롯 리스트 생성
    #    (요일, 강의실, 시간블록 단위)
    # ---------------------------------------
    for day in DAYS:
        for room in rooms_all:
            for (start, end) in BLOCKS:
                key = (day, room, start, end)
                if key not in used_slots:
                    free_slots.append(
                        {"day": day, "room": room, "start": start, "end": end}
                    )

    return room_stats, free_slots


# =====================================================
# 3. ICS 생성 (Google Calendar용)
# =====================================================
def generate_ics_from_free_slots(
    free_slots: List[Dict],
    base_monday: str = "2025-03-03",
) -> Tuple[str, str]:
    """
    대여 가능 슬롯(free_slots)을 기반으로 Google Calendar용 ICS 문자열과
    저장 파일명(filename)을 생성해서 반환.

    base_monday : 기준이 되는 "월요일" 날짜 (YYYY-MM-DD 형식)
    """
    # 1) 기준 월요일 날짜 파싱
    try:
        base_date = datetime.strptime(base_monday, "%Y-%m-%d")
    except ValueError:
        # 형식이 잘못된 경우 호출 측에서 HTTPException 처리
        raise ValueError("base_monday 형식은 YYYY-MM-DD 이어야 합니다.")

    weekday_map = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4}

    lines = []
    lines.append("BEGIN:VCALENDAR")
    lines.append("VERSION:2.0")
    lines.append("PRODID:-//ClassRoom Scheduler//KO")

    # 2) 각 슬롯을 VEVENT로 변환
    for i, slot in enumerate(free_slots):
        day = slot["day"]
        room = slot["room"]
        start_p = int(slot["start"])
        end_p = int(slot["end"])

        if day not in weekday_map:
            continue

        day_offset = weekday_map[day]
        date = base_date + timedelta(days=day_offset)

        # 1교시 = 9시, 2교시 = 10시 ... 으로 가정
        start_hour = 8 + start_p   # 1→9시, 4→12시
        end_hour = 9 + end_p       # 3→12시, 6→15시, 9→18시

        dt_start = date.replace(hour=start_hour, minute=0, second=0)
        dt_end = date.replace(hour=end_hour, minute=0, second=0)

        dt_start_str = dt_start.strftime("%Y%m%dT%H%M%S")
        dt_end_str = dt_end.strftime("%Y%m%dT%H%M%S")
        uid = f"{i}-{dt_start_str}-{room}@class-scheduler"

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{uid}")
        lines.append(f"SUMMARY:[대여가능] {room}")
        lines.append(f"DTSTART:{dt_start_str}")
        lines.append(f"DTEND:{dt_end_str}")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    ics_content = "\r\n".join(lines)
    filename = f"free_slots_{base_monday}.ics"
    return ics_content, filename
