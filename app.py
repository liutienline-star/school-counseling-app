import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="系統診斷模式", layout="wide")

st.title("🩺 智慧校園系統：環境診斷程式")
st.info("本頁面用於確認 API 金鑰有效性與模型路徑，解決 404 錯誤。")

# 1. 檢查 Secrets 結構
st.subheader("1. 鑰匙箱 (Secrets) 結構檢查")
keys = st.secrets.to_dict().keys()
st.write(f"目前偵測到的標籤：`{list(keys)}`")

# 2. 測試 Gemini 連線
st.subheader("2. AI 模型權限掃描")
try:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    st.success("✅ API 金鑰配置成功")
    
    st.write("--- 正在拉取可用模型清單 ---")
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            st.code(f"可用模型：{m.name}")
    
    if available_models:
        st.success(f"✅ 找到 {len(available_models)} 個可用模型")
        
        # 進行一次微型測試
        test_model_name = available_models[0] # 取清單中第一個
        st.write(f"🧪 正在使用 `{test_model_name}` 進行即時通訊測試...")
        model = genai.GenerativeModel(test_model_name)
        response = model.generate_content("你好，請回覆『連線成功』")
        st.info(f"AI 回傳結果：{response.text}")
    else:
        st.error("❌ 找不到任何支援文字生成的模型。")
        
except Exception as e:
    st.error(f"❌ AI 診斷過程出錯：{e}")

# 3. 測試 Sheets 連線
st.subheader("3. 數據 Hub 連線測試")
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    st.success("✅ Google Sheets 驗證通過")
    
    # 試著抓取檔案名稱
    # 請確保這檔名與您雲端一致
    HUB_NAME = "School_Counseling_Hub" 
    sheet = client.open(HUB_NAME)
    st.success(f"✅ 成功找到 Hub 檔案：`{HUB_NAME}`")
except Exception as e:
    st.error(f"❌ Hub 診斷出錯：{e}")
