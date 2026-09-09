import streamlit as st
import pandas as pd
import requests
import random
import time

st.set_page_config(page_title="DX-CheckMate", page_icon=":material/fact_check:", layout="wide")

col_title, col_guide = st.columns([1.5, 1])

with col_title:
    st.title(":material/how_to_reg: DX-CheckMate 자동 출석")
    st.caption("구글 스프레드시트 데이터를 읽어와 백엔드 API로 현장 패턴에 맞게 자동 출석을 제출합니다.")

    SHEET_ID = "1ws9JTAdRXwbp--NhrjWwelNorSTv1_LIJW7DijUtJLU"
    GID = "1678272994"
    CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    SHEET_WEB_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={GID}"
    ADMIN_WEB_URL = "https://cms.dxcheck.kr/admin/event"

    API_URL = "https://api.dxcheck.kr/api/v1/attendance"

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.link_button("출석체크 구글 시트 바로가기", SHEET_WEB_URL, icon=":material/table_view:", use_container_width=True)
    with btn_col2:
        st.link_button("CMS 프로그램 출결관리 바로가기", ADMIN_WEB_URL, icon=":material/admin_panel_settings:", use_container_width=True)

with col_guide:
    st.info("""
    **💡 사용 방법 가이드**
    1. 각 학교의 **개별 시트('연수자 명단' 탭)**에 기입된 정보를 복사합니다.
    2. **[출석체크 구글 시트]** 버튼을 눌러, 대상자 데이터를 붙여넣기(입력) 합니다.
    3. 이번에 출석을 진행할 인원들의 **'출석하기'** 열 체크박스를 선택합니다.
    4. 아래에서 실행 모드 선택 후 **[자동 출석체크 시작하기]** 버튼을 클릭합니다.
    5. 제출이 완료되면 **[CMS 프로그램 출결관리]**에서 최종 결과를 확인합니다.
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

    # 구간별 인원 비율 배분 (초기 몰림 60% ➔ 감쇄 30% ➔ 마무리 10%)
    count_peak = int(num_people * 0.60)
    count_mid = int(num_people * 0.30)
    count_tail = num_people - count_peak - count_mid

    t1 = total_duration * 0.40
    t2 = total_duration * 0.80

    timestamps = []

    # [전반부] 다수 기기의 동시 접속 폭주 구간 (소수점 밀리초 난수)
    for _ in range(count_peak):
        timestamps.append(random.uniform(0, t1))

    # [중반부] 간헐적 접속 구간
    for _ in range(count_mid):
        timestamps.append(random.uniform(t1, t2))

    # [후반부] 잔여 인원 개별 접속 구간
    for _ in range(count_tail):
        timestamps.append(random.uniform(t2, total_duration))

    # 타임스탬프 정렬 및 간격 계산
    timestamps.sort()
    delays = []
    prev_t = 0
    for t in timestamps:
        delays.append(t - prev_t)
        prev_t = t

    return delays

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
    
    st.success(f"실시간 출석 URL 인식 완료: {form_url}", icon=":material/link:")
    
    target_df = df[df['출석하기'].astype(str).str.upper().isin(['TRUE', 'O', 'V', '1'])]
    
    st.write(f":material/list_alt: 현재 출석체크 대상자: **총 {len(target_df)}명**")
    
    preview_cols = ['이름', '학교명', '전화번호 뒤 4자리', '구분(교/직원)', '점심식사 참석여부', '저녁식사 참석여부']
    st.dataframe(target_df[[col for col in preview_cols if col in target_df.columns]], use_container_width=True)

    st.subheader(":material/tune: 출석 패턴 모드 선택")
    
    exec_mode = st.radio(
        "연수 인원 및 현장 상황에 맞는 모드를 선택하세요.",
        [
            "⚡ [1분 이내 초고속 모드] (1분 이내 완료 / 긴급 출석 처리용)",
            "🔥 [2분 초밀집 모드] (0 - 2분 완료 / 소규모 10 - 20명용)",
            "🕵️ [4분 현장 표준 모드] (2 - 4분 완료 / 중규모 30 - 50명용)",
            "🐢 [6분 완만 분산 모드] (4 - 6분 완료 / 대규모 60명 이상용)",
            "🚀 [고속 즉시 모드] (1초 이내 완료 / 시스템 테스트용)"
        ],
        index=2
    )

    with st.expander("ℹ️ 자동 출석 시스템 세부 작동 원리 안내"):
        st.markdown("""
        이 시스템은 자동화 프로그램으로 감지되지 않도록 **사람들의 실제 출석 행동 패턴**을 수학적으로 재현합니다.

        **1. 명단 순서 무작위 섞기 (랜덤 셔플)**
        * 구글 시트 1번 줄부터 순서대로 제출하면 매크로로 의심받을 수 있어, 제비뽑기처럼 명단 순서를 무작위로 뒤섞어서 전송합니다.

        **2. 시간대별 자연스러운 분산 제출 (60% ➔ 30% ➔ 10%)**
        * **전반부 (초기 몰림 60%)**: 현장 안내 직후 다수의 연수 기기(스마트폰)에서 동시다발적으로 무작위 폭주 제출하는 현상 재현
        * **중반부 (완만 감쇄 30%)**: 뒤늦게 안내를 확인한 연수자들이 드문드문 제출하는 현상 재현
        * **후반부 (잔여 마무리 10%)**: 마감 직전 마지막 남은 인원이 제출하는 현상 재현
        """)

    if st.button("자동 출석체크 시작하기", type="primary"):
        total_count = len(target_df)
        progress_bar = st.progress(0)
        log_area = st.empty()
        success_count = 0
        result_logs = []

        shuffled_df = target_df.sample(frac=1).reset_index(drop=True)
        delays = generate_decay_delays(total_count, exec_mode)

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://dxcheck.kr/",
            "Origin": "https://dxcheck.kr"
        })

        for idx, (_, row) in enumerate(shuffled_df.iterrows()):
            wait_time = delays[idx]
            
            # 동시 제출(0.1초 미만)은 UI 지연 없이 즉시 연속 발송
            if wait_time >= 0.1:
                step = 0.1
                for elapsed in range(int(wait_time / step)):
                    remaining = round(wait_time - (elapsed * step), 1)
                    log_area.text(f"⏳ [{idx+1}/{total_count}명] 무작위 현장 패턴 대기 중... (다음 전송까지 {remaining}초)")
                    time.sleep(step)

            name = str(row.get('이름', '')).strip()
            school = str(row.get('학교명', '')).strip()
            phone_last4 = str(row.get('전화번호 뒤 4자리', '')).strip().replace('.0', '')
            role = str(row.get('구분(교/직원)', '')).strip()
            lunch_str = str(row.get('점심식사 참석여부', '')).strip().upper()
            dinner_str = str(row.get('저녁식사 참석여부', '')).strip().upper()

            if not school or school.lower() == 'nan':
                result_logs.append({
                    "이름": name if name else f"{idx+1}번 행",
                    "학교명": "미기입",
                    "처리 결과": "실패",
                    "상세 사유": "학교명 누락"
                })
                progress_bar.progress((idx + 1) / total_count)
                continue

            if not name or name.lower() == 'nan':
                result_logs.append({
                    "이름": f"{idx+1}번 행",
                    "학교명": school,
                    "처리 결과": "실패",
                    "상세 사유": "이름 누락"
                })
                progress_bar.progress((idx + 1) / total_count)
                continue

            log_area.text(f"[{idx+1}/{total_count}] ({school}) {name} 선생님 출석 처리 중...")

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
                    success_count += 1
                    result_logs.append({
                        "이름": name,
                        "학교명": school,
                        "처리 결과": "성공",
                        "상세 사유": "출석 기입 완료"
                    })
                else:
                    result_logs.append({
                        "이름": name,
                        "학교명": school,
                        "처리 결과": "실패",
                        "상세 사유": f"서버 응답 에러 ({response.status_code})"
                    })
            except Exception as e:
                result_logs.append({
                    "이름": name,
                    "학교명": school,
                    "처리 결과": "실패",
                    "상세 사유": f"통신 오류"
                })

            progress_bar.progress((idx + 1) / total_count)

        log_area.empty()
        st.success(f"작업 완료! 전체 {total_count}건 중 {success_count}건 기입 성공했습니다.", icon=":material/notifications_active:")

        st.subheader(":material/grading: 작업 상세 결과")
        result_df = pd.DataFrame(result_logs)
        st.dataframe(result_df, hide_index=True, use_container_width=True)

except Exception as e:
    st.error(f"구글 시트를 읽어오는 중 오류가 발생했습니다: {e}", icon=":material/error:")
