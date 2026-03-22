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
너는 현실적이고 엄격한 '건설 현장 시뮬레이터'야. 플레이어는 현장 소장이다.
[초기 상태] 예산: 100점, 안전도: 100점, 품질: 100점, 공정률: 0%
[진행 방식] 
반드시 플레이어가 전달하는 '현재 공정 단계'에 맞춰서 실제 현장 이슈를 발생시켜야 해.
- 토공사/기초 (0~20%): 흙막이 붕괴 우려, 파일 항타 소음 민원, 지하수 용출 등
- 골조공사 (21~60%): 철근 배근 간격 불량, 거푸집 동바리 좌굴 우려, 콘크리트 타설 후 컬링(Curling) 현상, 피복 두께 부족 등
- 마감공사 (61~90%): 방수층 들뜸, 조적/미장 크랙, 설비 배관 간섭 등
- 준공준비 (91~100%): 펀치리스트(미비점) 발생, 발주처 품질 지적 등

[출력 규칙] 반드시 아래 JSON 포맷으로만 출력해.
{
  "이전_선택_결과": "플레이어의 선택으로 인한 점수 증감과 현장 상황 변화 설명",
  "현재_상태": {"예산": 0, "안전도": 0, "품질": 0, "공정률": 0},
  "발생_상황": "현재 공정 단계에 맞는 새롭고 구체적인 현장 딜레마",
  "선택지": {"A": "행동과 리스크", "B": "행동과 리스크", "C": "행동과 리스크"}
}
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

# 💡 화면을 좌우로 분할 (비율 6:4)
left_col, right_col = st.columns([6, 4])

# --- [오른쪽 화면: 현장 CCTV 사진] ---
with right_col:
    st.subheader("📷 현장 CCTV")
    progress = status['공정률']
    
    # 공정률에 따라 다른 이미지 URL 연결
    if progress < 20:
        # 터파기, 흙막이, 기초 공사 이미지
        img_url = "https://images.unsplash.com/photo-1504307651254-35680f356f12?w=600&q=80" 
        caption = "🚧 가설 및 토공사 진행 중"
    elif progress < 60:
        # 철근, 거푸집, 타설 등 골조 공사 이미지
        img_url = "https://images.unsplash.com/photo-1541888086425-d81bb19240f5?w=600&q=80" 
        caption = "🏗️ 골조 및 콘크리트 공사 진행 중"
    elif progress < 90:
        # 외벽, 유리, 마감 공사 이미지
        img_url = "https://images.unsplash.com/photo-1589939705384-5185137a7f0f?w=600&q=80" 
        caption = "🏢 마감 및 방수 공사 진행 중"
    else:
        # 완공된 멋진 빌딩 이미지
        img_url = "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&q=80" 
        caption = "🎉 준공 완료!"
        
    st.image(img_url, caption=caption, use_column_width=True)

# --- [왼쪽 화면: 상황 보고 및 지시 내리기] ---
with left_col:
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

    # 현재 상황 및 선택지 진행
    if not st.session_state.game_over:
        st.warning(f"⚠️ **발생 상황:** {event['발생_상황']}")
        
        choice_options = []
        for key, val in event["선택지"].items():
            choice_options.append(f"{key}: {val}")
        
        selected_option = st.radio("소장님, 어떤 지시를 내리시겠습니까?", choice_options, index=None)
        
        if st.button("지시 내리기 👷‍♂️"):
            if selected_option:
                with st.spinner("현장 지시 사항을 반영 중입니다..."):
                    # 일지 기록
                    st.session_state.history_data.append({
                        "Turn": st.session_state.turn_count,
                        "Budget": status['예산'], 
                        "Safety": status['안전도'], 
                        "Quality": status['품질'], 
                        "Progress": status['공정률'],
                        "Event": event['발생_상황'], 
                        "Player_Choice": selected_option[0]
                    })
                    
                    # 공정 단계 계산
                    current_progress = status['공정률']
                    if current_progress < 20:
                        phase = "가설 및 토공사/기초공사 단계"
                    elif current_progress < 60:
                        phase = "지상층 철근/거푸집/콘크리트 골조공사 단계"
                    elif current_progress < 90:
                        phase = "내외부 방수 및 마감공사 단계"
                    else:
                        phase = "준공 전 펀치리스트 및 최종 점검 단계"

                    prompt = f"소장은 [{selected_option[0]}]를 선택했어. 결과를 계산해서 공정률을 올려줘. 다음 상황은 [{phase}]에 맞는 리얼한 현장 상황으로 줘."
                    
                    try:
                        res = st.session_state.chat_session.send_message(prompt)
                        st.session_state.current_event = json.loads(res.text)
                        st.session_state.turn_count += 1
                        st.rerun() 
                    except Exception as e:
                        st.error(f"오류가 발생했습니다: {e}")
            else:
                st.warning("선택지를 골라주세요!")

# 6. 하단 현장 일지 (Pandas 데이터프레임 시각화)
st.divider()
with st.expander("📊 소장님 업무 일지 (데이터 기록 확인)"):
    if st.session_state.history_data:
        df = pd.DataFrame(st.session_state.history_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.write("아직 기록된 일지가 없습니다.")