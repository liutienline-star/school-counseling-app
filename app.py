import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心設定 (嚴格保持與測試成功版一致) ---
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導系統 | 營運與管理", layout="wide", page_icon="🏫")

# --- 2. 視覺化界面設計 (保持校長喜好的高質感深色風格) ---
st.markdown("""
    <style>
    .block-container { max-width: 1200px !important; margin: auto; padding-top: 1.5rem; }
    .stApp { background-color: #1a1d24; color: #eceff4; }
    .main-header {
        text-align: center; background: linear-gradient(120deg, #88c0d0 0%, #a3be8c 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 600; font-size: 2.2rem; margin-bottom: 2rem;
    }
    div[data-baseweb="textarea"] > div { background-color: #242933 !important; border-radius: 12px !important; border: 1px solid #4c566a !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #2e3440; border-radius: 4px 4px 0px 0px; padding: 10px 20px; color: #88c0d0; }
    .stTabs [aria-selected="true"] { background-color: #88c0d0 !important; color: #1a1d24 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 初始化服務 (保持診斷成功的初始化順序) ---
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
        st.error(f"系統連線異常：{e}")
        return None, None

ai_engine, hub_engine = init_all_services()

# --- 4. 主介面導覽 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與管理系統</h1>', unsafe_allow_html=True)

# 建立分頁
tab_input, tab_report = st.tabs(["📝 紀錄錄入與 AI 分析", "📊 數據中樞與月報表"])

# --- 第一分頁：紀錄錄入 (原功能完全保留) ---
with tab_input:
    st.markdown("### 📝 即時觀察錄入")
    col_in, col_out = st.columns([1, 1.2])

    with col_in:
        stu_id = st.text_input("學生代號", placeholder="例如：903-21")
        category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫"])
        raw_obs = st.text_area("原始筆記描述：", height=350, placeholder="輸入事實觀察...")
        analyze_btn = st.button("✨ 啟動 AI 專業轉譯", type="primary")

    with col_out:
        if analyze_btn and raw_obs:
            with st.spinner("AI 正在應用教育心理學模型分析中..."):
                prompt = f"你是一位專業輔導老師，請針對此個案提供專業紀錄、分析與建議：\n{raw_obs}"
                response = ai_engine.generate_content(prompt)
                st.session_state.current_analysis = response.text
        
        if 'current_analysis' in st.session_state:
            st.markdown("##### 💡 AI 建議內容")
            st.info(st.session_state.current_analysis)

    st.divider()
    if st.button("💾 同步至雲端 Hub"):
        if stu_id and 'current_analysis' in st.session_state:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                now_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet.append_row([now_time, stu_id, category, raw_obs, st.session_state.current_analysis])
                st.balloons()
                st.success(f"✅ 紀錄已成功存入 {HUB_NAME}")
                del st.session_state.current_analysis
            except Exception as e:
                st.error(f"儲存失敗：{e}")
        else:
            st.warning("⚠️ 請填寫代號並執行 AI 分析後再存檔。")

# --- 第二分頁：月報表分析 (新增的彙整功能) ---
with tab_report:
    st.subheader("📅 全校輔導大數據彙整")
    
    if st.button("🔄 重新整理並生成本月報表"):
        try:
            with st.spinner("正在從雲端 Hub 提取數據並進行 AI 分析..."):
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                all_records = sheet.get_all_records()
                
                if all_records:
                    df = pd.DataFrame(all_records)
                    # 轉換日期格式
                    df['日期'] = pd.to_datetime(df['日期'])
                    now = datetime.now()
                    # 篩選當月數據
                    this_month_df = df[(df['日期'].dt.month == now.month) & (df['日期'].dt.year == now.year)]
                    
                    if not this_month_df.empty:
                        # 視覺化指標
                        c1, c2 = st.columns([1, 1.5])
                        with c1:
                            st.markdown(f"#### {now.month}月 分類統計")
                            counts = this_month_df['類別'].value_counts()
                            st.bar_chart(counts)
                            st.metric("本月累計個案數", len(this_month_df))
                        
                        with c2:
                            st.markdown("#### 🤖 AI 趨勢洞察分析")
                            summary_data = counts.to_dict()
                            report_prompt = f"身為輔導主任，請針對本月輔導統計數據給予校長三點行政建議：{summary_data}"
                            report_res = ai_engine.generate_content(report_prompt)
                            st.success(report_res.text)
                        
                        st.markdown("---")
                        st.markdown("#### 🔍 本月詳細明細")
                        st.dataframe(this_month_df, use_container_width=True)
                    else:
                        st.info(f"📅 本月 ({now.month}月) 尚未有紀錄存入。")
                else:
                    st.warning("目前 Hub 中尚無任何歷史數據。")
        except Exception as e:
            st.error(f"數據讀取異常：{e}")
