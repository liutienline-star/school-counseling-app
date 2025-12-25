import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 【設定一致性檢查點】 ---
# 1. 這裡的 key 必須對應 Secrets 裡的 [gcp_service_account]
GCP_KEY = "gcp_service_account"
# 2. 這裡的 key 必須對應 Secrets 裡的 [gemini]
AI_KEY = "gemini"
# 3. 這裡的名稱必須對應 Google Sheets 的實際檔名與分頁名
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"

st.set_page_config(page_title="智慧輔導數據對接測試", layout="wide")

# --- 初始化連線模組 ---
@st.cache_resource
def init_connection():
    try:
        # A. AI 連線
        genai.configure(api_key=st.secrets[AI_KEY]["api_key"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # B. Hub 連線
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets[GCP_KEY], scope)
        client = gspread.authorize(creds)
        
        return model, client
    except Exception as e:
        st.error(f"❌ 系統一致性檢查失敗：{str(e)}")
        return None, None

ai_engine, hub_engine = init_connection()

# --- 介面呈現 ---
st.markdown(f"## 🏫 智慧輔導系統：一致性連線測試")

if ai_engine and hub_engine:
    st.success("🎉 一致性檢查通過！各系統已成功串接。")
    
    # 測試一個簡單的儲存功能
    st.divider()
    test_input = st.text_input("請輸入測試文字（成功後會存入 Hub）：")
    
    if st.button("執行寫入測試"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            sheet.append_row([now, "系統測試", test_input])
            st.balloons()
            st.success("✅ 數據已寫入 Google Sheets！")
        except Exception as e:
            st.error(f"寫入失敗，請檢查 Sheets 權限或名稱是否正確：{e}")
else:
    st.warning("⚠️ 請檢查 Streamlit Secrets 中的 [gemini] 與 [gcp_service_account] 標籤名稱是否正確。")
