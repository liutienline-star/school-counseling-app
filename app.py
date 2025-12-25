import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 設定 Hub 標籤 (請確保與 Google Sheets 名稱完全一致) ---
HUB_NAME = "School_Counseling_Hub"
SHEET_NAME = "Counseling_Logs"

# --- 2. 視覺佈局 1:1 ---
st.set_page_config(page_title="智慧輔導系統連線版", layout="wide")

st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; margin: auto; }
    .stApp { background-color: #1a1d24; color: #eceff4; }
    .main-header { text-align: center; color: #88c0d0; font-size: 2rem; margin-bottom: 20px; }
    .status-card { background: #242933; padding: 15px; border-radius: 10px; border: 1px solid #3b4252; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 初始化連線服務 ---
@st.cache_resource
def connect_services():
    try:
        # A. 接通 Gemini
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
        
        # B. 接通 Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        gs_client = gspread.authorize(creds)
        
        return ai_model, gs_client
    except Exception as e:
        st.error(f"❌ 連線失敗：{str(e)}")
        return None, None

ai_engine, hub_engine = connect_services()

# --- 4. 系統操作介面 ---
st.markdown('<h1 class="main-header">📝 智慧輔導系統 | 連線測試介面</h1>', unsafe_allow_html=True)

# 顯示當前連線狀態
with st.container():
    c1, c2 = st.columns(2)
    with c1:
        if ai_engine: st.success("🟢 Gemini AI 連線正常")
    with c2:
        if hub_engine: st.success(f"🟢 Hub ({HUB_NAME}) 已對接")

st.markdown("---")

# 測試輸入區
st.subheader("📡 即時寫入測試")
col_left, col_right = st.columns([1, 1])

with col_left:
    test_id = st.text_input("學生代碼測試", value="T01")
    test_obs = st.text_area("觀察描述測試", placeholder="請輸入一段測試文字...", height=200)
    
    if st.button("🚀 執行 AI 格式化並儲存"):
        if test_obs and hub_engine:
            # 呼叫 AI 處理
            with st.spinner("AI 正在轉譯..."):
                prompt = f"請將這段導師觀察紀錄轉化為專業輔導語言：{test_obs}"
                ai_response = ai_engine.generate_content(prompt).text
                
                # 準備寫入資料
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                row = [timestamp, test_id, "測試類別", test_obs, ai_response]
                
                # 寫入 Google Sheets
                try:
                    sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_NAME)
                    sheet.append_row(row)
                    st.session_state.last_res = ai_response
                    st.balloons()
                    st.success("✅ 數據已成功存入雲端 Hub！")
                except Exception as e:
                    st.error(f"寫入失敗：{e}")

with col_right:
    st.subheader("📋 雲端回傳預覽")
    if 'last_res' in st.session_state:
        st.info("這是 AI 生成並已存檔的內容：")
        st.write(st.session_state.last_res)
    else:
        st.write("等待測試...")

# --- 5. Hub 歷程查看 (直接從雲端拉取) ---
st.markdown("---")
if st.button("📊 刷新並讀取最新 5 筆 Hub 紀錄"):
    if hub_engine:
        try:
            data = hub_engine.open(HUB_NAME).worksheet(SHEET_NAME).get_all_records()
            if data:
                st.table(pd.DataFrame(data).tail(5))
            else:
                st.info("目前試算表內尚無紀錄。")
        except:
            st.warning("讀取失敗，請確認分頁名稱是否為 Counseling_Logs。")
