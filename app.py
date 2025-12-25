import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心安全與連線設定 ---
AUTH_CODE = "641101"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導紀錄與親師生溝通系統", layout="wide", page_icon="🏫")

# --- 2. 驗證邏輯 ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state["pwd_input"] == AUTH_CODE:
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.error("❌ 授權碼錯誤。")

if not st.session_state.authenticated:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        st.markdown("""
            <div style="text-align: center; background-color: #2e3440; padding: 30px; border-radius: 15px; border: 1px solid #4c566a;">
                <h2 style="color: #88c0d0;">🔐 導師身分驗證</h2>
                <p style="color: #d8dee9;">請輸入授權碼以進入個人紀錄空間</p>
            </div>
        """, unsafe_allow_html=True)
        st.text_input("授權碼：", type="password", key="pwd_input", on_change=check_password)
        st.stop()

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

# --- 4. 視覺風格優化 (深度強化文字亮度) ---
st.markdown("""
    <style>
    /* 基礎背景 */
    .stApp { 
        background-color: #242933; 
        color: #d8dee9; 
    }
    
    /* 1. 強化所有元件上方的標籤文字 (如：學生代號、事件類別) */
    [data-testid="stWidgetLabel"] p, label {
        color: #FFFFFF !important; 
        font-size: 1.15rem !important;
        font-weight: 700 !important;
        opacity: 1 !important;
    }

    /* 2. 特別針對單選按鈕 (Radio) 的選項文字進行「強制增亮」 */
    /* 這是修正「學生 (個人晤談)」與「家長 (親師聯繫)」看不清楚的關鍵 */
    div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] p {
        color: #FFFFFF !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        opacity: 1 !important;
    }

    /* 3. 針對文字區域的標題 (事實描述...) 進行額外補強 */
    .stTextArea label p {
        color: #FFFFFF !important;
    }

    /* 其他視覺調整 */
    .main-header { 
        text-align: center; 
        color: #88c0d0;
        font-weight: 700; 
        font-size: 2.8rem; 
        margin-bottom: 2rem; 
    }
    
    .record-box { 
        background-color: #2e3440; 
        padding: 25px; 
        border-radius: 15px; 
        border: 1px solid #434c5e; 
        margin-bottom: 15px;
        line-height: 1.8; 
    }
    
    .stTabs [aria-selected="true"] { 
        background-color: #88c0d0 !important; 
        color: #2e3440 !important; 
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)

tab_input, tab_history, tab_report = st.tabs(["📝 導師紀錄錄入與分析", "🔍 班級個案歷程追蹤", "📊 個人觀察彙整筆記"])

# --- TAB 1: 紀錄錄入 ---
with tab_input:
    st.markdown("### ✍️ 第一步：觀察錄入與功能選擇")
    
    # 排版與輸入
    row1_c1, row1_c2, row1_c3 = st.columns([1.3, 1, 1])
    with row1_c1:
        # 這裡就是您提到的「學生 (個人晤談)」與「家長 (親師聯繫)」
        target_type = st.radio("對象：", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with row1_c2:
        stu_id = st.text_input("學生代號", placeholder="例如：702-05")
    with row1_c3:
        category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    raw_obs = st.text_area("事實描述或晤談紀錄摘要：", height=250, placeholder="在此輸入觀察事實...")
    
    # 功能按鈕
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1])
    with btn_col1:
        gen_formal = st.button("📁 1. 生成優化紀錄文稿", use_container_width=True)
    with btn_col2:
        if "學生" in target_type:
            gen_plan = st.button("🎯 2. 生成後續觀察重點", use_container_width=True)
        else:
            gen_line = st.button("💬 2. 撰寫親師合作訊息", use_container_width=True)
    with btn_col3:
        save_hub = st.button("💾 3. 同步至雲端個人手冊", use_container_width=True)

    st.divider()

    # --- 下方：AI 分析結果區 ---
    st.markdown("### ✨ 第二步：導師輔助分析結果")
    res_col1, res_col2 = st.columns(2, gap="large")
    
    if gen_formal and raw_obs:
        with st.spinner("優化筆記中..."):
            prompt = f"你是一位班級導師，請將以下筆記轉化為專業客觀的「導師觀察紀錄」：\n{raw_obs}"
            st.session_state.analysis_1 = ai_engine.generate_content(prompt).text
    
    if 'analysis_1' in st.session_state:
        with res_col1:
            st.markdown("##### 📋 建議紀錄文稿")
            st.markdown(f'<div class="record-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
            
    if "學生" in target_type and 'gen_plan' in locals() and gen_plan and raw_obs:
        with st.spinner("分析觀察重點中..."):
            st.session_state.analysis_2 = ai_engine.generate_content(f"身為導師，請針對此內容提供後續觀察重點：\n{raw_obs}").text
    
    if "家長" in target_type and 'gen_line' in locals() and gen_line and raw_obs:
        with st.spinner("擬定訊息中..."):
            st.session_state.analysis_2 = ai_engine.generate_content(f"請以導師身份，撰寫一段溫馨的親師聯繫訊息：\n{raw_obs}").text

    if 'analysis_2' in st.session_state:
        with res_col2:
            st.markdown(f"##### {'🎯 導師行動建議' if '學生' in target_type else '🟢 親師合作草稿'}")
            if "家長" in target_type: st.code(st.session_state.analysis_2, language="text")
            else: st.markdown(f'<div class="record-box" style="border-left: 5px solid #88c0d0;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

    # 儲存邏輯
    if save_hub:
        if stu_id and ( 'analysis_1' in st.session_state or 'analysis_2' in st.session_state ):
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, target_type, category, raw_obs, f"{st.session_state.get('analysis_1','')}\n\n{st.session_state.get('analysis_2','')}"])
                st.balloons()
                st.success("✅ 紀錄已成功存入個人 Hub")
                for k in ['analysis_1', 'analysis_2']: 
                    if k in st.session_state: del st.session_state[k]
            except Exception as e: st.error(f"儲存失敗：{e}")

# --- TAB 2 & 3 ---
with tab_history:
    st.markdown("### 🔍 班級學生輔導歷程檢索")
    search_id = st.text_input("輸入學生代號查詢：")
    if search_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            records = sheet.get_all_records()
            matches = [r for r in records if str(r.get('學生代號', '')) == search_id]
            if matches:
                for r in matches[::-1]:
                    with st.expander(f"📅 {r.get('日期')} | {r.get('對象')}"):
                        st.markdown(f"<div class='record-box'>{r.get('AI 分析結果')}</div>", unsafe_allow_html=True)
            else: st.warning("查無紀錄。")
        except: st.error("查詢異常")

with tab_report:
    st.markdown("### 📊 導師觀察彙整")
    if st.button("🔄 更新數據"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                st.metric("本班累積案量", len(df))
                st.bar_chart(df['類別'].value_counts())
        except: st.error("數據異常")
