import streamlit as st
import pandas as pd
import os

# Playwright 자동 브라우저 설치
os.system("playwright install chromium")
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="DX-CheckMate", page_icon="✅")
st.title("✅ DX-CheckMate 자동 출석 시스템")
st.caption("구글 스프레드시트 '출석체크' 탭 데이터를 실시간으로 읽어와 자동 출석을 진행합니다.")

# 구글 스프레드시트 '출석체크' 탭 (gid=1678272994) CSV 내보내기 URL
SHEET_ID = "1ws9JTAdRXwbp--NhrjWwelNorSTv1_LIJW7DijUtJLU"
GID = "1678272994"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# 데이터 새로고침 버튼
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
    
    # 미리보기 테이블 출력
    preview_cols = ['이름', '학교명', '전화번호 뒤 4자리', '구분(교/직원)', '점심식사 참석여부', '저녁식사 참석여부']
    st.dataframe(target_df[[col for col in preview_cols if col in target_df.columns]])

    if st.button("🚀 자동 출석체크 시작하기"):
        progress_bar = st.progress(0)
        log_area = st.empty()
        success_count = 0
        total_count = len(target_df)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for idx, (_, row) in enumerate(target_df.iterrows()):
                name = str(row.get('이름', '')).strip()
                school = str(row.get('학교명', '')).strip()
                phone_last4 = str(row.get('전화번호 뒤 4자리', '')).strip().replace('.0', '')
                role = str(row.get('구분(교/직원)', '')).strip()
                lunch_val = str(row.get('점심식사 참석여부', '')).strip()
                dinner_val = str(row.get('저녁식사 참석여부', '')).strip()

                # ⚠️ 필수 데이터(이름, 학교명, 전화번호) 검증 - 누락 시 기본값을 채우지 않고 즉시 중단 및 에러 처리
                if not school or school.lower() == 'nan':
                    st.error(f"❌ [{name}] 선생님의 '학교명' 정보가 누락되어 출석 입력을 진행하지 않습니다.")
                    progress_bar.progress((idx + 1) / total_count)
                    continue

                if not name or name.lower() == 'nan':
                    st.error(f"❌ {idx+1}번째 행의 '이름' 정보가 누락되었습니다.")
                    progress_bar.progress((idx + 1) / total_count)
                    continue

                log_area.text(f"[{idx+1}/{total_count}] ({school}) {name} 선생님 출석 처리 중...")
                
                try:
                    page.goto(form_url, timeout=15000)
                    page.wait_for_load_state("networkidle")

                    # 1. 이름 입력
                    page.fill("input[placeholder*='이름'], input[name*='name']", name)
                    
                    # 2. 학교명 입력 (시트에 기입된 값 그대로 입력)
                    page.fill("input[placeholder*='학교'], input[name*='school']", school)

                    # 3. 전화번호 뒷 4자리
                    page.fill("input[placeholder*='휴대폰'], input[name*='phone']", phone_last4)

                    # 4. 구분 선택
                    if '교원' in role:
                        page.select_option("select[name*='role'], select[name*='type']", label="교원")
                    elif '직원' in role:
                        page.select_option("select[name*='role'], select[name*='type']", label="직원")

                    # 5. 점심식사
                    if lunch_val and lunch_val.lower() != 'nan':
                        page.click(f"xpath=//label[contains(text(), '{lunch_val}')]")

                    # 6. 저녁식사
                    if dinner_val and dinner_val.lower() != 'nan':
                        page.click(f"xpath=//label[contains(text(), '{dinner_val}')]")

                    # 7. 개인정보 동의
                    privacy_box = page.locator("input[type='checkbox']")
                    if privacy_box.is_visible() and not privacy_box.is_checked():
                        privacy_box.check()

                    # 8. 제출 버튼 클릭
                    page.click("button:has-text('제출'), input[type='submit']")
                    page.wait_for_timeout(1000)
                    
                    success_count += 1
                except Exception as e:
                    st.warning(f"❌ {name} 선생님 입력 중 오류 발생: {e}")

                progress_bar.progress((idx + 1) / total_count)

            browser.close()

        st.success(f"🎉 작업 완료! 전체 {total_count}건 중 {success_count}건 기입을 성공했습니다.")

except Exception as e:
    st.error(f"❌ 구글 시트를 읽어오는 중 오류가 발생했습니다: {e}")
