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

st.set_page_config(page_title="智慧輔導系統 v1.7 | 雙軌優化版", layout="wide", page_icon="🛡️")

# --- 2. 驗證邏輯 ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state["pwd_input"] == AUTH_CODE:
        st.session_state.authenticated = True
        st.rerun()
    else:
        st.error("❌ 授權碼錯誤，請洽詢系統管理員。")

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
    .main-header {
        text-align: center; background: linear-gradient(120deg, #88c0d0 0%, #a3be8c 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 600; font-size: 2.2rem; margin-bottom: 2rem;
    }
    .record-box { background-color: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #4c566a; }
    .target-label { font-size: 1.2rem; font-weight: bold; color: #88c0d0; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 5. 主介面 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師溝通系統</h1>', unsafe_allow_html=True)

st.sidebar.success(f"🔑 已授權存取")
if st.sidebar.button("登出系統"):
    st.session_state.authenticated = False
    st.rerun()

tab_input, tab_report = st.tabs(["📝 紀錄錄入與 AI 分析", "📊 數據中樞與月報表"])

# --- TAB 1: 錄入分頁 ---
with tab_input:
    col_in, col_out = st.columns([1, 1.2])
    
    with col_in:
        st.subheader("📝 晤談與觀察錄入")
        
        # 新增對象選擇
        target_type = st.radio("【第一步】請選擇晤談對象：", ["學生 (個案晤談)", "家長 (親師溝通)"], horizontal=True)
        
        stu_id = st.text_input("學生代號", placeholder="例如：702-05")
        category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
        raw_obs = st.text_area("晤談或事實描述：", height=250, placeholder="請輸入本次對話或觀察到的重點...")
        
        st.markdown("---")
        # 根據對象顯示不同按鈕
        btn_col1, btn_col2 = st.columns(2)
        
        if "學生" in target_type:
            with btn_col1: gen_formal = st.button("📁 生成專業晤談紀錄")
            with btn_col2: gen_plan = st.button("🎯 生成輔導計畫建議")
        else:
            with btn_col1: gen_formal = st.button("📁 生成專業親師紀錄")
            with btn_col2: gen_line = st.button("💬 生成 LINE 溝通草稿")

    with col_out:
        # A. 生成正式紀錄邏輯 (共用)
        if gen_formal and raw_obs:
            with st.spinner("AI 轉譯專業格式中..."):
                role_desc = "輔導老師針對學生的晤談摘要" if "學生" in target_type else "導師與家長的通聯紀錄"
                prompt = f"你是一位專業輔導老師，請將以下內容轉化為「{role_desc}」，要求客觀中立、包含心理動機分析：\n{raw_obs}"
                st.session_state.analysis_1 = ai_engine.generate_content(prompt).text
        
        # B. 學生專屬：輔導計畫
        if "學生" in target_type and 'gen_plan' in locals() and gen_plan and raw_obs:
            with st.spinner("生成輔導計畫建議..."):
                prompt = f"身為專業輔導員，針對此學生的對話內容，請給予導師具體的「下階段輔導計畫」與「班級經營建議」：\n{raw_obs}"
                st.session_state.analysis_2 = ai_engine.generate_content(prompt).text
        
        # C. 家長專屬：LINE草稿
        if "家長" in target_type and 'gen_line' in locals() and gen_line and raw_obs:
            with st.spinner("撰寫 LINE 草稿中..."):
                prompt = f"請撰寫一段適合傳給家長的 LINE 訊息。語氣溫柔、強調親師合作、具體轉達事件並提出共同協助的邀請：\n{raw_obs}"
                st.session_state.analysis_2 = ai_engine.generate_content(prompt).text

        # 顯示結果
        if 'analysis_1' in st.session_state:
            label = "📁 專業晤談紀錄" if "學生" in target_type else "📁 親師通聯專業紀錄"
            st.markdown(f"##### {label}")
            st.markdown(f'<div class="record-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
            
        if 'analysis_2' in st.session_state:
            label = "🎯 下階段輔導計畫建議" if "學生" in target_type else "🟢 LINE 親師溝通金句"
            st.markdown(f"##### {label}")
            if "家長" in target_type:
                st.code(st.session_state.analysis_2, language="text")
            else:
                st.markdown(f'<div class="record-box" style="border-left: 5px solid #88c0d0;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

    st.divider()
    # 儲存邏輯修改
    if st.button("💾 同步至雲端 Hub"):
        if stu_id and ( 'analysis_1' in st.session_state or 'analysis_2' in st.session_state ):
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                an1 = st.session_state.get('analysis_1', 'N/A')
                an2 = st.session_state.get('analysis_2', 'N/A')
                # 存入時增加「對象」欄位，方便區分
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                sheet.append_row([now_str, stu_id, target_type, category, raw_obs, f"{an1}\n\n{an2}"])
                st.balloons()
                st.success(f"✅ {target_type}紀錄已成功存入 Hub！")
                if 'analysis_1' in st.session_state: del st.session_state.analysis_1
                if 'analysis_2' in st.session_state: del st.session_state.analysis_2
            except Exception as e: st.error(f"儲存失敗：{e}")

# --- TAB 2: 月報表 (增加對象分析) ---
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
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write("各類別件數")
                        st.bar_chart(this_month_df['類別'].value_counts())
                    with c2:
                        st.write("對象佔比")
                        # 這裡修正如果沒有對象欄位的舊資料處理
                        if '對象' in this_month_df.columns:
                            st.write(this_month_df['對象'].value_counts())
                        else:
                            st.info("舊有資料無對象標籤")
                    with c3:
                        st.metric("本月累計總案量", len(this_month_df))
                    
                    st.divider()
                    report_res = ai_engine.generate_content(f"請根據本月數據給予校長三點行政管理建議：{this_month_df.to_string()}")
                    st.success(report_res.text)
                else: st.info("本月暫無數據。")
        except Exception as e: st.error(f"報表異常：{e}")
