import streamlit as st
import google.generativeai as genai
import pandas as pd
import json

# 1. 페이지 기본 설정
st.set_page_config(page_title="건설 현장 소장 서바이벌", page_icon="🏗️", layout="centered")
st.title("🏗️ 건설 현장 소장 서바이벌")
st.subheader("모든 책임은 소장에게 있습니다. 현장을 무사히 준공시키세요!")

# 2. API 키 설정 (스트림릿 클라우드의 Secrets 금고에서 가져옴)
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except KeyError:
    st.error("오류: Streamlit Secrets에 API 키가 설정되지 않았습니다.")
    st.stop()

# 3. 모델 설정 (시공 순서 및 스포일러 금지 규칙 적용)
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

🚨 [가장 중요한 규칙 - 점수 스포일러 절대 금지!]
플레이어에게 제시하는 '선택지(A, B, C)'에는 특정 점수가 깎이거나 오를 것이라는 예상 리스크나 결과, 힌트를 절대 미리 적지 마. 
오직 소장으로서 내릴 수 있는 '구체적인 행동 지시'만 현장 용어로 짧고 건조하게 적어. (예: "A: 철근 반입 반려 후 재발주", "B: 추가 보강 후 타설 강행")
결과(점수 증감)는 플레이어가 선택을 마친 뒤, 다음 턴의 '이전_선택_결과'에서만 냉정하게 알려줘.

[출력 규칙] 반드시 아래 JSON 포맷으로만 출력해.
{
  "이전_선택_결과": "직전 턴의 결정으로 인해 예산/안전/품질 점수가 어떻게 깎이거나 올랐는지 구체적인 수치와 함께 결과 보고",
  "현재_상태": {"예산": 0, "안전도": 0, "품질": 0, "공정률": 0},
  "발생_상황": "현재 공정 단계에 맞는 새롭고 구체적인 현장 딜레마",
  "선택지": {"A": "행동 지시", "B": "행동 지시", "C": "행동 지시"}
}
"""

@st.cache_resource
def get_model():
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        system_instruction=system_instruction
    )

# 4. 세션 상태 관리 (게임 데이터 유지)
if "chat_session" not in st.session_state:
    st.session_state.chat_session = get_model().start_chat(history=[])
if "game_over" not in st.session_state:
    st.session_state.game_over = False
if "history_data" not in st.session_state:
    st.session_state.history_data = [] 
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 1
if "current_event" not in st.session_state:
    # 게임 시작 시 첫 공정 단계를 명시하여 요청
    response = st.session_state.chat_session.send_message("게임을 시작해줘. 가설 및 토공사/기초공사 단계에 맞는 첫 번째 상황을 보고해.")
    st.session_state.current_event = json.loads(response.text)

# 5. 게임 화면 UI 구성 (이미지 제거 및 텍스트 중심)
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

                # 스포일러 없는 다음 상황 요청
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

# 6. 하단 현장 일지 (Pandas 데이터프레임)
st.divider()
with st.expander("📊 소장님 업무 일지 (데이터 기록 확인)"):
    if st.session_state.history_data:
        df = pd.DataFrame(st.session_state.history_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.write("아직 기록된 일지가 없습니다.")