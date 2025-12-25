import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心安全與連線設定 (功能不變) ---
AUTH_CODE = "1225"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

# 修改標題與版面寬度
st.set_page_config(page_title="智慧輔導紀錄與親師生溝通系統", layout="wide", page_icon="🏫")

# --- 2. 驗證邏輯 (功能不變) ---
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
                <h2 style="color: #88c0d0;">🔐 校內人員驗證</h2>
                <p style="color: #d8dee9;">請輸入授權碼以存取親師生溝通系統</p>
            </div>
        """, unsafe_allow_html=True)
        st.text_input("授權碼：", type="password", key="pwd_input", on_change=check_password)
        st.stop()

# --- 3. 初始化服務 (功能不變) ---
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

# --- 4. 視覺風格優化 (視覺重塑區) ---
st.markdown("""
    <style>
    /* 1. 寬幅容器優化 */
    .block-container { 
        max-width: 1400px !important; 
        padding-top: 2rem; 
        padding-bottom: 5rem; 
    }
    
    /* 2. 背景與文字調色 (護眼深藍灰) */
    .stApp { 
        background-color: #242933; 
        color: #d8dee9; 
    }
    
    /* 3. 主標題視覺 */
    .main-header { 
        text-align: center; 
        color: #88c0d0;
        font-weight: 700; 
        font-size: 2.8rem; 
        margin-bottom: 3rem; 
        letter-spacing: 1px;
    }
    
    /* 4. 紀錄方框 (增加行高與呼吸感) */
    .record-box { 
        background-color: #2e3440; 
        padding: 25px; 
        border-radius: 15px; 
        border: 1px solid #434c5e; 
        margin-bottom: 15px;
        line-height: 1.8; /* 提高閱讀舒適度 */
        font-size: 1.05rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 5. 分頁 Tab 優化 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #3b4252;
        border-radius: 10px 10px 0 0;
        color: #d8dee9;
        padding: 0 25px;
        font-size: 1.1rem;
    }
    .stTabs [aria-selected="true"] { 
        background-color: #88c0d0 !important; 
        color: #2e3440 !important; 
        font-weight: bold;
    }
    
    /* 6. 輸入區域高度優化 */
    .stTextArea textarea { line-height: 1.6; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)

# 側邊欄簡化
st.sidebar.markdown(f"**🟢 系統已授權**")
if st.sidebar.button("登出系統"):
    st.session_state.authenticated = False
    st.rerun()

tab_input, tab_history, tab_report = st.tabs(["📝 紀錄錄入與智慧分析", "🔍 個案歷程追蹤回溯", "📊 行政數據中樞"])

# --- TAB 1: 紀錄錄入 (佈局加寬) ---
with tab_input:
    col_in, col_out = st.columns([1, 1.2], gap="large")
    with col_in:
        st.markdown("### ✍️ 晤談與觀察錄入")
        target_type = st.radio("【第一步】請選擇晤談對象：", ["學生 (個案晤談)", "家長 (親師溝通)"], horizontal=True)
        
        c1, c2 = st.columns(2)
        with c1: stu_id = st.text_input("學生代號", placeholder="例如：702-05")
        with c2: category = st.selectbox("事件類別", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
        
        raw_obs = st.text_area("事實描述或晤談摘要：", height=350, placeholder="在此詳細輸入觀察到的狀況或晤談重點...")
        
        st.markdown("<br>", unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns(2)
        if "學生" in target_type:
            with btn_col1: gen_formal = st.button("📁 生成專業晤談紀錄")
            with btn_col2: gen_plan = st.button("🎯 生成輔導計畫建議")
        else:
            with btn_col1: gen_formal = st.button("📁 生成專業親師紀錄")
            with btn_col2: gen_line = st.button("💬 生成 LINE 草稿")

    with col_out:
        st.markdown("### ✨ AI 智慧轉譯結果")
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
            st.markdown(f"##### 📁 專業分析文稿")
            st.markdown(f'<div class="record-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
        if 'analysis_2' in st.session_state:
            st.markdown(f"##### {'🎯 計畫建議' if '學生' in target_type else '🟢 LINE 草稿建議'}")
            if "家長" in target_type: st.code(st.session_state.analysis_2, language="text")
            else: st.markdown(f'<div class="record-box" style="border-left: 5px solid #88c0d0;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

    st.divider()
    if st.button("💾 同步至雲端 Hub 資料庫"):
        if stu_id and ( 'analysis_1' in st.session_state or 'analysis_2' in st.session_state ):
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                an1 = st.session_state.get('analysis_1', 'N/A')
                an2 = st.session_state.get('analysis_2', 'N/A')
                sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, target_type, category, raw_obs, f"{an1}\n\n{an2}"])
                st.balloons()
                st.success(f"✅ 紀錄已成功存入 Hub")
                for k in ['analysis_1', 'analysis_2']: 
                    if k in st.session_state: del st.session_state[k]
            except Exception as e: st.error(f"儲存失敗：{e}")

# --- TAB 2: 個案歷程追蹤 (強化閱讀體驗) ---
with tab_history:
    st.markdown("### 🔍 個案歷史紀錄檢索")
    search_id = st.text_input("輸入學生代號查詢 (回車鍵搜尋)：", key="case_search_v2")
    
    if search_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            records = sheet.get_all_records()
            
            if records:
                matches = [r for r in records if str(r.get('學生代號', '')) == search_id]
                
                if matches:
                    st.info(f"📍 找到 {len(matches)} 筆關於 {search_id} 的歷史輔導紀錄")
                    for r in matches[::-1]:
                        with st.expander(f"📅 {r.get('日期')} | {r.get('對象')} | {r.get('類別')}", expanded=False):
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown("**【原始觀察描述】**")
                                st.write(r.get('原始觀察描述'))
                            with col_b:
                                st.markdown("**【AI 分析結果】**")
                                st.markdown(f"<div style='background-color:#3b4252; padding:15px; border-radius:10px;'>{r.get('AI 分析結果')}</div>", unsafe_allow_html=True)
                else:
                    st.warning(f"查無代號 {search_id} 的紀錄。")
            else:
                st.info("資料庫目前尚無數據。")
        except Exception as e: 
            st.error(f"查詢異常：{e}")

# --- TAB 3: 行政月報表 ---
with tab_report:
    st.markdown("### 📊 全校輔導行政數據摘要")
    if st.button("🔄 重新整理統計數據"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            if not df.empty:
                c_m1, c_m2 = st.columns([1, 2])
                with c_m1:
                    st.metric("累積輔導總案量", len(df))
                    st.write("輔導對象佔比")
                    st.write(df['對象'].value_counts())
                with c_m2:
                    st.write("事件類別統計趨勢")
                    st.bar_chart(df['類別'].value_counts())
            else: st.info("尚無數據可分析。")
        except Exception as e: st.error(f"報表異常：{e}")
