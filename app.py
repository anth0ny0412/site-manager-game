import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# 1. 페이지 기본 설정
st.set_page_config(page_title="건설 현장 소장 서바이벌", page_icon="🏗️", layout="centered")
st.title("🏗️ 건설 현장 소장 서바이벌")
st.subheader("모든 책임은 소장에게 있습니다. 현장을 무사히 준공시키세요!")

# 2. API 키 설정 (스트림릿 클라우드의 Secrets 금고에서 안전하게 가져옴)
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except KeyError:
    st.error("오류: Streamlit Secrets에 API 키가 설정되지 않았습니다.")
    st.stop()

# 3. 모델 설정 (반드시 gemini-2.5-flash 사용!)
generation_config = {
    "temperature": 0.7,
    "response_mime_type": "application/json",
}

system_instruction = """
너는 현실적이고 엄격한 '건설 현장 시뮬레이터'야. 플레이어는 이제 막 부임한 현장 소장이다.
[초기 상태] 예산: 100점, 안전도: 100점, 품질: 100점, 공정률: 0%
[진행 방식] 콘크리트 타설, 거푸집, 철근 배근, 방수 공사 등 실제 현장 이슈를 다뤄. 3가지 선택지(A, B, C)를 줘.
[출력 규칙] 반드시 주어진 JSON 포맷("이전_선택_결과", "현재_상태", "발생_상황", "선택지")으로만 출력해. 다른 부연 설명은 절대 하지 마.
"""

@st.cache_resource
def get_model():
    return genai.GenerativeModel(
        model_name="gemini-2.5-flash", # 에러 방지를 위해 2.5-flash로 고정
        generation_config=generation_config,
        system_instruction=system_instruction
    )

# 4. 세션 상태 관리 (새로고침해도 게임이 초기화되지 않게 유지)
if "chat_session" not in st.session_state:
    st.session_state.chat_session = get_model().start_chat(history=[])
if "game_over" not in st.session_state:
    st.session_state.game_over = False
if "history_data" not in st.session_state:
    st.session_state.history_data = [] # 판다스 일지 기록용 배열
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 1
if "current_event" not in st.session_state:
    # 첫 게임 시작 요청
    response = st.session_state.chat_session.send_message("게임을 시작해줘.")
    st.session_state.current_event = json.loads(response.text)

# 5. 게임 화면 UI 구성
event = st.session_state.current_event
status = event["현재_상태"]

# 상단 4가지 스탯 대시보드
cols = st.columns(4)
cols[0].metric("💰 예산", f"{status['예산']}점")
cols[1].metric("⛑️ 안전도", f"{status['안전도']}점")
cols[2].metric("🏢 품질", f"{status['품질']}점")
cols[3].metric("📈 공정률", f"{status['공정률']}%")
st.divider()

# 이전 턴의 결과 출력
if event.get("이전_선택_결과"):
    st.info(f"📋 **이전 지시 결과:** {event['이전_선택_결과']}")

# 게임 종료 조건 체크
if status['공정률'] >= 100:
    st.success("🎉 무사히 준공을 마쳤습니다! 훌륭한 소장님이십니다!")
    st.balloons()
    st.session_state.game_over = True
elif status['예산'] <= 0 or status['안전도'] <= 0 or status['품질'] <= 0:
    st.error("🚨 현장에 심각한 문제가 발생하여 소장 자리에서 해임되었습니다. 게임 오버!")
    st.session_state.game_over = True

# 현재 상황 및 선택지 진행 (게임이 끝나지 않았을 때만 표시)
if not st.session_state.game_over:
    st.warning(f"⚠️ **발생 상황:** {event['발생_상황']}")
    
    # 선택지를 라디오 버튼으로 예쁘게 구성
    choice_options = []
    for key, val in event["선택지"].items():
        choice_options.append(f"{key}: {val}")
    
    selected_option = st.radio("소장님, 어떤 지시를 내리시겠습니까?", choice_options, index=None)
    
    # 지시 내리기 버튼
    if st.button("지시 내리기 👷‍♂️"):
        if selected_option:
            with st.spinner("현장 지시 사항을 반영 중입니다..."):
                # 현재 상태를 기록 (Pandas 표를 위해)
                st.session_state.history_data.append({
                    "Turn": st.session_state.turn_count,
                    "Budget": status['예산'], 
                    "Safety": status['안전도'], 
                    "Quality": status['품질'], 
                    "Progress": status['공정률'],
                    "Event": event['발생_상황'], 
                    "Player_Choice": selected_option[0] # A, B, C 중 하나
                })
                
                # AI에게 소장님의 선택(A, B, C) 전달하고 다음 상황 받기
                try:
                    res = st.session_state.chat_session.send_message(selected_option[0])
                    st.session_state.current_event = json.loads(res.text)
                    st.session_state.turn_count += 1
                    st.rerun() # 화면 새로고침하여 다음 턴 표시
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")
        else:
            st.warning("선택지를 골라주세요!")

# 6. 하단 현장 일지 (Pandas 데이터프레임 시각화)
with st.expander("📊 소장님 업무 일지 (데이터 기록 확인)"):
    if st.session_state.history_data:
        # 딕셔너리 리스트를 Pandas DataFrame으로 변환하여 출력
        df = pd.DataFrame(st.session_state.history_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.write("아직 기록된 일지가 없습니다.")