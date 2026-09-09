import streamlit as st
import pandas as pd
import os

# Playwright 및 브라우저 의존성 자동 설치
os.system("playwright install chromium")
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="DX-CheckMate", page_icon="✅")
st.title("✅ DX-CheckMate 자동 출석 시스템")
st.caption("구글 스프레드시트 '출석체크' 탭 데이터를 실시간으로 읽어와 키보드 네비게이션으로 자동 출석을 진행합니다.")

# 구글 스프레드시트 '출석체크' 탭 (gid=1678272994) CSV URL
SHEET_ID = "1ws9JTAdRXwbp--NhrjWwelNorSTv1_LIJW7DijUtJLU"
GID = "1678272994"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

if st.button("🔄 구글 시트 실시간 데이터 불러오기"):
    st.cache_data.clear()

try:
    # 1. 2행에서 URL 자동 추출
    df_raw = pd.read_csv(CSV_URL, header=None)
    form_url = ""
    for cell in df_raw.iloc[1].dropna():
        if str(cell).strip().startswith("http"):
            form_url = str(cell).strip()
            break
            
    # 2. 3행(index 2)을 헤더로 지정하여 데이터 로드
    df = pd.read_csv(CSV_URL, header=2)
    
    st.success(f"🔗 실시간 출석 URL 인식 완료: {form_url}")
    
    # '출석하기' 열에서 TRUE/O/V/1로 표시된 체크 항목만 필터링
    target_df = df[df['출석하기'].astype(str).str.upper().isin(['TRUE', 'O', 'V', '1'])]
    st.write(f"📋 현재 출석체크 대상자: **총 {len(target_df)}명**")
    
    preview_cols = ['이름', '학교명', '전화번호 뒤 4자리', '구분(교/직원)', '점심식사 참석여부', '저녁식사 참석여부']
    st.dataframe(target_df[[col for col in preview_cols if col in target_df.columns]])

    if st.button("🚀 자동 출석체크 시작하기"):
        progress_bar = st.progress(0)
        log_area = st.empty()
        success_count = 0
        total_count = len(target_df)

        # 항목별 방향키 인덱스 매핑
        ROLE_MAP = {'교원': 0, '직원': 1, '강사': 2, '학생': 3, '학부모': 4, '운영기관': 5}
        LUNCH_MAP = {'O': 0, 'X': 1}
        DINNER_MAP = {'O': 0, 'X': 1}

        # 직전 선택 위치 추적 변수 (최초 기본값)
        current_role_idx = 0
        current_lunch_idx = 0
        current_dinner_idx = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto(form_url)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2500)  # 최초 진입 시 2.5초 대기

            for idx, (_, row) in enumerate(target_df.iterrows()):
                name = str(row.get('이름', '')).strip()
                school = str(row.get('학교명', '')).strip()
                phone = str(row.get('전화번호 뒤 4자리', '')).strip().replace('.0', '')
                
                role_str = str(row.get('구분(교/직원)', '')).strip()
                lunch_str = str(row.get('점심식사 참석여부', '')).strip().upper()
                dinner_str = str(row.get('저녁식사 참석여부', '')).strip().upper()

                # 필수 데이터 누락 시 오입력 방지를 위한 즉시 중단
                if not school or school.lower() == 'nan':
                    st.error(f"❌ [{name}] 선생님의 '학교명' 정보가 누락되어 출석 입력을 스킵합니다.")
                    progress_bar.progress((idx + 1) / total_count)
                    continue

                if not name or name.lower() == 'nan':
                    st.error(f"❌ {idx+1}번째 행의 '이름' 정보가 누락되었습니다.")
                    progress_bar.progress((idx + 1) / total_count)
                    continue

                log_area.text(f"[{idx+1}/{total_count}] ({school}) {name} 선생님 출석 기입 중...")

                target_role_idx = ROLE_MAP.get(role_str, 0)
                target_lunch_idx = LUNCH_MAP.get(lunch_str, 0)
                target_dinner_idx = DINNER_MAP.get(dinner_str, 0)

                try:
                    # 1. Tab -> 이름 입력
                    page.keyboard.press("Tab")
                    page.keyboard.type(name, delay=50)

                    # 2. Tab -> 학교명 입력
                    page.keyboard.press("Tab")
                    page.keyboard.type(school, delay=50)

                    # 3. Tab -> 휴대폰 번호 뒷 4자리 입력
                    page.keyboard.press("Tab")
                    page.keyboard.type(phone, delay=50)

                    # 4. Tab -> 구분 선택 (이전 상태 위치 차이만큼 방향키 이동)
                    page.keyboard.press("Tab")
                    role_diff = target_role_idx - current_role_idx
                    if role_diff > 0:
                        for _ in range(role_diff): page.keyboard.press("ArrowDown")
                    elif role_diff < 0:
                        for _ in range(abs(role_diff)): page.keyboard.press("ArrowUp")
                    current_role_idx = target_role_idx

                    # 5. Tab -> 점심식사 여부
                    page.keyboard.press("Tab")
                    lunch_diff = target_lunch_idx - current_lunch_idx
                    if lunch_diff > 0:
                        for _ in range(lunch_diff): page.keyboard.press("ArrowDown")
                    elif lunch_diff < 0:
                        for _ in range(abs(lunch_diff)): page.keyboard.press("ArrowUp")
                    current_lunch_idx = target_lunch_idx

                    # 6. Tab -> 저녁식사 여부
                    page.keyboard.press("Tab")
                    dinner_diff = target_dinner_idx - current_dinner_idx
                    if dinner_diff > 0:
                        for _ in range(dinner_diff): page.keyboard.press("ArrowDown")
                    elif dinner_diff < 0:
                        for _ in range(abs(dinner_diff)): page.keyboard.press("ArrowUp")
                    current_dinner_idx = target_dinner_idx

                    # 7. Tab -> 개인정보 수집 이용동의 (Space)
                    page.keyboard.press("Tab")
                    page.keyboard.press("Space")

                    # 8. Enter (제출)
                    page.keyboard.press("Enter")
                    success_count += 1

                    # 9. 새로고침 및 2.5초 대기 (다음 사이클 준비)
                    page.reload()
                    page.wait_for_load_state("domcontentloaded")
                    page.wait_for_timeout(2500)

                except Exception as e:
                    st.warning(f"❌ {name} 선생님 입력 중 오류 발생: {e}")

                progress_bar.progress((idx + 1) / total_count)

            browser.close()

        st.success(f"🎉 작업 완료! 전체 {total_count}건 중 {success_count}건 기입을 성공했습니다.")

except Exception as e:
    st.error(f"❌ 구글 시트를 읽어오는 중 오류가 발생했습니다: {e}")
