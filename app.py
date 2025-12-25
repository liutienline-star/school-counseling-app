import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心安全與連線設定 ---
AUTH_CODE = "1225"  # <--- 校長，您可以在這裡修改您的專屬密碼 (例如校慶日期)
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導系統 | 安全授權版", layout="wide", page_icon="🛡️")

# --- 2. 驗證邏輯 ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state["pwd_input"] == AUTH_CODE:
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.error("❌ 授權碼錯誤，請洽詢系統管理員。")

# --- 3. 登入介面 ---
if not st.session_state.authenticated:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1, 1.5, 1])
    with col_m:
        st.markdown("""
            <div style="text-align: center; background-color: #2e3440; padding: 30px; border-radius: 15px; border: 1px solid #88c0d0;">
                <h2 style="color: #88c0d0;">🔐 校內人員驗證</h2>
                <p style="color: #eceff4;">本系統包含學生個資，請輸入授權碼以繼續</p>
            </div>
        """, unsafe_allow_html=True)
        st.text_input("請輸入專屬授權碼：", type="password", key="pwd_input", on_change=check_password)
        st.stop() # 停止執行後續代碼

# --- 4. 驗證通過後的正式系統 (承襲 v1.5 所有功能) ---

# --- 視覺風格 ---
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
    </style>
""", unsafe_allow_html=True)

# --- 初始化服務 ---
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

# --- 主介面 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師溝通系統</h1>', unsafe_allow_html=True)
st.sidebar.success(f"🔑 已授權存取 (登入時間: {datetime.now().strftime('%H:%M')})")
if st.sidebar.button("登出系統"):
    st.session_state.authenticated = False
    st.rerun()

tab_input, tab_report = st.tabs(["📝 紀錄錄入與功能按鈕", "📊 數據中樞與月報表"])

# --- 第一分頁：紀錄錄入 (雙按鈕獨立版) ---
with tab_input:
    col_in, col_out = st.columns([1, 1.2])
    with col_in:
        st.subheader("📝 觀察錄入")
        stu_id = st.text_input("學生代號", placeholder="例如：702-05")
        category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫"])
        raw_obs = st.text_area("事實描述：", height=280)
        
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1: gen_record = st.button("📁 生成專業紀錄")
        with btn_col2: gen_line = st.button("💬 生成 LINE 草稿")

    with col_out:
        if gen_record and raw_obs:
            with st.spinner("轉譯中..."):
                st.session_state.formal_record = ai_engine.generate_content(f"請將以下觀察轉化為專業輔導紀錄：\n{raw_obs}").text
        if gen_line and raw_obs:
            with st.spinner("擬稿中..."):
                st.session_state.line_draft = ai_engine.generate_content(f"請針對以下內容撰寫給家長的 LINE 訊息，強調親師合作：\n{raw_obs}").text

        if 'formal_record' in st.session_state:
            st.markdown("##### 📁 專業輔導紀錄分析")
            st.markdown(f'<div class="record-box">{st.session_state.formal_record}</div>', unsafe_allow_html=True)
        if 'line_draft' in st.session_state:
            st.markdown("##### 🟢 LINE 親師溝通草稿")
            st.code(st.session_state.line_draft, language="text")

    st.divider()
    if st.button("💾 同步至雲端 Hub"):
        if stu_id and ( 'formal_record' in st.session_state or 'line_draft' in st.session_state ):
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                f_rec = st.session_state.get('formal_record', '未生成')
                l_dra = st.session_state.get('line_draft', '未生成')
                sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, category, raw_obs, f"【紀錄】{f_rec}\n【LINE】{l_dra}"])
                st.balloons()
                st.success("✅ 數據已存入 Hub！")
                for k in ['formal_record', 'line_draft']: 
                    if k in st.session_state: del st.session_state[k]
            except Exception as e: st.error(f"儲存失敗：{e}")

# --- 第二分頁：月報表功能 ---
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
                        report_res = ai_engine.generate_content(f"請針對本月輔導數據給予校長行政建議：{this_month_df['類別'].value_counts().to_dict()}")
                        st.success(report_res.text)
                else: st.info("本月暫無數據。")
        except Exception as e: st.error(f"報表異常：{e}")
