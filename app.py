import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心安全與連線設定 ---
AUTH_CODE = "1225"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

# 保持 wide 模式但透過 CSS 限制內容寬度
st.set_page_config(page_title="智慧輔導紀錄系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格優化 (限制寬度與文字高亮) ---
st.markdown("""
    <style>
    /* 核心佈局修正：限制內容寬度並置中 */
    .block-container {
        max-width: 1100px !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        margin: auto;
    }

    .stApp { 
        background-color: #1a1c23; 
        color: #e5e9f0; 
    }
    
    /* 標籤文字強化：純白且加粗 */
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        opacity: 1 !important;
    }
    
    /* 單選按鈕文字強化 */
    div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] p {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }

    .main-header { 
        text-align: center; 
        background: linear-gradient(90deg, #88c0d0, #5e81ac);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800; 
        font-size: 2.8rem; 
        margin-bottom: 2rem;
    }

    /* 文字輸入框內部配色 */
    .stTextArea textarea { 
        background-color: #2e3440 !important; 
        color: #ffffff !important; 
        border: 1px solid #4c566a !important;
    }

    /* Tab 切換按鈕美化 */
    .stTabs [aria-selected="true"] { 
        background-color: #88c0d0 !important; 
        color: #242933 !important; 
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. 驗證邏輯 (解決警告問題) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col_m, _ = st.columns([1, 1.5, 1])
    with col_m:
        st.markdown("""
            <div style="text-align: center; background-color: #2e3440; padding: 40px; border-radius: 25px; border-top: 5px solid #88c0d0; box-shadow: 0 15px 35px rgba(0,0,0,0.4);">
                <h1 style="font-size: 60px; margin-bottom: 20px;">🔐</h1>
                <h2 style="color: #88c0d0;">導師身分驗證</h2>
                <p style="color: #d8dee9; font-size: 1.1rem;">請輸入授權碼進入系統</p>
            </div>
        """, unsafe_allow_html=True)
        pwd_input = st.text_input("授權碼：", type="password")
        if pwd_input:
            if pwd_input == AUTH_CODE:
                st.session_state.authenticated = True
                st.rerun() # 此處 rerun 是合法的，不會出現警告
            else:
                st.error("❌ 授權碼錯誤")
    st.stop()

# --- 4. 初始化服務 ---
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

# --- 5. 主程式頁面 (已限制內容寬度) ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)

tab_input, tab_history, tab_report = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

with tab_input:
    st.markdown("### ✍️ 第一步：觀察錄入與功能選擇")
    
    # 橫向基礎資訊
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with c2:
        stu_id = st.text_input("【學生代號】", placeholder="例如：809-01")
    with c3:
        category = st.selectbox("【事件類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    # 紀錄輸入
    raw_obs = st.text_area("【事實描述或晤談紀錄摘要】", height=280, placeholder="在此輸入觀察事實...")
    
    # 操作按鈕
    st.markdown("<br>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1: gen_formal = st.button("📁 1. 生成優化紀錄文稿", use_container_width=True)
    with b2:
        if "學生" in target_type: gen_plan = st.button("🎯 2. 生成後續觀察重點", use_container_width=True)
        else: gen_line = st.button("💬 2. 撰寫親師合作訊息", use_container_width=True)
    with b3: save_hub = st.button("💾 3. 同步至雲端手冊", use_container_width=True, type="primary")

    st.divider()
    st.markdown("### ✨ 第二步：導師輔助分析結果")
    res_l, res_r = st.columns(2, gap="large")
    
    if gen_formal and raw_obs:
        with st.spinner("優化中..."):
            st.session_state.analysis_1 = ai_engine.generate_content(f"身為導師，請優化紀錄：\n{raw_obs}").text
    
    if 'analysis_1' in st.session_state:
        with res_l:
            st.info("📋 **建議紀錄文稿**")
            st.markdown(f'<div style="background-color:#2e3440; padding:20px; border-radius:15px; border:1px solid #4c566a; line-height:1.7;">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)

    if 'analysis_2' in st.session_state:
        with res_r:
            st.success(f"🎯 **{'導師行動建議' if '學生' in target_type else '親師合作草稿'}**")
            if "家長" in target_type: st.code(st.session_state.analysis_2)
            else: st.markdown(f'<div style="background-color:#2e3440; padding:20px; border-radius:15px; border-left:5px solid #88c0d0; line-height:1.7;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

    # 存檔邏輯 (功能與原版完全一致)
    if save_hub and stu_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, target_type, category, raw_obs, f"{st.session_state.get('analysis_1','')}\n\n{st.session_state.get('analysis_2','')}"])
            st.balloons()
            st.success("✅ 紀錄已成功同步至雲端 Hub")
            for k in ['analysis_1', 'analysis_2']: 
                if k in st.session_state: del st.session_state[k]
        except Exception as e: st.error(f"儲存失敗：{e}")

# (後續歷史追蹤與報表功能維持穩定)
with tab_history:
    st.markdown("### 🔍 班級學生輔導歷程檢索")
    search_id = st.text_input("輸入代號查詢 (例：809-01)：")
    if search_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            records = sheet.get_all_records()
            matches = [r for r in records if str(r.get('學生代號', '')) == search_id]
            if matches:
                for r in matches[::-1]:
                    with st.expander(f"📅 {r.get('日期')} | {r.get('對象')}"):
                        st.markdown(f"<div style='background-color:#2e3440; padding:15px; border-radius:10px;'>{r.get('AI 分析結果')}</div>", unsafe_allow_html=True)
            else: st.warning("無符合代號之紀錄")
        except: st.error("連線異常")

with tab_report:
    st.markdown("### 📊 班級數據統計")
    if st.button("🔄 更新彙整數據"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            st.metric("累積輔導筆數", len(df))
            st.bar_chart(df['類別'].value_counts())
        except: st.error("數據統計異常")
