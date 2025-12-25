import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心安全與連線設定 (功能完全維持) ---
AUTH_CODE = "1225"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導紀錄系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格優化 (限制寬度、高對比、顏色標籤) ---
st.markdown("""
    <style>
    .block-container { max-width: 1000px !important; padding-top: 2rem !important; margin: auto; }
    .stApp { background-color: #1a1c23; color: #e5e9f0; }
    
    /* 標籤純白加粗 */
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
    }
    
    div[data-testid="stRadio"] label div[data-testid="stMarkdownContainer"] p {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }

    .main-header { 
        text-align: center; 
        background: linear-gradient(90deg, #88c0d0, #5e81ac);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800; font-size: 2.5rem; margin-bottom: 2rem;
    }

    .stTextArea textarea { background-color: #2e3440 !important; color: #ffffff !important; border: 1px solid #4c566a !important; }
    
    /* 輔助顏色標籤樣式 */
    .tag-urgent { color: #ff6b6b; font-weight: bold; }
    .tag-normal { color: #88c0d0; }
    .tag-support { color: #ffd93d; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 驗證邏輯 (無 rerun 警告版) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col_m, _ = st.columns([1, 1.5, 1])
    with col_m:
        st.markdown("<div style='text-align:center; background-color:#2e3440; padding:40px; border-radius:20px; border-top:5px solid #88c0d0;'><h1>🔐</h1><h2 style='color:#88c0d0;'>導師身分驗證</h2></div>", unsafe_allow_html=True)
        pwd_input = st.text_input("授權碼：", type="password")
        if pwd_input == AUTH_CODE:
            st.session_state.authenticated = True
            st.rerun()
        elif pwd_input: st.error("❌ 授權碼錯誤")
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
        st.error(f"連線異常：{e}")
        return None, None

ai_engine, hub_engine = init_all_services()

# --- 5. 主程式介面 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)
tab_input, tab_history, tab_report = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

with tab_input:
    st.markdown("### ✍️ 第一步：觀察錄入與功能選擇")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with c2: stu_id = st.text_input("【學生代號】", placeholder="例如：809-01")
    with c3: category = st.selectbox("【事件類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    # [建議 2]: 快速錄入標籤
    quick_tags = st.multiselect("💡 快速標籤 (點選後可自動加入下方內容)", ["表現優異", "情緒波動", "學習退步", "同儕糾紛", "家長已讀", "建議介入"])
    tag_str = " ".join([f"[{t}]" for t in quick_tags])
    
    raw_obs = st.text_area("【事實描述或晤談紀錄摘要】", value=tag_str if tag_str else "", height=250, placeholder="在此輸入觀察事實... (建議：可使用手機語音輸入)")
    
    # [建議 4]: 去識別化機制
    is_private = st.checkbox("🔒 機密紀錄 (存檔時隱藏原始事實，僅保留 AI 分析結果)")

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
        with st.spinner("AI 處理中..."):
            st.session_state.analysis_1 = ai_engine.generate_content(f"身為導師，請優化以下紀錄：\n{raw_obs}").text
    
    if 'analysis_1' in st.session_state:
        with res_l:
            st.info("📋 **建議紀錄文稿**")
            st.markdown(f'<div style="background-color:#2e3440; padding:20px; border-radius:15px; border:1px solid #4c566a; line-height:1.7;">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
            # [建議 3]: 匯出功能
            st.download_button("📥 下載此份正式文稿 (.txt)", data=st.session_state.analysis_1, file_name=f"{stu_id}_觀察紀錄.txt")

    if 'analysis_2' in st.session_state:
        with res_r:
            st.success(f"🎯 **{'導師行動建議' if '學生' in target_type else '親師合作草稿'}**")
            if "家長" in target_type: st.code(st.session_state.analysis_2)
            else: st.markdown(f'<div style="background-color:#2e3440; padding:20px; border-radius:15px; border-left:5px solid #88c0d0; line-height:1.7;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

    if save_hub and stu_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            # 處理隱私模式
            fact_to_save = "[內容已去識別化保護]" if is_private else raw_obs
            sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), stu_id, target_type, category, fact_to_save, f"{st.session_state.get('analysis_1','')}\n\n{st.session_state.get('analysis_2','')}"])
            st.balloons(); st.success("✅ 紀錄已成功存入雲端 Hub")
            for k in ['analysis_1', 'analysis_2']: 
                if k in st.session_state: del st.session_state[k]
        except Exception as e: st.error(f"儲存失敗：{e}")

with tab_history:
    st.markdown("### 🔍 班級個案歷程查詢")
    search_id = st.text_input("輸入代號查詢 (例：809-01)：")
    if search_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            records = sheet.get_all_records()
            matches = [r for r in records if str(r.get('學生代號', '')) == search_id]
            for r in matches[::-1]:
                # [建議 1]: 顏色與標籤區分
                icon = "🚨" if r.get('類別') == "緊急事件" else "💡"
                with st.expander(f"{icon} {r.get('日期')} | {r.get('類別')}"):
                    st.write(f"**對象：** {r.get('對象')}")
                    st.write(f"**事實：** {r.get('事實描述')}")
                    st.markdown(f"<div style='background-color:#2e3440; padding:15px; border-radius:10px;'>{r.get('AI 分析結果')}</div>", unsafe_allow_html=True)
        except: st.error("讀取異常")

with tab_report:
    st.markdown("### 📊 班級數據統計")
    if st.button("🔄 更新統計圖表"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            st.metric("累積輔導筆數", len(df))
            st.bar_chart(df['類別'].value_counts())
        except: st.error("統計失敗")
