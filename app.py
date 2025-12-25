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

st.set_page_config(page_title="智慧輔導系統 v1.8.3", layout="wide", page_icon="🛡️")

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
    col_l, col_m, col_r = st.columns([1, 1.5, 1])
    with col_m:
        st.markdown('<div style="text-align: center; background-color: #2e3440; padding: 30px; border-radius: 15px; border: 1px solid #88c0d0;"><h2 style="color: #88c0d0;">🔐 校內人員驗證</h2></div>', unsafe_allow_html=True)
        st.text_input("請輸入專屬授權碼：", type="password", key="pwd_input", on_change=check_password)
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

# --- 4. 視覺風格 ---
st.markdown("""
    <style>
    .block-container { max-width: 1200px !important; margin: auto; padding-top: 1rem; }
    .stApp { background-color: #1a1d24; color: #eceff4; }
    .main-header { text-align: center; background: linear-gradient(120deg, #88c0d0 0%, #a3be8c 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 600; font-size: 2.2rem; margin-bottom: 2rem; }
    .record-box { background-color: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #4c566a; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師溝通系統</h1>', unsafe_allow_html=True)

tab_input, tab_history, tab_report = st.tabs(["📝 紀錄錄入與 AI 分析", "🔍 個案歷程追蹤", "📊 數據中樞與月報表"])

# --- TAB 1: 紀錄錄入 ---
with tab_input:
    col_in, col_out = st.columns([1, 1.2])
    with col_in:
        st.subheader("📝 晤談與觀察錄入")
        target_type = st.radio("【第一步】請選擇晤談對象：", ["學生 (個案晤談)", "家長 (親師溝通)"], horizontal=True)
        stu_id = st.text_input("學生代號", placeholder="例如：702-05")
        category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
        raw_obs = st.text_area("晤談或事實描述：", height=250)
        
        btn_col1, btn_col2 = st.columns(2)
        if "學生" in target_type:
            with btn_col1: gen_formal = st.button("📁 生成專業晤談紀錄")
            with btn_col2: gen_plan = st.button("🎯 生成輔導計畫建議")
        else:
            with btn_col1: gen_formal = st.button("📁 生成專業親師紀錄")
            with btn_col2: gen_line = st.button("💬 生成 LINE 草稿")

    with col_out:
        if gen_formal and raw_obs:
            with st.spinner("AI 轉譯中..."):
                role_desc = "輔導老師針對學生的晤談摘要" if "學生" in target_type else "導師與家長的通聯紀錄"
                prompt = f"你是一位專業輔導老師，請將以下內容轉化為「{role_desc}」，要求客觀中立、包含心理動機分析：\n{raw_obs}"
                st.session_state.analysis_1 = ai_engine.generate_content(prompt).text
        
        if "學生" in target_type and 'gen_plan' in locals() and gen_plan and raw_obs:
            with st.spinner("計畫生成中..."):
                st.session_state.analysis_2 = ai_engine.generate_content(f"身為專業輔導員，請給予「下階段輔導計畫」建議：\n{raw_obs}").text
        
        if "家長" in target_type and 'gen_line' in locals() and gen_line and raw_obs:
            with st.spinner("草稿撰寫中..."):
                st.session_state.analysis_2 = ai_engine.generate_content(f"請撰寫一段溫柔專業、強調親師合作的 LINE 訊息：\n{raw_obs}").text

        if 'analysis_1' in st.session_state:
            st.markdown(f"##### 📁 專業分析紀錄")
            st.markdown(f'<div class="record-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
        if 'analysis_2' in st.session_state:
            st.markdown(f"##### {'🎯 計畫建議' if '學生' in target_type else '🟢 LINE 草稿'}")
            if "家長" in target_type: st.code(st.session_state.analysis_2, language="text")
            else: st.markdown(f'<div class="record-box" style="border-left: 5px solid #88c0d0;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

    st.divider()
    if st.button("💾 同步至雲端 Hub"):
        if stu_id and ( 'analysis_1' in st.session_state or 'analysis_2' in st.session_state ):
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                an1 = st.session_state.get('analysis_1', 'N/A')
                an2 = st.session_state.get('analysis_2', 'N/A')
                # 對齊校長的欄位順序：日期, 學生代號, 對象, 類別, 原始觀察描述, AI 分析結果
                sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, target_type, category, raw_obs, f"{an1}\n\n{an2}"])
                st.balloons()
                st.success(f"✅ 紀錄已存入 Hub")
                for k in ['analysis_1', 'analysis_2']: 
                    if k in st.session_state: del st.session_state[k]
            except Exception as e: st.error(f"儲存失敗：{e}")

# --- TAB 2: 個案歷程追蹤 (精準對齊校長欄位) ---
with tab_history:
    st.subheader("🔍 個案歷史紀錄追蹤")
    search_id = st.text_input("輸入學生代號查詢：", key="case_search_final")
    
    if search_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            # 使用 get_all_records 直接以標題名稱對應，避免位置錯誤
            records = sheet.get_all_records()
            
            if records:
                # 篩選代號符合的紀錄
                matches = [r for r in records if str(r.get('學生代號', '')) == search_id]
                
                if matches:
                    st.info(f"找到 {len(matches)} 筆歷史紀錄")
                    for r in matches[::-1]: # 最新到舊
                        # 使用校長提供的確切欄位名稱
                        date = r.get('日期', '未知時間')
                        target = r.get('對象', '未指定')
                        cat = r.get('類別', '未分類')
                        obs = r.get('原始觀察描述', '無描述內容')
                        result = r.get('AI 分析結果', '無分析結果')
                        
                        with st.expander(f"📅 {date} | {target} | {cat}"):
                            st.markdown("**【原始觀察描述】**")
                            st.write(obs)
                            st.divider()
                            st.markdown("**【AI 分析結果】**")
                            st.write(result)
                else:
                    st.warning(f"查無代號 {search_id} 的紀錄。")
            else:
                st.info("雲端資料庫目前為空。")
        except Exception as e: 
            st.error(f"查詢異常：{e}")

# --- TAB 3: 月報表 ---
with tab_report:
    st.subheader("📊 數據大數據彙整")
    if st.button("🔄 重新整理報表"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                st.metric("累積總案量", len(df))
                if '類別' in df.columns:
                    st.write("事件類別分析")
                    st.bar_chart(df['類別'].value_counts())
                if '對象' in df.columns:
                    st.write("輔導對象佔比")
                    st.write(df['對象'].value_counts())
            else: st.info("尚無數據可分析。")
        except Exception as e: st.error(f"報表異常：{e}")
