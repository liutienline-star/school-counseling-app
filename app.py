import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心參數設定 (請確保與 Google Sheets 一致) ---
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"

# --- 2. 網頁頁面配置 ---
st.set_page_config(page_title="智慧輔導系統 | 導師行政減壓", layout="wide", page_icon="🍎")

# 高質感深色主題 CSS
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
    .stButton>button { width: 100%; height: 3rem; background-color: #2e3440; color: #88c0d0; border: 1px solid #4c566a; border-radius: 8px; }
    .stButton>button:hover { background-color: #88c0d0; color: #1a1d24; border: 1px solid #88c0d0; }
    .status-card { background: #2e3440; padding: 15px; border-radius: 10px; border-left: 5px solid #88c0d0; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 初始化服務 (修正後的順序) ---
@st.cache_resource
def init_services():
    try:
        # A. 先執行 AI 配置 (必須在建立模型之前)
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        # B. 建立模型物件
        model = genai.GenerativeModel('models/gemini-1.5-flash')
        
        # C. 初始化 Google Sheets 連線
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        
        return model, client
    except Exception as e:
        st.error(f"⚠️ 系統連線異常：{e}")
        return None, None

ai_engine, hub_engine = init_services()

# --- 4. 輔助函數 ---
def save_data(data_row):
    try:
        sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
        sheet.append_row(data_row)
        return True
    except Exception as e:
        st.error(f"❌ 數據寫入失敗: {e}")
        return False

# --- 5. 主介面 UI ---
st.markdown('<h1 class="main-header">🍎 智慧輔導紀錄系統</h1>', unsafe_allow_html=True)

# 顯示連線狀態與資訊
with st.container():
    c1, c2, c3 = st.columns([1,1,1])
    with c1: st.markdown(f"📡 **系統狀態:** {'✅ 已連線' if hub_engine else '❌ 斷線'}")
    with c2: st.markdown(f"📂 **數據中樞:** `{HUB_NAME}`")
    with c3: st.markdown(f"📅 **今日日期:** {datetime.now().strftime('%Y-%m-%d')}")

st.markdown("---")

# 操作區：左側輸入、右側分析
col_input, col_output = st.columns([1, 1.2])

with col_input:
    st.subheader("📝 紀錄輸入區")
    stu_id = st.text_input("學生代號", placeholder="例如：701-05 (請勿填寫全名)")
    case_type = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫"])
    raw_text = st.text_area("觀察描述 (大白話紀錄)：", height=380, 
                           placeholder="在此輸入您觀察到的事實內容...")
    
    analyze_trigger = st.button("✨ 啟動 AI 專業轉譯與分析", type="primary")

with col_output:
    st.subheader("💡 AI 專業建議與優化紀錄")
    if analyze_trigger and raw_text:
        with st.spinner("AI 正在應用教育心理學模型分析中..."):
            prompt = f"""
            你是一位專業的學校輔導老師。請針對以下導師的觀察筆記進行優化：
            觀察內容：{raw_text}
            
            請提供：
            1. 【專業格式紀錄】：以客觀、專業的輔導語言重寫紀錄。
            2. 【學生行為分析】：從心理或環境角度簡析可能原因。
            3. 【後續行動建議】：提供導師具體的處置或觀察方針。
            4. 【親師溝通方案】：建議一句與家長溝通時的專業語句。
            """
            try:
                # 串流輸出
                placeholder = st.empty()
                full_res = ""
                response = ai_engine.generate_content(prompt, stream=True)
                for chunk in response:
                    full_res += chunk.text
                    placeholder.markdown(full_res + "▌")
                placeholder.markdown(full_res)
                st.session_state.last_analysis = full_res
            except Exception as e:
                st.error(f"AI 生成失敗: {e}")
    elif 'last_analysis' in st.session_state:
        st.markdown(st.session_state.last_analysis)

# 儲存與存檔
st.markdown("---")
col_btn1, col_btn2 = st.columns([1, 2])
with col_btn1:
    if st.button("💾 確認並同步至雲端 Hub"):
        if stu_id and raw_text and 'last_analysis' in st.session_state:
            now_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            # 存入 Google Sheets 的欄位：時間, 代號, 類別, 原始內容, AI分析
            record = [now_time, stu_id, case_type, raw_text, st.session_state.last_analysis]
            if save_data(record):
                st.balloons()
                st.success(f"✅ 紀錄已成功存入 {HUB_NAME}")
                # 清除快取，避免重複提交
                if 'last_analysis' in st.session_state:
                    del st.session_state.last_analysis
        else:
            st.warning("⚠️ 請填寫完整資料並完成 AI 分析後再存檔。")

# 歷程預覽
with st.expander("📊 歷史紀錄 Hub 快速檢視 (最新 5 筆)"):
    if hub_engine:
        try:
            raw_data = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB).get_all_records()
            if raw_data:
                df = pd.DataFrame(raw_data).tail(5)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("目前 Hub 內尚無紀錄。")
        except:
            st.write("等待數據同步中...")
