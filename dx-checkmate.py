import streamlit as st
import pandas as pd
import requests

# 페이지 탭 아이콘 세팅
st.set_page_config(page_title="DX-CheckMate", page_icon=":material/fact_check:", layout="wide")

# 레이아웃 분할 (좌측: 메인 타이틀 및 버튼 / 우측: 사용 설명서)
col_title, col_guide = st.columns([1.5, 1])

with col_title:
    st.title(":material/how_to_reg: DX-CheckMate 자동 출석")
    st.caption("구글 스프레드시트 '출석체크' 탭 데이터를 읽어와 백엔드 API로 직접 자동 출석을 제출합니다.")

    SHEET_ID = "1ws9JTAdRXwbp--NhrjWwelNorSTv1_LIJW7DijUtJLU"
    GID = "1678272994"
    CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
    SHEET_WEB_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={GID}"
    ADMIN_WEB_URL = "https://cms.dxcheck.kr/admin/event"

    API_URL = "https://api.dxcheck.kr/api/v1/attendance"

    # 바로가기 버튼 2개를 나란히 배치
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.link_button("출석체크 구글 시트 바로가기", SHEET_WEB_URL, icon=":material/table_view:", use_container_width=True)
    with btn_col2:
        # 버튼 명칭 변경 적용
        st.link_button("CMS 프로그램 출결관리 바로가기", ADMIN_WEB_URL, icon=":material/admin_panel_settings:", use_container_width=True)

with col_guide:
    st.info("""
    **💡 사용 방법 가이드**
    1. 각 학교의 **개별 시트('연수자 명단' 탭)**에 기입된 정보를 복사합니다.
    2. 왼쪽의 **[출석체크 구글 시트]** 버튼을 눌러, 대상자 데이터를 붙여넣기(입력) 합니다.
    3. 이번에 출석을 진행할 인원들의 **'출석하기'** 열 체크박스를 선택합니다.
    4. 본 웹 화면으로 돌아와 아래의 **[자동 출석체크 시작하기]** 버튼을 클릭합니다.
    5. 제출이 완료되면 **[CMS 프로그램 출결관리]**에서 최종 결과를 확인합니다.
    """)

st.divider()

try:
    # 매 로딩 시 구글 시트 실시간 데이터 직접 로드
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
    
    # '출석하기' 열 필터링
    target_df = df[df['출석하기'].astype(str).str.upper().isin(['TRUE', 'O', 'V', '1'])]
    
    st.write(f":material/list_alt: 현재 출석체크 대상자: **총 {len(target_df)}명**")
    
    preview_cols = ['이름', '학교명', '전화번호 뒤 4자리', '구분(교/직원)', '점심식사 참석여부', '저녁식사 참석여부']
    st.dataframe(target_df[[col for col in preview_cols if col in target_df.columns]], use_container_width=True)

    if st.button("자동 출석체크 시작하기", type="primary"):
        progress_bar = st.progress(0)
        log_area = st.empty()
        success_count = 0
        total_count = len(target_df)

        result_logs = []

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": "https://dxcheck.kr/",
            "Origin": "https://dxcheck.kr"
        })

        for idx, (_, row) in enumerate(target_df.iterrows()):
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
