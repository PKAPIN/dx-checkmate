import streamlit as st
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

st.set_page_config(page_title="DX-CheckMate", page_icon="✅")

st.title("✅ DX-CheckMate 자동 출석 시스템")
st.caption("구글 시트에서 다운로드한 '출석체크.xlsx' 파일을 업로드해 주세요.")

def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

uploaded_file = st.file_uploader("엑셀 파일(.xlsx) 선택", type=["xlsx"])

if uploaded_file is not None:
    try:
        # B2 셀(1행 1열)에서 URL 추출
        df_raw = pd.read_excel(uploaded_file, header=None)
        form_url = str(df_raw.iloc[1, 1]).strip()
        
        # 3행을 헤더로 지정하여 실제 데이터 로드
        uploaded_file.seek(0)
        df = pd.read_excel(uploaded_file, header=2)
        
        st.success(f"🔗 타겟 출석 URL 인식 완료: {form_url}")
        st.dataframe(df.head(5))

        if st.button("🚀 자동 출석체크 시작하기"):
            with st.spinner("자동화 브라우저를 구동하는 중입니다..."):
                driver = get_driver()
                wait = WebDriverWait(driver, 10)
            
            progress_bar = st.progress(0)
            log_area = st.empty()
            
            # '출석하기' 체크박스 행 필터링
            target_rows = [row for _, row in df.iterrows() if str(row.get('출석하기', '')).strip().upper() in ['TRUE', 'O', 'V', '1']]
            total_count = len(target_rows)
            success_count = 0
            
            for idx, row in enumerate(target_rows):
                name = str(row.get('이름', '')).strip()
                phone_last4 = str(row.get('전화번호 뒤 4자리', '')).strip()
                if phone_last4.endswith('.0'): phone_last4 = phone_last4[:-2]
                
                role = str(row.get('구분(교/직원)', '')).strip()
                lunch_val = str(row.get('점심식사 참석여부', '')).strip()
                dinner_val = str(row.get('저녁식사 참석여부', '')).strip()
                
                log_area.text(f"[{idx+1}/{total_count}] {name} 선생님 출석 처리 중...")
                
                driver.get(form_url)
                time.sleep(1.2)
                
                try:
                    # 1. 이름
                    name_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='이름을 입력하세요' or contains(@name, 'name')]")))
                    name_input.clear()
                    name_input.send_keys(name)

                    # 2. 학교명 (기본값)
                    school_input = driver.find_element(By.XPATH, "//input[@placeholder='학교명을 입력하세요' or contains(@name, 'school')]")
                    school_input.clear()
                    school_input.send_keys("영천중앙초등학교")

                    # 3. 전화번호 뒷 4자리
                    phone_input = driver.find_element(By.XPATH, "//input[@placeholder='휴대폰 번호 뒷 4자리' or contains(@name, 'phone')]")
                    phone_input.clear()
                    phone_input.send_keys(phone_last4)

                    # 4. 구분
                    role_select_element = driver.find_element(By.XPATH, "//select[contains(@name, 'role') or contains(@name, 'type')]")
                    role_select = Select(role_select_element)
                    if '교원' in role: role_select.select_by_visible_text('교원')
                    elif '직원' in role: role_select.select_by_visible_text('직원')

                    # 5. 점심식사
                    if lunch_val:
                        lunch_radio = driver.find_element(By.XPATH, f"//div[contains(text(), '점심')]//following-sibling::*//label[contains(text(), '{lunch_val}')]")
                        driver.execute_script("arguments[0].click();", lunch_radio)

                    # 6. 저녁식사
                    if dinner_val:
                        dinner_radio = driver.find_element(By.XPATH, f"//div[contains(text(), '저녁')]//following-sibling::*//label[contains(text(), '{dinner_val}')]")
                        driver.execute_script("arguments[0].click();", dinner_radio)

                    # 7. 개인정보 동의
                    privacy_checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox' and contains(@name, 'agree')]")
                    if not privacy_checkbox.is_selected():
                        driver.execute_script("arguments[0].click();", privacy_checkbox)

                    # 8. 제출
                    submit_button = driver.find_element(By.XPATH, "//button[contains(text(), '제출') or @type='submit']")
                    driver.execute_script("arguments[0].click();", submit_button)

                    time.sleep(1.2)
                    success_count += 1
                except Exception as e:
                    st.warning(f"❌ {name} 선생님 입력 실패")

                progress_bar.progress((idx + 1) / total_count)
            
            driver.quit()
            st.success(f"🎉 작업 완료! 전체 {total_count}건 중 {success_count}건 기입을 성공했습니다.")

    except Exception as e:
        st.error(f"엑셀 읽기 오류: {e}")
