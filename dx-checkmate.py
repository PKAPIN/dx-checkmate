import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="DX-CheckMate", page_icon="✅")
st.title("✅ DX-CheckMate 자동 출석 시스템")
st.caption("구글 스프레드시트 '출석체크' 탭 데이터를 읽어와 백엔드 API로 직접 자동 출석을 제출합니다.")

# 구글 스프레드시트 '출석체크' 탭 (gid=1678272994) CSV URL
SHEET_ID = "1ws9JTAdRXwbp--NhrjWwelNorSTv1_LIJW7DijUtJLU"
GID = "1678272994"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

# 실제 출석 처리 API 엔드포인트
API_URL = "https://api.dxcheck.kr/api/v1/attendance"

if st.button("🔄 구글 시트 실시간 데이터 불러오기"):
    st.cache_data.clear()

try:
    # 1. 2행에서 URL 및 고유 코드(UUID) 추출
    df_raw = pd.read_csv(CSV_URL, header=None)
    form_url = ""
    for cell in df_raw.iloc[1].dropna():
        cell_str = str(cell).strip()
        if cell_str.startswith("http"):
            form_url = cell_str
            break
            
    # URL에서 이벤트 고유 코드 추출 (예: 8b72783a-c69c-4975-8d86-326cc5050061)
    event_code = form_url.rstrip('/').split('/')[-1] if form_url else ""
    
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

            # 필수 데이터 검증
            if not school or school.lower() == 'nan':
                st.error(f"❌ [{name}] 선생님의 '학교명' 정보가 누락되어 출석 입력을 스킵합니다.")
                progress_bar.progress((idx + 1) / total_count)
                continue

            if not name or name.lower() == 'nan':
                st.error(f"❌ {idx+1}번째 행의 '이름' 정보가 누락되었습니다.")
                progress_bar.progress((idx + 1) / total_count)
                continue

            log_area.text(f"[{idx+1}/{total_count}] ({school}) {name} 선생님 출석 처리 중...")

            # API 전송 페이로드 구성 (확인된 Form Data 스펙과 100% 일치)
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
                # API 직접 전송 (POST)
                response = session.post(API_URL, data=payload, timeout=10)
                if response.status_code == 200:
                    success_count += 1
                else:
                    st.warning(f"⚠️ {name} 선생님 전송 응답 코드: {response.status_code}")
            except Exception as e:
                st.warning(f"❌ {name} 선생님 전송 중 오류 발생: {e}")

            progress_bar.progress((idx + 1) / total_count)

        st.success(f"🎉 작업 완료! 전체 {total_count}건 중 {success_count}건 기입을 성공했습니다.")

except Exception as e:
    st.error(f"❌ 구글 시트를 읽어오는 중 오류가 발생했습니다: {e}")
