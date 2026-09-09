import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="DX-CheckMate", page_icon="✅")
st.title("✅ DX-CheckMate 자동 출석 시스템")
st.caption("구글 스프레드시트 '출석체크' 탭 데이터를 실시간으로 읽어와 브라우저 없이 즉시 출석을 처리합니다.")

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

        # HTTP 세션 생성
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        for idx, (_, row) in enumerate(target_df.iterrows()):
            name = str(row.get('이름', '')).strip()
            school = str(row.get('학교명', '')).strip()
            phone_last4 = str(row.get('전화번호 뒤 4자리', '')).strip().replace('.0', '')
            role = str(row.get('구분(교/직원)', '')).strip()
            lunch_val = str(row.get('점심식사 참석여부', '')).strip()
            dinner_val = str(row.get('저녁식사 참석여부', '')).strip()

            # 필수 데이터 누락 시 즉시 중단 및 안내
            if not school or school.lower() == 'nan':
                st.error(f"❌ [{name}] 선생님의 '학교명' 정보가 누락되어 출석 입력을 진행하지 않습니다.")
                progress_bar.progress((idx + 1) / total_count)
                continue

            if not name or name.lower() == 'nan':
                st.error(f"❌ {idx+1}번째 행의 '이름' 정보가 누락되었습니다.")
                progress_bar.progress((idx + 1) / total_count)
                continue

            log_area.text(f"[{idx+1}/{total_count}] ({school}) {name} 선생님 출석 처리 중...")
            
            # 웹 폼 전송 데이터 페이로드 구성
            payload = {
                "name": name,
                "school": school,
                "phone": phone_last4,
                "role": role,
                "lunch": lunch_val if lunch_val.lower() != 'nan' else "",
                "dinner": dinner_val if dinner_val.lower() != 'nan' else "",
                "privacy_agree": "true"
            }

            try:
                # HTTP POST로 Form 데이터 직접 제출
                response = session.post(form_url, data=payload, timeout=10)
                if response.status_code in [200, 201, 302]:
                    success_count += 1
                else:
                    st.warning(f"⚠️ {name} 선생님 응답 코드: {response.status_code}")
            except Exception as e:
                st.warning(f"❌ {name} 선생님 전송 실패: {e}")

            progress_bar.progress((idx + 1) / total_count)

        st.success(f"🎉 작업 완료! 전체 {total_count}건 중 {success_count}건 기입을 성공했습니다.")

except Exception as e:
    st.error(f"❌ 구글 시트를 읽어오는 중 오류가 발생했습니다: {e}")
