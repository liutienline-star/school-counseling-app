import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 定點設定 (確保名稱完全一致) ---
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
# 使用測試成功的最新模型
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導系統 | 導師行政減壓", layout="wide", page_icon="🏫")

# --- 2. 視覺化界面設計 ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; margin: auto; padding-top: 1.5rem; }
    .stApp { background-color: #1a1d24; color: #eceff4; }
    .main-header {
        text-align: center; background: linear-gradient(120deg, #88c0d0 0%, #a3be8c 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 600; font-size: 2.2rem; margin-bottom: 2rem;
    }
    div[data-baseweb="textarea"] > div { background-color: #242933 !important; border-radius: 12px !important; border: 1px solid #4c566a !important; }
    .status-badge { background: #2e3440; padding: 10px; border-radius: 8px; border-left: 4px solid #88c0d0; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 系統初始化 ---
@st.cache_resource
def init_all_services():
    try:
        # 配置 AI
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        model = genai.GenerativeModel(MODEL_NAME)
        
        # 配置 Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        
        return model, client
    except Exception as e:
        st.error(f"連線異常：{e}")
        return None, None

ai_engine, hub_engine = init_all_services()

# --- 4. 主介面佈局 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄系統</h1>', unsafe_allow_html=True)

# 顯示目前系統狀態
with st.container():
    c1, c2, c3 = st.columns(3)
    with c1: st.write(f"🟢 **系統狀態:** AI 2.5 Flash 已就緒")
    with c2: st.write(f"📂 **資料中樞:** `{HUB_NAME}`")
    with c3: st.write(f"📅 **今日日期:** {datetime.now().strftime('%Y-%m-%d')}")

st.divider()

# 操作區
col_in, col_out = st.columns([1, 1.2])

with col_in:
    st.subheader("📝 觀察紀錄輸入")
    stu_id = st.text_input("學生代號", placeholder="例如：802-15")
    category = st.selectbox("事件類別", ["常規生活", "人際衝突", "情緒困擾", "家庭溝通", "學習適應"])
    raw_obs = st.text_area("原始筆記 (輸入事實)：", height=350, placeholder="在此輸入您的觀察...")
    
    analyze_btn = st.button("✨ 啟動 AI 專業轉譯", type="primary")

with col_out:
    st.subheader("💡 AI 專業建議與格式化")
    if analyze_btn and raw_obs:
        with st.spinner("AI 正在應用教育心理學模型分析中..."):
            prompt = f"""
            你是一位專業的輔導老師，請針對以下內容進行優化：
            內容：{raw_obs}
            
            請輸出：
            1. 【專業格式紀錄】：以客觀、中立且專業的語言重寫。
            2. 【個案行為分析】：簡析可能的心理動機。
            3. 【行動方案建議】：給導師的具體對應方針。
            """
            res_placeholder = st.empty()
            full_res = ""
            for chunk in ai_engine.generate_content(prompt, stream=True):
                full_res += chunk.text
                res_placeholder.markdown(full_res + "▌")
            res_placeholder.markdown(full_res)
            st.session_state.current_res = full_res
    elif 'current_res' in st.session_state:
        st.markdown(st.session_state.current_res)

# 儲存與備份
st.divider()
if st.button("💾 同步至雲端 Hub"):
    if stu_id and 'current_res' in st.session_state:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            sheet.append_row([now, stu_id, category, raw_obs, st.session_state.current_res])
            st.balloons()
            st.success("✅ 紀錄已成功存入雲端 Hub，並完成異地備份。")
            del st.session_state.current_res
        except Exception as e:
            st.error(f"寫入 Hub 出錯：{e}")
    else:
        st.warning("⚠️ 請確認已輸入學生代號並完成 AI 分析。")

# 歷程預覽
with st.expander("📊 歷史紀錄 Hub 預覽"):
    if hub_engine:
        try:
            data = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB).get_all_records()
            if data:
                st.table(pd.DataFrame(data).tail(5))
        except: st.info("尚無紀錄。")
