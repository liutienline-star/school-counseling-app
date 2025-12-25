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
MODEL_NAME = "models/gemini-2.0-flash" 

st.set_page_config(page_title="智慧輔導紀錄系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格優化 (維持校長風格) ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; margin: auto; }
    .stApp { background-color: #1a1c23; color: #e5e9f0; }
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p { color: #FFFFFF !important; font-weight: 700 !important; font-size: 1.15rem !important; }
    .main-header { text-align: center; background: linear-gradient(90deg, #88c0d0, #5e81ac); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 2.5rem; margin-bottom: 2rem; }
    .result-box { background-color: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #4c566a; min-height: 300px; margin-top: 10px; white-space: pre-wrap; }
    .risk-badge { padding: 5px 15px; border-radius: 20px; font-weight: 800; font-size: 0.9rem; margin-bottom: 10px; display: inline-block; }
    .risk-high { background-color: #bf616a; color: white; border: 1px solid #ff0000; }
    .risk-med { background-color: #ebcb8b; color: #2e3440; }
    .risk-low { background-color: #a3be8c; color: white; }
    .stTextArea textarea { background-color: #2e3440 !important; color: #ffffff !important; border: 1px solid #4c566a !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 驗證邏輯 ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    _, col_m, _ = st.columns([1, 1.5, 1])
    with col_m:
        st.markdown("<div style='text-align:center; background-color:#2e3440; padding:40px; border-radius:20px;'><h1>🔐</h1><h2 style='color:#88c0d0;'>導師身分驗證</h2></div>", unsafe_allow_html=True)
        if st.text_input("授權碼：", type="password") == AUTH_CODE:
            st.session_state.authenticated = True
            st.rerun()
    st.stop()

# --- 4. 初始化服務 ---
@st.cache_resource
def init_services():
    try:
        genai.configure(api_key=st.secrets["gemini"]["api_key"])
        model = genai.GenerativeModel(MODEL_NAME)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return model, gspread.authorize(creds)
    except Exception as e:
        st.error(f"連線異常：{e}"); return None, None

ai_engine, hub_engine = init_services()

# --- 5. 主介面 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)
tab_input, tab_history, tab_report = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

if 'analysis_1' not in st.session_state: st.session_state.analysis_1 = ""
if 'analysis_2' not in st.session_state: st.session_state.analysis_2 = ""
if 'risk_level' not in st.session_state: st.session_state.risk_level = "低"

with tab_input:
    st.markdown("### ✍️ 第一步：觀察錄入與功能選擇")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with c2: stu_id = st.text_input("【學生代號】", placeholder="例如：809-01")
    with c3: category = st.selectbox("【事件類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    raw_obs = st.text_area("【事實描述或晤談紀錄摘要】", height=200)
    is_private = st.checkbox("🔒 機密紀錄模式 (隱藏事實描述)")

    st.markdown("<br>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    
    if b1.button("📁 1. 生成優化紀錄文稿"):
        st.session_state.analysis_1 = ai_engine.generate_content(f"請優化為正式、客觀的輔導紀錄：\n{raw_obs}").text

    if b2.button("🎯 2. 生成分析與建議"):
        with st.spinner("撰寫中..."):
            if "學生" in target_type:
                prompt = (f"請分析內容。第一行標註：【風險等級：高/中/低】。\n"
                          f"分析要求：1.風險評估。2.提供1-3項具體行動建議。內容：\n{raw_obs}")
            else:
                # --- 【核心修正】：調整親師訊息的語氣為「溫潤專業版」 ---
                prompt = (f"請分析以下內容。第一行標註：【風險等級：高/中/低】。\n"
                          f"分析要求：\n"
                          f"1. 提供導師面對家長或此事件的『初步處理行動建議』(1-3點)。\n"
                          f"2. 撰寫一份『給家長的溝通訊息』：\n"
                          f"   - 【語氣規範】：溫潤、有溫度、展現專業關懷。不要像公文，也不要太隨便。\n"
                          f"   - 【內容結構】：\n"
                          f"     a. 先簡單肯定孩子（破冰）。\n"
                          f"     b. 以關心的視角敘述當前觀察到的現象或事件。\n"
                          f"     c. 邀請家長一同觀察或合作，並結尾表示感謝與支持。\n\n"
                          f"內容如下：\n{raw_obs}")
            
            res_text = ai_engine.generate_content(prompt).text
            st.session_state.analysis_2 = res_text
            
            # 解析風險等級
            first_line = res_text.split('\n')[0]
            if "高" in first_line: st.session_state.risk_level = "高"
            elif "中" in first_line: st.session_state.risk_level = "中"
            else: st.session_state.risk_level = "低"

    if b3.button("💾 3. 同步至雲端手冊", type="primary"):
        if stu_id:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                fact = "[機密]" if is_private else raw_obs
                sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    stu_id, target_type, category, 
                    st.session_state.risk_level, 
                    fact, 
                    f"{st.session_state.analysis_1}\n\n{st.session_state.analysis_2}" 
                ])
                st.balloons(); st.success("✅ 已成功同步")
            except Exception as e: st.error(f"同步失敗：{e}")
        else: st.error("❌ 請輸入代號")

    st.divider()
    st.markdown("### ✨ 第二步：導師輔助分析結果")
    res_c1, res_c2 = st.columns(2)
    with res_c1:
        st.markdown("**📋 優化文稿**")
        st.markdown(f'<div class="result-box">{st.session_state.analysis_1 or "等待生成..."}</div>', unsafe_allow_html=True)
    with res_c2:
        st.markdown("**🎯 行動建議與親師訊息**")
        risk_color = "risk-high" if st.session_state.risk_level == "高" else ("risk-med" if st.session_state.risk_level == "中" else "risk-low")
        st.markdown(f'<div class="risk-badge {risk_color}">⚠️ 風險評估：{st.session_state.risk_level}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-box" style="border-left:5px solid #88c0d0;">{st.session_state.analysis_2 or "等待生成..."}</div>', unsafe_allow_html=True)

# --- 歷史與統計 (維持不變) ---
with tab_history:
    st.markdown("### 🔍 個案歷程查詢")
    q_id = st.text_input("輸入代號：")
    if q_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            recs = sheet.get_all_records()
            matches = [r for r in recs if str(r.get('學生代號','')) == q_id]
            for r in matches[::-1]:
                with st.expander(f"📅 {r.get('日期')} | {r.get('類別')} (風險：{r.get('風險等級')})"):
                    st.write(f"事實：{r.get('事實描述')}")
                    st.info(f"AI：\n{r.get('AI 分析結果')}")
        except: st.error("查詢失敗")

with tab_report:
    if st.button("🔄 更新統計圖表"):
        try:
            df = pd.DataFrame(hub_engine.open(HUB_NAME).worksheet(SHEET_TAB).get_all_records())
            st.bar_chart(df['類別'].value_counts())
        except: st.error("統計失敗")
