import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 設定對齊 ---
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" # 使用診斷程式證實成功的名稱

st.set_page_config(page_title="智慧輔導系統 v1.0", layout="wide")

# --- 2. 初始化連線 ---
@st.cache_resource
def init_services():
    try:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        model = genai.GenerativeModel(MODEL_NAME)
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return model, client
    except Exception as e:
        st.error(f"系統啟動異常：{e}")
        return None, None

ai_engine, hub_engine = init_services()

# --- 3. UI 介面 (1:1 高質感版) ---
st.markdown(f'<h1 style="text-align:center; color:#88c0d0;">🍎 智慧輔導紀錄系統 v1.0</h1>', unsafe_allow_html=True)

col_in, col_out = st.columns([1, 1.2])

with col_in:
    st.subheader("📝 紀錄輸入")
    stu_id = st.text_input("學生代號")
    category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫"])
    raw_obs = st.text_area("觀察描述：", height=300)
    analyze_btn = st.button("✨ 啟動 AI 專業轉譯", type="primary")

with col_out:
    st.subheader("💡 AI 專業建議")
    if analyze_btn and raw_obs:
        with st.spinner("AI 分析中..."):
            prompt = f"你是一位專業輔導老師，請分析此個案並提供：1.專業格式紀錄 2.行為分析 3.行動建議：\n{raw_obs}"
            response = ai_engine.generate_content(prompt)
            st.markdown(response.text)
            st.session_state.last_analysis = response.text
    elif 'last_analysis' in st.session_state:
        st.markdown(st.session_state.last_analysis)

st.divider()

if st.button("💾 同步至雲端 Hub"):
    if stu_id and 'last_analysis' in st.session_state:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, category, raw_obs, st.session_state.last_analysis])
            st.balloons()
            st.success("✅ 數據已成功存入雲端 Hub！")
        except Exception as e:
            st.error(f"儲存失敗：{e}")
