import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心安全與連線設定 (核心功能不變) ---
AUTH_CODE = "1225"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導紀錄與親師生溝通系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格優化 (針對字體亮度與排版) ---
st.markdown("""
    <style>
    /* 背景與基礎文字 */
    .stApp { 
        background-color: #1a1c23; 
        color: #e5e9f0; 
    }
    
    /* 核心修正：讓所有標籤與單選文字「絕對純白」 */
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
        opacity: 1 !important;
        letter-spacing: 1px;
    }
    
    /* 針對單選按鈕(Radio)選項的文字亮度 */
    div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] p {
        color: #FFFFFF !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
    }

    /* 主標題設計 */
    .main-header { 
        text-align: center; 
        background: linear-gradient(90deg, #88c0d0, #5e81ac);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800; 
        font-size: 2.8rem; 
        margin-bottom: 2rem;
        padding-top: 1rem;
    }

    /* 卡片式容器樣式 */
    .stTextArea textarea { 
        background-color: #2e3440 !important; 
        color: #ffffff !important; 
        border: 1px solid #4c566a !important;
        font-size: 1.1rem !important;
    }
    
    .stTabs [aria-selected="true"] { 
        background-color: #88c0d0 !important; 
        color: #242933 !important; 
        font-weight: bold !important;
    }

    /* 調整列間距 */
    [data-testid="column"] {
        padding: 0 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. 驗證邏輯 (功能維持，美化排版) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state["pwd_input"] == AUTH_CODE:
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.error("❌ 授權碼錯誤，請重新輸入。")

if not st.session_state.authenticated:
    # 建立美化的登入頁面
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        st.markdown("""
            <div style="text-align: center; background-color: #2e3440; padding: 40px; border-radius: 25px; border-top: 5px solid #88c0d0; box-shadow: 0 15px 35px rgba(0,0,0,0.4);">
                <h1 style="font-size: 60px; margin-bottom: 20px;">🔐</h1>
                <h2 style="color: #88c0d0;">導師身分驗證</h2>
                <p style="color: #d8dee9; font-size: 1.1rem;">請輸入授權碼以進入個人紀錄空間</p>
            </div>
        """, unsafe_allow_html=True)
        st.text_input("授權碼：", type="password", key="pwd_input", on_change=check_password)
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
        st.error(f"系統連線異常，請聯繫管理員：{e}")
        return None, None

ai_engine, hub_engine = init_all_services()

# --- 5. 主程式介面 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)

tab_input, tab_history, tab_report = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

# --- TAB 1: 紀錄錄入 ---
with tab_input:
    st.markdown("### ✍️ 第一步：觀察錄入與功能選擇")
    
    # 橫向排列基礎資訊
    row1_c1, row1_c2, row1_c3 = st.columns([1.5, 1, 1])
    with row1_c1:
        target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with row1_c2:
        stu_id = st.text_input("【學生代號】", placeholder="例如：809-01")
    with row1_c3:
        category = st.selectbox("【事件類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    # 全幅輸入區
    raw_obs = st.text_area("【事實描述或晤談紀錄摘要】", height=280, placeholder="身為導師，請在此紀錄觀察到的具體事實、對話重點或學生表現...")
    
    # 功能按鈕列
    st.markdown("<br>", unsafe_allow_html=True)
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    with btn_col1:
        gen_formal = st.button("📁 1. 生成優化紀錄文稿", use_container_width=True)
    with btn_col2:
        if "學生" in target_type:
            gen_plan = st.button("🎯 2. 生成後續觀察重點", use_container_width=True)
        else:
            gen_line = st.button("💬 2. 撰寫親師合作訊息", use_container_width=True)
    with btn_col3:
        save_hub = st.button("💾 3. 同步至雲端手冊", use_container_width=True, type="primary")

    st.divider()

    # --- 下方：AI 分析與建議顯示區 ---
    st.markdown("### ✨ 第二步：導師輔助分析結果")
    res_col_l, res_col_r = st.columns(2, gap="large")
    
    if gen_formal and raw_obs:
        with st.spinner("正在優化文稿..."):
            prompt = f"你是一位經驗豐富的班級導師，請將以下口語筆記轉化為專業、客觀且具備關懷視角的「導師觀察紀錄」：\n{raw_obs}"
            st.session_state.analysis_1 = ai_engine.generate_content(prompt).text
    
    if 'analysis_1' in st.session_state:
        with res_col_l:
            st.info("📋 **建議紀錄文稿** (可直接複製使用)")
            st.markdown(f'<div style="background-color:#2e3440; padding:20px; border-radius:15px; border:1px solid #4c566a; line-height:1.7;">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
            
    if "學生" in target_type and 'gen_plan' in locals() and gen_plan and raw_obs:
        with st.spinner("正在分析重點..."):
            st.session_state.analysis_2 = ai_engine.generate_content(f"身為導師，請針對此個案提供後續在班級中可觀察的行為重點與導師介入建議：\n{raw_obs}").text
    
    if "家長" in target_type and 'gen_line' in locals() and gen_line and raw_obs:
        with st.spinner("正在撰寫訊息..."):
            st.session_state.analysis_2 = ai_engine.generate_content(f"請以導師身份，撰寫一段與家長聯繫的訊息。語氣要溫馨、專業，強調親師合作：\n{raw_obs}").text

    if 'analysis_2' in st.session_state:
        with res_col_r:
            st.success(f"🎯 **{'導師行動建議' if '學生' in target_type else '親師合作草稿'}**")
            if "家長" in target_type: st.code(st.session_state.analysis_2, language="text")
            else: st.markdown(f'<div style="background-color:#2e3440; padding:20px; border-radius:15px; border-left:5px solid #88c0d0; line-height:1.7;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

    # 執行儲存功能
    if save_hub:
        if stu_id and ( 'analysis_1' in st.session_state or 'analysis_2' in st.session_state ):
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                an1 = st.session_state.get('analysis_1', 'N/A')
                an2 = st.session_state.get('analysis_2', 'N/A')
                sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, target_type, category, raw_obs, f"{an1}\n\n{an2}"])
                st.balloons()
                st.success(f"✅ 紀錄已同步至您的雲端個人手冊")
                # 儲存後清除暫存，避免重複儲存
                for k in ['analysis_1', 'analysis_2']: 
                    if k in st.session_state: del st.session_state[k]
            except Exception as e: st.error(f"儲存失敗，請檢查網路連線：{e}")

# --- TAB 2 & 3: 維持原有功能穩定性 ---
with tab_history:
    st.markdown("### 🔍 班級學生輔導歷程檢索")
    search_id = st.text_input("輸入學生代號查詢 (例如：809-01)：", key="final_search")
    if search_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            records = sheet.get_all_records()
            matches = [r for r in records if str(r.get('學生代號', '')) == search_id]
            if matches:
                st.info(f"📍 找到 {len(matches)} 筆歷史紀錄")
                for r in matches[::-1]:
                    with st.expander(f"📅 {r.get('日期')} | {r.get('對象')} | {r.get('類別')}"):
                        st.markdown(f"<div style='background-color:#2e3440; padding:15px; border-radius:10px;'>{r.get('AI 分析結果')}</div>", unsafe_allow_html=True)
            else: st.warning("目前查無此代號之相關紀錄。")
        except: st.error("資料讀取異常")

with tab_report:
    st.markdown("### 📊 班級觀察數據統計")
    if st.button("🔄 重新載入最新數據"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.metric("本學期輔導案量", len(df))
                    st.write(df['類別'].value_counts())
                with c2:
                    st.bar_chart(df['類別'].value_counts())
        except: st.error("數據統計異常")
