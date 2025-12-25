import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心設定 (保持穩定版本參數) ---
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導系統 v1.3 | 溝通強化版", layout="wide", page_icon="🏫")

# --- 2. 視覺化風格 (延續校長喜好的深色高質感風格) ---
st.markdown("""
    <style>
    .block-container { max-width: 1200px !important; margin: auto; padding-top: 1.5rem; }
    .stApp { background-color: #1a1d24; color: #eceff4; }
    .main-header {
        text-align: center; background: linear-gradient(120deg, #88c0d0 0%, #a3be8c 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 600; font-size: 2.2rem; margin-bottom: 2rem;
    }
    .line-card { background-color: #06c755; color: white; padding: 15px; border-radius: 10px; margin-top: 10px; border-left: 5px solid #04a948; }
    div[data-baseweb="textarea"] > div { background-color: #242933 !important; border-radius: 12px !important; border: 1px solid #4c566a !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 初始化服務 ---
@st.cache_resource
def init_all_services():
    try:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        model = genai.GenerativeModel(MODEL_NAME)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        client = gspread.authorize(creds)
        return model, client
    except Exception as e:
        st.error(f"連線異常：{e}")
        return None, None

ai_engine, hub_engine = init_all_services()

# --- 4. 主介面 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師溝通系統</h1>', unsafe_allow_html=True)

tab_input, tab_report = st.tabs(["📝 紀錄錄入與 LINE 助手", "📊 數據中樞與月報表"])

# --- 第一分頁：錄入與 LINE 助手 ---
with tab_input:
    col_in, col_out = st.columns([1, 1.2])

    with col_in:
        st.subheader("📝 觀察錄入")
        stu_id = st.text_input("學生代號")
        category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫"])
        raw_obs = st.text_area("事實描述：", height=280)
        analyze_btn = st.button("✨ 啟動 AI 專業轉譯與生成草稿", type="primary")

    with col_out:
        if analyze_btn and raw_obs:
            with st.spinner("AI 正在撰寫輔導紀錄與溝通金句..."):
                # 強化 Prompt，要求生成 LINE 草稿
                prompt = f"""
                你是一位充滿智慧與溫度的學校輔導老師。請針對以下個案內容：
                內容：{raw_obs}
                
                請輸出：
                1. 【專業格式紀錄】：客觀中立的輔導文字。
                2. 【學生行為分析】：深層心理動機簡析。
                3. 【LINE 親師溝通草稿】：請寫一段適合導師傳給家長的 LINE 訊息。
                   - 要求：語氣溫柔但專業、避免指責家長、強調「親師合作」與「我們一起幫助孩子」、結尾給予具體建議或邀約。
                """
                response = ai_engine.generate_content(prompt)
                # 簡單分割內容（這裡假設 AI 會按照格式輸出）
                st.session_state.current_analysis = response.text
        
        if 'current_analysis' in st.session_state:
            st.subheader("💡 AI 專業建議")
            st.info(st.session_state.current_analysis)
            
            # 額外顯示 LINE 草稿區 (讓老師一眼看到並方便複製)
            st.markdown('<div class="line-card">🟢 <b>LINE 溝通草稿 (建議複製)：</b></div>', unsafe_allow_html=True)
            # 這裡我們用一個 code block 方便老師一鍵點擊複製
            st.code(st.session_state.current_analysis.split("【LINE 親師溝通草稿】")[-1].strip(), language="text")

    st.divider()
    if st.button("💾 同步至雲端 Hub"):
        if stu_id and 'current_analysis' in st.session_state:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, category, raw_obs, st.session_state.current_analysis])
                st.balloons()
                st.success("✅ 紀錄已同步！")
                del st.session_state.current_analysis
            except Exception as e: st.error(f"儲存失敗：{e}")

# --- 第二分頁：月報表功能 (保持原功能) ---
with tab_report:
    st.subheader("📊 全校輔導大數據彙整")
    if st.button("🔄 重新整理本月報表"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                df['日期'] = pd.to_datetime(df['日期'])
                now = datetime.now()
                this_month_df = df[(df['日期'].dt.month == now.month) & (df['日期'].dt.year == now.year)]
                if not this_month_df.empty:
                    c1, c2 = st.columns([1, 1.5])
                    with c1:
                        st.bar_chart(this_month_df['類別'].value_counts())
                        st.metric("本月累計個案", len(this_month_df))
                    with c2:
                        report_res = ai_engine.generate_content(f"請針對本月輔導數據給予校長三點行政建議：{this_month_df['類別'].value_counts().to_dict()}")
                        st.success(report_res.text)
                else: st.info("本月暫無數據。")
        except Exception as e: st.error(f"數據解析異常：{e}")
