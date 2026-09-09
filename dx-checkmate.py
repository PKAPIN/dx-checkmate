import streamlit as st
import pandas as pd
import requests
import random
import time
import json
import os
import threading

st.set_page_config(page_title="DX-CheckMate", page_icon=":material/fact_check:", layout="wide")

# 백그라운드 작업 상태 공유용 전역 변수
if "GLOBAL_JOBS" not in globals():
    GLOBAL_JOBS = {}

SHEET_ID = "1ws9JTAdRXwbp--NhrjWwelNorSTv1_LIJW7DijUtJLU"
SHEET_WEB_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
ADMIN_WEB_URL = "https://cms.dxcheck.kr/admin/event"
API_URL = "https://api.dxcheck.kr/api/v1/attendance"

# 1, 2, 3번 탭 GID 매핑
TAB_CONFIG = {
    "출석체크_1": "1678272994",
    "출석체크_2": "1005009417",
    "출석체크_3": "508140271"
}

col_title, col_guide = st.columns([1.5, 1])

with col_title:
    st.title(":material/how_to_reg: DX-CheckMate 멀티 자동 출석")
    st.caption("각 탭별 작업이 백그라운드 스레드로 독립 실행되어 탭을 이동해도 끊기지 않습니다.")

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.link_button("출석체크 구글 시트 바로가기", SHEET_WEB_URL, icon=":material/table_view:", use_container_width=True)
    with btn_col2:
        st.link_button("CMS 프로그램 출결관리 바로가기", ADMIN_WEB_URL, icon=":material/admin_panel_settings:", use_container_width=True)

with col_guide:
    st.info("""
    **💡 멀티 세션 사용 가이드**
    1. 상단 **[출석체크_1 / 2 / 3]** 탭을 클릭하여 해당 차수로 이동합니다.
    2. 각각의 탭에서 독립적으로 **[자동 출석체크 시작하기]**를 실행할 수 있습니다.
    3. 다른 탭으로 이동하거나 화면을 전환해도 실행 중인 작업은 백그라운드에서 계속 진행됩니다.
    """)

st.divider()

def generate_decay_delays(num_people, mode):
    if num_people == 0:
        return []

    if "1초 이내" in mode:
        return [0] * num_people

    if "1분 이내" in mode:
        total_duration = random.uniform(30, 50)
    elif "2분 초밀집" in mode:
        total_duration = random.uniform(90, 120)
    elif "4분 현장 표준" in mode:
        total_duration = random.uniform(180, 240)
    elif "6분 완만 분산" in mode:
        total_duration = random.uniform(300, 360)
    else:
        return [0] * num_people

    count_peak = int(num_people * 0.60)
    count_mid = int(num_people * 0.30)
    count_tail = num_people - count_peak - count_mid

    t1 = total_duration * 0.40
    t2 = total_duration * 0.80

    timestamps = []

    for _ in range(count_peak):
        timestamps.append(random.uniform(0, t1))

    for _ in range(count_mid):
        timestamps.append(random.uniform(t1, t2))

    for _ in range(count_tail):
        timestamps.append(random.uniform(t2, total_duration))

    timestamps.sort()
    delays = []
    prev_t = 0
    for t in timestamps:
        delays.append(t - prev_t)
        prev_t = t

    return delays

# --- 백그라운드 비동기 작업 실행 함수 ---
def run_attendance_worker(gid, shuffled_df, delays, exec_mode, event_code):
    job = GLOBAL_JOBS[gid]
    job["status"] = "running"
    
    total_count = len(shuffled_df)
    total_delay_sum = sum(delays)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://dxcheck.kr/",
        "Origin": "https://dxcheck.kr"
    })

    start_time = time.time()

    for idx in range(total_count):
        job["current_index"] = idx
        row = shuffled_df.iloc[idx]
        wait_time = delays[idx]

        name = str(row.get('이름', '')).strip()
        school = str(row.get('학교명', '')).strip()
        phone_last4 = str(row.get('전화번호 뒤 4자리', '')).strip().replace('.0', '')
        role = str(row.get('구분(교/직원)', '')).strip()
        lunch_str = str(row.get('점심식사 참석여부', '')).strip().upper()
        dinner_str = str(row.get('저녁식사 참석여부', '')).strip().upper()

        sec = int(time.time() - start_time)
        resp_time_str = f"{sec // 60:02d}분 {sec % 60:02d}초"

        if not school or school.lower() == 'nan':
            job["result_logs"].append({
                "이름": name if name else f"{idx+1}번 행",
                "학교명": "미기입",
                "응답 시간": resp_time_str,
                "처리 결과": "실패",
                "상세 사유": "학교명 누락"
            })
            continue

        if not name or name.lower() == 'nan':
            job["result_logs"].append({
                "이름": f"{idx+1}번 행",
                "학교명": school,
                "응답 시간": resp_time_str,
                "처리 결과": "실패",
                "상세 사유": "이름 누락"
            })
            continue

        # 대기 루프 중 상태 업데이트
        if wait_time >= 0.1:
            step = 0.1
            for _ in range(int(wait_time / step)):
                elapsed_total = time.time() - start_time
                remaining = max(0, round(total_delay_sum - elapsed_total, 1))
                job["current_msg"] = f"⏳ [{idx+1}/{total_count}] ({school}) {name} 선생님 입력 중... (예상 전체 작업시간 : {remaining}초 남음)"
                time.sleep(step)
        else:
            elapsed_total = time.time() - start_time
            remaining = max(0, round(total_delay_sum - elapsed_total, 1))
            job["current_msg"] = f"⏳ [{idx+1}/{total_count}] ({school}) {name} 선생님 입력 중... (예상 전체 작업시간 : {remaining}초 남음)"

        payload = {
            "code": event_code,
            "name": name,
            "phone": phone_last4,
            "type": role,
            "department": school,
            "is_lunch": 1 if lunch_str in ['O', '1', 'TRUE', '참석'] else 0,
            "is_dinner": 1 if dinner_str in ['O', '1', 'TRUE', '참석'] else 0
        }

        try:
            response = session.post(API_URL, data=payload, timeout=10)
            if response.status_code == 200:
                job["success_count"] += 1
                job["result_logs"].append({
                    "이름": name,
                    "학교명": school,
                    "응답 시간": resp_time_str,
                    "처리 결과": "성공",
                    "상세 사유": "출석 기입 완료"
                })
            else:
                job["result_logs"].append({
                    "이름": name,
                    "학교명": school,
                    "응답 시간": resp_time_str,
                    "처리 결과": "실패",
                    "상세 사유": f"서버 응답 에러 ({response.status_code})"
                })
        except Exception:
            job["result_logs"].append({
                "이름": name,
                "학교명": school,
                "응답 시간": resp_time_str,
                "처리 결과": "실패",
                "상세 사유": "통신 오류"
            })

    job["status"] = "completed"
    job["current_msg"] = "✅ 출석 처리가 완료되었습니다."

# --- 상단 탭 생성 ---
tab_list = st.tabs(list(TAB_CONFIG.keys()))

for tab_ui, (tab_name, current_gid) in zip(tab_list, TAB_CONFIG.items()):
    with tab_ui:
        CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={current_gid}"

        # 해당 GID의 전역 작업 객체 초기화
        if current_gid not in GLOBAL_JOBS:
            GLOBAL_JOBS[current_gid] = {
                "status": "idle",
                "current_index": 0,
                "current_msg": "",
                "result_logs": [],
                "success_count": 0,
                "thread": None
            }

        job = GLOBAL_JOBS[current_gid]

        try:
            df_raw = pd.read_csv(CSV_URL, header=None)
            form_url = ""
            for cell in df_raw.iloc[1].dropna():
                cell_str = str(cell).strip()
                if cell_str.startswith("http"):
                    form_url = cell_str
                    break
                    
            event_code = form_url.rstrip('/').split('/')[-1] if form_url else ""
            df = pd.read_csv(CSV_URL, header=2)
            
            st.success(f"[{tab_name}] 실시간 출석 URL 인식 완료: {form_url}", icon=":material/link:")
            
            target_df = df[df['출석하기'].astype(str).str.upper().isin(['TRUE', 'O', 'V', '1'])]
            
            st.write(f":material/list_alt: [{tab_name}] 현재 출석체크 대상자: **총 {len(target_df)}명**")
            
            preview_cols = ['이름', '학교명', '전화번호 뒤 4자리', '구분(교/직원)', '점심식사 참석여부', '저녁식사 참석여부']
            st.dataframe(target_df[[col for col in preview_cols if col in target_df.columns]], use_container_width=True)

            st.subheader(":material/tune: 출석 패턴 모드 선택")
            
            exec_mode = st.radio(
                f"[{tab_name}] 실행 모드를 선택하세요.",
                [
                    "⚡ [1분 이내 초고속 모드] (1분 이내 완료 / 긴급 출석 처리용)",
                    "🔥 [2분 초밀집 모드] (0 - 2분 완료 / 소규모 10 - 20명용)",
                    "🕵️ [4분 현장 표준 모드] (2 - 4분 완료 / 중규모 30 - 50명용)",
                    "🐢 [6분 완만 분산 모드] (4 - 6분 완료 / 대규모 60명 이상용)",
                    "🚀 [고속 즉시 모드] (1초 이내 완료 / 시스템 테스트용)"
                ],
                index=2,
                key=f"mode_{current_gid}"
            )

            col_btn1, col_btn2 = st.columns([1, 2])
            
            with col_btn1:
                if job["status"] != "running":
                    if st.button(f"🚀 [{tab_name}] 자동 출석체크 시작", type="primary", key=f"btn_start_{current_gid}"):
                        shuffled_df = target_df.sample(frac=1).reset_index(drop=True)
                        delays = generate_decay_delays(len(target_df), exec_mode)
                        
                        job["status"] = "running"
                        job["result_logs"] = []
                        job["success_count"] = 0
                        job["current_index"] = 0
                        
                        # 백그라운드 스레드로 작업 생성 및 시작
                        t = threading.Thread(
                            target=run_attendance_worker,
                            args=(current_gid, shuffled_df, delays, exec_mode, event_code)
                        )
                        job["thread"] = t
                        t.start()
                        st.rerun()
                else:
                    st.button("⚙️ 작업 실행 중...", disabled=True, key=f"btn_dis_{current_gid}")

            with col_btn2:
                if st.button("🔄 화면 새로고침 (진행 상황 업데이트)", key=f"btn_refresh_{current_gid}"):
                    st.rerun()

            # 작업 진행 상황 표시 영역
            if job["status"] in ["running", "completed"]:
                st.divider()
                st.info(job["current_msg"], icon=":material/sync:" if job["status"] == "running" else ":material/check_circle:")
                
                total_len = len(target_df)
                if total_len > 0:
                    prog_val = min(1.0, (job["current_index"] + 1) / total_len) if job["status"] == "running" else 1.0
                    st.progress(prog_val)

                if len(job["result_logs"]) > 0:
                    st.subheader(":material/grading: 작업 상세 결과")
                    result_df = pd.DataFrame(job["result_logs"])
                    st.dataframe(result_df, hide_index=True, use_container_width=True)

        except Exception as e:
            st.error(f"[{tab_name}] 구글 시트를 읽어오는 중 오류가 발생했습니다: {e}", icon=":material/error:")
