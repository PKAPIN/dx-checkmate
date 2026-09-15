import streamlit as st
import pandas as pd
import requests
import random
import time
import json
import os
import uuid

st.set_page_config(page_title="DX-CheckMate 자동 출석", page_icon=":material/fact_check:", layout="wide")

# 📌 1. 개발자 세션 상태 관리
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "is_dev" not in st.session_state:
    st.session_state.is_dev = False

# 📌 2. 사이드바 암호 입력 영역 (개발자 모드 전환용)
with st.sidebar:
    st.title("⚙️ 시스템 설정")
    if not st.session_state.authenticated:
        st.subheader("🔒 개발자 인증")
        dev_pass = st.text_input("보안/개발자 암호", type="password", placeholder="암호 입력 후 엔터")
        if dev_pass == "edunlab":
            st.session_state.authenticated = True
            st.session_state.is_dev = False
            st.success("일반 사용자 인증 완료")
            st.rerun()
        elif dev_pass == "coldblend":
            st.session_state.authenticated = True
            st.session_state.is_dev = True
            st.success("개발자(Dev) 모드 인증 완료")
            st.rerun()
        elif dev_pass != "":
            st.error("암호가 올바르지 않습니다.")
    else:
        if st.session_state.is_dev:
            st.success("👨‍💻 개발자 권한 활성화됨")
            if st.button("로그아웃 / 암호 재설정"):
                st.session_state.authenticated = False
                st.session_state.is_dev = False
                st.rerun()
        else:
            st.info("👤 일반 사용자 모드")

if st.session_state.is_dev:
    st.toast("👨‍💻 Developer Mode 활성화 상태", icon="🛠️")

# ---------------- 메인 자동 출석 시스템 ----------------

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "selected_tab" not in st.session_state:
    st.session_state.selected_tab = "출석체크_1"
if "completed_results" not in st.session_state:
    st.session_state.completed_results = None

SHEET_ID = "1ws9JTAdRXwbp--NhrjWwelNorSTv1_LIJW7DijUtJLU"
SHEET_WEB_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid=1678272994#gid=1678272994"
ADMIN_WEB_URL = "https://cms.dxcheck.kr/"
API_URL = "https://api.dxcheck.kr/api/v1/attendance"

TAB_CONFIG = {
    "출석체크_1": "1678272994",
    "출석체크_2": "211467376",
    "출석체크_3": "971906306"
}

col_title, col_guide = st.columns([1.5, 1])

with col_title:
    st.title(":material/how_to_reg: DX-CheckMate 자동 출석")
    st.caption("구글 스프레드시트 데이터를 읽어와 백엔드 API로 현장 패턴에 맞게 자동 출석을 제출합니다.")

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.link_button("출석체크 구글 시트 바로가기", SHEET_WEB_URL, icon=":material/table_view:", use_container_width=True)
    with btn_col2:
        st.link_button("CMS 프로그램 출결관리 바로가기", ADMIN_WEB_URL, icon=":material/admin_panel_settings:", use_container_width=True)

with col_guide:
    st.info("""
    **💡 사용 방법 가이드**
    1. **[출석체크 구글 시트 바로가기]** 링크에 접속한 후 작업할 출석시트(1,2,3)를 선택하고 학교, 과정명, 회차를 선택합니다.
    2. 5행 식사여부는 상황에 맞춰 **[점심식사]** / **[저녁식사]** 토글로 변경해 줍니다.
    3. 이번에 출석을 진행할 실시간 출석 URL 주소를 'url 입력'란에 붙여넣습니다.
    4. 이번에 출석을 진행할 인원들의 '출석하기' 열 체크박스를 선택합니다.
    5. 본 탭(웹)으로 돌아와 진행할 시트 선택 및 실행모드 선택 후 **[자동 출석체크 시작하기]** 버튼을 클릭합니다.
    6. 제출이 완료되면 **[CMS 프로그램 출결관리]**에서 최종 결과를 확인합니다.
    
    ⚠️ *(꼭 확인 후 다음 프로세스 진행하십시오) 실제 출석 데이터에 반영됩니다.*
    """)

st.divider()

if not st.session_state.is_running:
    selected_tab_name = st.radio(
        "📌 진행할 출석 시트 탭을 선택하세요",
        options=list(TAB_CONFIG.keys()),
        index=list(TAB_CONFIG.keys()).index(st.session_state.selected_tab),
        horizontal=True
    )
    st.session_state.selected_tab = selected_tab_name
else:
    selected_tab_name = st.session_state.selected_tab
    st.warning(f"🔒 **현재 [{selected_tab_name}] 작업이 진행 중입니다.** (작업이 끝날 때까지 시트 변경 상자가 숨겨집니다.)", icon=":material/lock:")

current_gid = TAB_CONFIG[selected_tab_name]
CHECKPOINT_FILE = f".checkpoint_{st.session_state.session_id}_{current_gid}.json"

def generate_decay_delays(num_people, mode):
    if num_people == 0:
        return []

    if "1초 이내" in mode or "고속 즉시" in mode:
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

    early_ratio = random.uniform(0.04, 0.08)
    peak_ratio = random.uniform(0.60, 0.70)
    
    count_early = max(1, int(num_people * early_ratio))
    count_peak = int(num_people * peak_ratio)
    count_tail = num_people - count_early - count_peak

    t_early = total_duration * random.uniform(0.05, 0.10)
    t_peak = total_duration * random.uniform(0.25, 0.35)

    timestamps = []
    for _ in range(count_early):
        timestamps.append(random.uniform(0, t_early))
        
    for _ in range(count_peak):
        timestamps.append(random.uniform(t_early, t_peak))

    for _ in range(count_tail):
        timestamps.append(random.uniform(t_peak, total_duration))

    timestamps.sort()

    delays = []
    prev_t = 0
    for t in timestamps:
        delays.append(t - prev_t)
        prev_t = t

    return delays

def save_checkpoint(current_index, shuffled_data, delays, result_logs, success_count, event_code, elapsed_base):
    checkpoint_data = {
        "current_index": current_index,
        "shuffled_data": shuffled_data,
        "delays": delays,
        "result_logs": result_logs,
        "success_count": success_count,
        "event_code": event_code,
        "elapsed_base": elapsed_base
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def clear_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={current_gid}"

try:
    df_raw = pd.read_csv(CSV_URL, header=None, dtype=str)
    
    default_school = ""
    if len(df_raw) > 1 and pd.notna(df_raw.iloc[1, 1]):
        default_school = str(df_raw.iloc[1, 1]).strip()

    form_url = ""
    if len(df_raw) > 3:
        for cell in df_raw.iloc[3].dropna():
            cell_str = str(cell).strip()
            if cell_str.startswith("http") and "docs.google.com" not in cell_str:
                form_url = cell_str
                break
            
    event_code = form_url.rstrip('/').split('/')[-1] if form_url else ""
    df = pd.read_csv(CSV_URL, header=4, dtype=str)
    
    meal_col = [col for col in df.columns if '식사' in str(col)]
    meal_header_name = meal_col[0] if meal_col else '점심식사'
    is_lunch_mode = '점심' in meal_header_name

    if form_url:
        st.success(f"[{selected_tab_name}] 실시간 출석 URL 인식 완료: {form_url}", icon=":material/link:")
    else:
        st.error("⚠️ URL 주소가 입력되지 않았습니다.", icon=":material/link_off:")
    
    target_df = df[df['출석하기'].astype(str).str.upper().isin(['TRUE', 'O', 'V', '1'])].copy()
    
    target_df['전화번호 뒤 4자리'] = target_df['전화번호 뒤 4자리'].astype(str).str.replace('.0', '', regex=False).str.strip().str.zfill(4)
    target_df['학교명'] = target_df['학교명'].apply(lambda x: default_school if pd.isna(x) or str(x).strip() in ['', 'nan', 'None'] else str(x).strip())
    
    st.write(f":material/list_alt: [{selected_tab_name}] 현재 출석체크 대상자: **총 {len(target_df)}명**")
    
    preview_cols = ['이름', '학교명', '전화번호 뒤 4자리', '구분(교/직원)', meal_header_name]
    st.dataframe(target_df[[col for col in preview_cols if col in target_df.columns]], use_container_width=True)

    st.subheader(":material/tune: 출석 패턴 모드 선택")
    
    exec_mode = st.radio(
        "연수 인원 및 현장 상황에 맞는 모드를 선택하세요.",
        [
            ":material/bolt: [1분 이내 초고속 모드] (1분 이내 완료 / 긴급 출석 처리용)",
            ":material/local_fire_department: [2분 초밀집 모드] (0 - 2분 완료 / 소규모 10 - 20명용)",
            ":material/verified_user: [4분 현장 표준 모드] (2 - 4분 완료 / 중규모 30 - 50명용)",
            ":material/schedule: [6분 완만 분산 모드] (4 - 6분 완료 / 대규모 60명 이상용)",
            ":material/rocket_launch: [고속 즉시 모드] (1초 이내 완료 / 시스템 테스트용)"
        ],
        index=2,
        disabled=st.session_state.is_running
    )

    with st.expander("ℹ️ 자동 출석 시스템 세부 작동 원리 (Security & Pattern Obfuscation)"):
        st.markdown("""
        본 시스템은 백엔드 서버의 매크로 및 어뷰징 탐지 알고리즘(Anti-Bot Detection)을 무력화하기 위해, **현장 QR 오프라인 출석 시 발생하는 생체 인지 반응 및 동시 다발적 접속 행동(S-Curve Burst Traffic)**을 수학적 난수 알고리즘으로 재현합니다.

        **1. 명단 순서 비선형 무작위화 (Non-linear Random Shuffling)**
        * 정적 스프레드시트의 인덱스 순서대로 데이터를 순차 전송할 경우 자동화 스크립트로 즉시 식별됩니다. 이를 방지하기 위해 제출 대상자의 순서를 제비뽑기 알고리즘으로 비선형 무작위 셔플링하여 수신 서버에 전송합니다.

        **2. 인간 인지 반응 지연 및 동시 피크 모사 (Cognitive Delay & S-Curve Spike)**
        * QR 코드 투사 즉시 접속하는 기계적 0초 제출을 배제하고, **초기 탐색 지연(Phase 1: 5%) -> 주 폭주 피크(Phase 2: 65%) -> 잔여 분산(Phase 3: 30%)**의 3단계 오프라인 S곡선 트래픽 곡선을 생성합니다.

        **3. 전체 사이클 및 분기점 난수화 (Dynamic Total Duration & Threshold)**
        * 모드별 **전체 소요 시간(Total Duration)**을 매 실행마다 무작위 산출하고, 구간별 시간 분기점 및 비중을 난수로 재계산하여 정적 매크로 패턴 분석을 완전히 무력화합니다.
        """)

    saved_cp = load_checkpoint()
    
    if saved_cp and saved_cp.get("event_code") == event_code and event_code:
        processed_num = saved_cp.get("current_index", 0)
        total_num = len(saved_cp.get("shuffled_data", []))
        st.warning(f"⚠️ [{selected_tab_name}] 이전 작업이 중단된 기록이 있습니다. ({processed_num}/{total_num}명 진행 완료)", icon=":material/warning:")
        
        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            resume_btn = st.button("🚀 중단된 작업 이어서 시작하기", type="primary")
        with btn_col2:
            reset_btn = st.button("🔄 기록 지우고 처음부터 새로 시작", type="secondary")
            
        if reset_btn:
            clear_checkpoint()
            st.session_state.is_running = False
            st.session_state.completed_results = None
            st.rerun()
    else:
        resume_btn = False
        start_btn = st.button("자동 출석체크 시작하기", type="primary", disabled=st.session_state.is_running or not form_url)

    if (not saved_cp and start_btn) or (saved_cp and resume_btn):
        if not form_url:
            st.error("⚠️ URL 주소가 입력되지 않았습니다.", icon=":material/link_off:")
        else:
            st.session_state.is_running = True
            st.session_state.completed_results = None
            st.rerun()

    if st.session_state.is_running:
        progress_bar = st.progress(0)
        log_area = st.empty()

        if saved_cp:
            current_index = saved_cp["current_index"]
            shuffled_data = saved_cp["shuffled_data"]
            delays = saved_cp["delays"]
            result_logs = saved_cp["result_logs"]
            success_count = saved_cp["success_count"]
            elapsed_base = saved_cp.get("elapsed_base", 0)
            shuffled_df = pd.DataFrame(shuffled_data)
        else:
            clear_checkpoint()
            current_index = 0
            shuffled_df = target_df.sample(frac=1).reset_index(drop=True)
            shuffled_data = shuffled_df.to_dict(orient="records")
            delays = generate_decay_delays(len(target_df), exec_mode)
            result_logs = []
            success_count = 0
            elapsed_base = 0

        total_count = len(shuffled_df)
        remaining_delays = delays[current_index:]
        total_delay_sum = sum(remaining_delays)

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://dxcheck.kr/",
            "Origin": "https://dxcheck.kr"
        })

        start_time = time.time() - elapsed_base

        try:
            for idx in range(current_index, total_count):
                row = shuffled_df.iloc[idx]
                wait_time = delays[idx]

                name = str(row.get('이름', '')).strip()
                
                school = str(row.get('학교명', '')).strip()
                if not school or school.lower() in ['nan', 'none', '']:
                    school = default_school

                phone_raw = str(row.get('전화번호 뒤 4자리', '')).strip().replace('.0', '')
                phone_last4 = phone_raw.zfill(4) if phone_raw.isdigit() else phone_raw

                role = str(row.get('구분(교/직원)', '')).strip()
                
                meal_status = str(row.get(meal_header_name, '')).strip().upper()
                is_attending = meal_status in ['참석', 'O', '1', 'TRUE', 'V']
                
                is_lunch = 1 if (is_lunch_mode and is_attending) else 0
                is_dinner = 1 if ((not is_lunch_mode) and is_attending) else 0

                def get_formatted_time():
                    sec = int(time.time() - start_time)
                    return f"{sec // 60:02d}분 {sec % 60:02d}초"

                if not school or school.lower() == 'nan':
                    result_logs.append({
                        "이름": name if name else f"{idx+1}번 행",
                        "학교명": "미기입",
                        "응답 시간": get_formatted_time(),
                        "처리 결과": "실패",
                        "상세 사유": "학교명 누락"
                    })
                    current_elapsed = time.time() - start_time
                    save_checkpoint(idx + 1, shuffled_data, delays, result_logs, success_count, event_code, current_elapsed)
                    progress_bar.progress((idx + 1) / total_count)
                    continue

                if not name or name.lower() == 'nan':
                    result_logs.append({
                        "이름": f"{idx+1}번 행",
                        "학교명": school,
                        "응답 시간": get_formatted_time(),
                        "처리 결과": "실패",
                        "상세 사유": "이름 누락"
                    })
                    current_elapsed = time.time() - start_time
                    save_checkpoint(idx + 1, shuffled_data, delays, result_logs, success_count, event_code, current_elapsed)
                    progress_bar.progress((idx + 1) / total_count)
                    continue

                if wait_time >= 0.1:
                    step = 0.1
                    for elapsed in range(int(wait_time / step)):
                        elapsed_total = time.time() - start_time
                        remaining_total = max(0, round(total_delay_sum - (elapsed_total - elapsed_base), 1))
                        log_area.text(f"⏳ [{idx+1}/{total_count}] ({school}) {name} 선생님 입력 중... (예상 전체 작업시간 : {remaining_total}초 남음)")
                        time.sleep(step)
                else:
                    elapsed_total = time.time() - start_time
                    remaining_total = max(0, round(total_delay_sum - (elapsed_total - elapsed_base), 1))
                    log_area.text(f"⏳ [{idx+1}/{total_count}] ({school}) {name} 선생님 입력 중... (예상 전체 작업시간 : {remaining_total}초 남음)")

                payload = {
                    "code": event_code,
                    "name": name,
                    "phone": phone_last4,
                    "type": role,
                    "department": school,
                    "is_lunch": is_lunch,
                    "is_dinner": is_dinner
                }

                resp_time_str = get_formatted_time()

                try:
                    response = session.post(API_URL, data=payload, timeout=10)
                    if response.status_code == 200:
                        success_count += 1
                        result_logs.append({
                            "이름": name,
                            "학교명": school,
                            "응답 시간": resp_time_str,
                            "처리 결과": "성공",
                            "상세 사유": "출석 기입 완료"
                        })
                    else:
                        result_logs.append({
                            "이름": name,
                            "학교명": school,
                            "응답 시간": resp_time_str,
                            "처리 결과": "실패",
                            "상세 사유": f"서버 응답 에러 ({response.status_code})"
                        })
                except Exception as e:
                    result_logs.append({
                        "이름": name,
                        "학교명": school,
                        "응답 시간": resp_time_str,
                        "처리 결과": "실패",
                        "상세 사유": f"통신 오류"
                    })

                current_elapsed = time.time() - start_time
                save_checkpoint(idx + 1, shuffled_data, delays, result_logs, success_count, event_code, current_elapsed)
                progress_bar.progress((idx + 1) / total_count)

            clear_checkpoint()
            st.session_state.completed_results = {
                "tab_name": selected_tab_name,
                "total_count": total_count,
                "success_count": success_count,
                "logs": result_logs
            }
            st.session_state.is_running = False
            st.rerun()

        except Exception as e:
            st.error(f"작업 진행 중 오류 발생: {e}")

    if not st.session_state.is_running and st.session_state.completed_results:
        res = st.session_state.completed_results
        if res.get("tab_name") == selected_tab_name:
            st.success(f"작업 완료! [{res['tab_name']}] 전체 {res['total_count']}건 중 {res['success_count']}건 기입 성공했습니다.", icon=":material/notifications_active:")
            st.subheader(":material/grading: 작업 상세 결과")
            result_df = pd.DataFrame(res['logs'])
            st.dataframe(result_df, hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"구글 시트를 읽어오는 중 오류가 발생했습니다: {e}", icon=":material/error:")
