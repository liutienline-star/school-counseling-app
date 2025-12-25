import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心設定 ---
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導系統 v1.5", layout="wide", page_icon="🏫")

# --- 2. 視覺風格 ---
st.markdown("""
    <style>
    .block-container { max-width: 1200px !important; margin: auto; padding-top: 1rem; }
    .stApp { background-color: #1a1d24; color: #eceff4; }
    .main-header {
        text-align: center; background: linear-gradient(120deg, #88c0d0 0%, #a3be8c 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 600; font-size: 2.2rem; margin-bottom: 2rem;
    }
    .record-box { background-color: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #4c566a; }
    .line-box { background-color: #06c755; color: white; padding: 15px; border-radius: 12px; }
    /* 讓按鈕並排的樣式 */
    div.stButton > button { width: 100%; border-radius: 8px; }
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

tab_input, tab_report = st.tabs(["📝 紀錄錄入與功能按鈕", "📊 數據中樞與月報表"])

# --- 第一分頁：雙按鈕功能區 ---
with tab_input:
    col_in, col_out = st.columns([1, 1.2])

    with col_in:
        st.subheader("📝 觀察錄入")
        stu_id = st.text_input("學生代號", placeholder="例如：702-05")
        category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫"])
        raw_obs = st.text_area("事實描述：", height=280, placeholder="請輸入觀察到的事實...")
        
        st.markdown("---")
        # 雙按鈕設計
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            gen_record = st.button("📁 生成專業紀錄")
        with btn_col2:
            gen_line = st.button("💬 生成 LINE 草稿")

    with col_out:
        # 功能 A：生成專業輔導紀錄
        if gen_record and raw_obs:
            with st.spinner("正在轉譯專業紀錄..."):
                prompt_a = f"你是一位專業輔導老師，請將以下觀察描述轉化為「專業、客觀」的輔導紀錄格式，並包含行為動機簡析：\n{raw_obs}"
                res_a = ai_engine.generate_content(prompt_a)
                st.session_state.formal_record = res_a.text
        
        # 功能 B：生成 LINE 溝通草稿
        if gen_line and raw_obs:
            with st.spinner("正在撰寫 LINE 草稿..."):
                prompt_b = f"你是一位溫柔專業的老師，請針對以下內容撰寫一段適合傳給家長的 LINE 訊息。強調親師合作、語氣委婉、提供具體建議：\n{raw_obs}"
                res_b = ai_engine.generate_content(prompt_b)
                st.session_state.line_draft = res_b.text

        # 顯示結果區塊
        if 'formal_record' in st.session_state:
            st.markdown("##### 📁 專業輔導紀錄分析")
            st.markdown(f'<div class="record-box">{st.session_state.formal_record}</div>', unsafe_allow_html=True)
            st.write("") # 間隔

        if 'line_draft' in st.session_state:
            st.markdown("##### 🟢 LINE 親師溝通草稿")
            st.code(st.session_state.line_draft, language="text")
            st.caption("💡 點擊右上角複製圖示即可使用")

    st.divider()
    # 儲存按鈕
    if st.button("💾 同步至雲端 Hub"):
        if stu_id and ( 'formal_record' in st.session_state or 'line_draft' in st.session_state ):
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                # 取得目前已生成的內容，若無則留空
                f_rec = st.session_state.get('formal_record', '未生成')
                l_dra = st.session_state.get('line_draft', '未生成')
                combined_res = f"【專業紀錄】\n{f_rec}\n\n【LINE草稿】\n{l_dra}"
                
                sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, category, raw_obs, combined_res])
                st.balloons()
                st.success("✅ 數據已存入 Hub！")
                # 清除狀態
                if 'formal_record' in st.session_state: del st.session_state.formal_record
                if 'line_draft' in st.session_state: del st.session_state.line_draft
            except Exception as e: st.error(f"儲存失敗：{e}")

# --- 第二分頁：月報表功能 (保持不變) ---
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
