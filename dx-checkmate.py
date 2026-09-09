import streamlit as st
import pandas as pd
import os

# Playwright 자동 브라우저 설치
os.system("playwright install chromium")
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="DX-CheckMate", page_icon="✅")
st.title("✅ DX-CheckMate 자동 출석 시스템")
st.caption("구글 시트에서 다운로드한 '출석체크.xlsx' 파일을 업로드해 주세요.")

uploaded_file = st.file_uploader("엑셀 파일(.xlsx) 선택", type=["xlsx"])

if uploaded_file is not None:
    try:
        # B2 셀(1행 1열)에서 URL 추출
        df_raw = pd.read_excel(uploaded_file, header=None)
        form_url = str(df_raw.iloc[1, 1]).strip()
        
        # 3행(인덱스 2)을 헤더로 지정하여 데이터 로드
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, header=2)
        
        st.success(f"🔗 타겟 출석 URL 인식 완료: {form_url}")
        
        # '출석하기' 열(H열)이 TRUE/O/V/1 인 데이터만 추출
        target_df = df[df['출석하기'].astype(str).str.upper().isin(['TRUE', 'O', 'V', '1'])]
        st.write(f"📋 총 **{len(target_df)}명**의 출석 대상자가 확인되었습니다.")
        st.dataframe(target_df[['이름', '전화번호 뒤 4자리', '구분(교/직원)', '점심식사 참석여부', '저녁식사 참석여부']])

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
                    phone_last4 = str(row.get('전화번호 뒤 4자리', '')).strip().replace('.0', '')
                    role = str(row.get('구분(교/직원)', '')).strip()
                    lunch_val = str(row.get('점심식사 참석여부', '')).strip()
                    dinner_val = str(row.get('저녁식사 참석여부', '')).strip()

                    log_area.text(f"[{idx+1}/{total_count}] {name} 선생님 출석 처리 중...")
                    
                    try:
                        page.goto(form_url, timeout=15000)
                        page.wait_for_load_state("networkidle")

                        # 1. 이름 입력
                        page.fill("input[placeholder*='이름'], input[name*='name']", name)
                        
                        # 2. 학교명 기본값 입력
                        page.fill("input[placeholder*='학교'], input[name*='school']", "영천중앙초등학교")

                        # 3. 전화번호 뒷 4자리
                        page.fill("input[placeholder*='휴대폰'], input[name*='phone']", phone_last4)

                        # 4. 구분 선택
                        if '교원' in role:
                            page.select_option("select[name*='role'], select[name*='type']", label="교원")
                        elif '직원' in role:
                            page.select_option("select[name*='role'], select[name*='type']", label="직원")

                        # 5. 점심식사
                        if lunch_val:
                            page.click(f"xpath=//label[contains(text(), '{lunch_val}')]")

                        # 6. 저녁식사
                        if dinner_val:
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
                        st.warning(f"❌ {name} 선생님 입력 중 오류 발생")

                    progress_bar.progress((idx + 1) / total_count)

                browser.close()

            st.success(f"🎉 작업 완료! 전체 {total_count}건 중 {success_count}건 기입을 성공했습니다.")

    except Exception as e:
        st.error(f"❌ 엑셀 구조 읽기 실패: {e}")
