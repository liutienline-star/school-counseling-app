import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心參數設定 (保持與您剛才成功的設定一致) ---
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"

st.set_page_config(page_title="智慧輔導系統 v1.0", layout="wide", page_icon="🍎")

# --- 2. 專業視覺佈局 ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; margin: auto; padding-top: 1rem; }
    .stApp { background-color: #1a1d24; color: #eceff4; }
    .main-header {
        text-align: center; background: linear-gradient(120deg, #88c0d0 0%, #a3be8c 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 600; font-size: 2.2rem; margin-bottom: 2rem;
    }
    div[data-baseweb="textarea"] > div { background-color: #242933 !important; border-radius: 12px !important; }
    .card { background: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #434c5e; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 初始化連線 ---
@st.cache_resource
def init_all():
    # 使用您剛才成功的 Secrets Key 名稱
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    gs_client = gspread.authorize(creds)
    return ai_model, gs_client

ai_engine, hub_engine = init_all()

# --- 4. 核心功能函數 ---
def save_to_hub(data_row):
    try:
        sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
        sheet.append_row(data_row)
        return True
    except Exception as e:
        st.error(f"寫入 Hub 失敗：{e}")
        return False

# --- 5. 主介面設計 ---
st.markdown('<h1 class="main-header">🍎 智慧輔導紀錄系統 v1.0</h1>', unsafe_allow_html=True)

# 頂部狀態列
c1, c2, c3 = st.columns([1,1,1])
with c1: st.success("📡 系統連線：正常")
with c2: st.info(f"📂 數據中樞：{HUB_NAME}")
with c3: st.write(f"⏰ 當前時間：{datetime.now().strftime('%Y-%m-%d')}")

st.divider()

# 操作區
col_in, col_out = st.columns([1, 1.2])

with col_in:
    st.markdown("### 📝 紀錄輸入")
    stu_id = st.text_input("學生代號 (例如：701-05)", placeholder="請務必使用去識別化代號")
    category = st.selectbox("事件類別", ["人際衝突", "情緒困擾", "常規违規", "家長溝通", "學習適應"])
    
    raw_obs = st.text_area("原始觀察筆記 (隨手記)：", height=350, 
                          placeholder="請輸入發生的事實，例如：今天學生在課堂上突然大聲對老師咆哮，隨後衝出教室...")
    
    analyze_btn = st.button("✨ 啟動 AI 專業轉譯與分析", type="primary")

with col_out:
    st.markdown("### 💡 AI 專業建議與格式化")
    if analyze_btn and raw_obs:
        with st.spinner("AI 正在應用教育心理學模型分析中..."):
            prompt = f"""
            你是一位專業的學校輔導主任。請針對導師的筆記內容進行專業優化：
            【筆記內容】：{raw_obs}
            
            請輸出：
            1. 專業紀錄轉譯：將白話筆記轉化為符合輔導紀錄格式的客觀文字。
            2. 潛在動機分析：從學生心理發展角度分析可能原因。
            3. 後續處理建議：給導師的具體行動方案。
            4. 親師溝通金句：一句最適合與家長初步溝通的 professional wording。
            """
            response_container = st.empty()
            full_response = ""
            for chunk in ai_engine.generate_content(prompt, stream=True):
                full_response += chunk.text
                response_container.markdown(full_response + "▌")
            response_container.markdown(full_response)
            st.session_state.current_analysis = full_response
    elif 'current_analysis' in st.session_state:
        st.markdown(st.session_state.current_analysis)

# 儲存功能區
st.divider()
if st.button("💾 同步至雲端 Hub 並備份"):
    if stu_id and raw_obs and 'current_analysis' in st.session_state:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        # 準備存入 Hub 的欄位
        data = [timestamp, stu_id, category, raw_obs, st.session_state.current_analysis]
        if save_to_hub(data):
            st.balloons()
            st.success(f"✅ 學生 {stu_id} 的輔導紀錄已成功歸檔至 {HUB_NAME}！")
            # 清除暫存
            del st.session_state.current_analysis
    else:
        st.warning("⚠️ 請確認已填寫學生代號、觀察內容，並已點擊 AI 分析。")

# 歷史回顧
with st.expander("📊 歷史紀錄 Hub 預覽 (最新 3 筆)"):
    if hub_engine:
        try:
            records = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB).get_all_records()
            if records:
                st.table(pd.DataFrame(records).tail(3))
        except: st.write("尚無紀錄。")
