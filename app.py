import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 設定 ---
AUTH_CODE = "641101"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.0-flash" 

st.set_page_config(page_title="智慧輔導紀錄系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格 (校長風格) ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; margin: auto; }
    .stApp { background-color: #1a1c23; color: #e5e9f0; }
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p { color: #FFFFFF !important; font-weight: 700 !important; font-size: 1.15rem !important; }
    .main-header { text-align: center; background: linear-gradient(90deg, #88c0d0, #5e81ac); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 2.5rem; margin-bottom: 2rem; }
    .result-box { background-color: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #4c566a; min-height: 300px; margin-top: 10px; white-space: pre-wrap; color: #ffffff; }
    .risk-badge { padding: 5px 15px; border-radius: 20px; font-weight: 800; font-size: 0.9rem; margin-bottom: 10px; display: inline-block; }
    .risk-high { background-color: #bf616a; color: white; border: 1px solid #ff0000; }
    .risk-med { background-color: #ebcb8b; color: #2e3440; }
    .risk-low { background-color: #a3be8c; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 驗證邏輯 ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    _, col_m, _ = st.columns([1, 1.5, 1])
    with col_m:
        st.markdown("<h2 style='text-align:center;'>🔐 導師驗證</h2>", unsafe_allow_html=True)
        if st.text_input("授權碼：", type="password") == AUTH_CODE:
            st.session_state.authenticated = True
            st.rerun()
    st.stop()

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

# --- 4. 主介面邏輯 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)
tab_input, tab_history, tab_report = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

if 'analysis_1' not in st.session_state: st.session_state.analysis_1 = ""
if 'analysis_2' not in st.session_state: st.session_state.analysis_2 = ""
if 'risk_level' not in st.session_state: st.session_state.risk_level = "低"

with tab_input:
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with c2: stu_id = st.text_input("【學生代號】")
    with c3: category = st.selectbox("【類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    raw_obs = st.text_area("【事實描述摘要】", height=150)
    is_private = st.checkbox("🔒 機密模式 (雲端僅存入 [機密])")

    col_b1, col_b2, col_b3 = st.columns(3)
    if col_b1.button("📁 1. 生成優化紀錄文稿"):
        st.session_state.analysis_1 = ai_engine.generate_content(f"請優化為正式輔導紀錄：{raw_obs}").text
        
    if col_b2.button("🎯 2. 生成分析與建議"):
        with st.spinner("分析中..."):
            prompt = (f"分析內容並於第一行標註：【風險等級：高/中/低】。\n"
                      f"隨後提供『行動建議』與一份『語氣溫潤且關懷的親師訊息』。內容：{raw_obs}")
            res = ai_engine.generate_content(prompt).text
            st.session_state.analysis_2 = res
            if "高" in res.split('\n')[0]: st.session_state.risk_level = "高"
            elif "中" in res.split('\n')[0]: st.session_state.risk_level = "中"
            else: st.session_state.risk_level = "低"

    if col_b3.button("💾 3. 同步至雲端手冊", type="primary"):
        if stu_id:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                fact_to_save = "[機密紀錄]" if is_private else raw_obs
                # --- 精準對齊 7 欄位 A-G ---
                row_data = [
                    datetime.now().strftime("%Y/%m/%d %H:%M"), # A: 日期
                    stu_id,                                    # B: 學生代號
                    target_type,                               # C: 對象類型
                    category,                                  # D: 類別
                    st.session_state.risk_level,               # E: 風險等級
                    fact_to_save,                              # F: 原始觀察描述
                    f"{st.session_state.analysis_1}\n\n{st.session_state.analysis_2}" # G: AI分析結果
                ]
                sheet.append_row(row_data)
                st.success("✅ 資料已同步！")
            except Exception as e: st.error(f"同步失敗：{e}")
        else: st.error("請輸入學生代號")

    res_c1, res_c2 = st.columns(2)
    with res_c1:
        st.markdown("**📋 優化文稿**")
        st.markdown(f'<div class="result-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
    with res_c2:
        risk_color = "risk-high" if st.session_state.risk_level == "高" else ("risk-med" if st.session_state.risk_level == "中" else "risk-low")
        st.markdown(f'**⚠️ 風險評估：** <span class="risk-badge {risk_color}">{st.session_state.risk_level}</span>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-box">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

# --- 5. 歷史紀錄追蹤 ---
with tab_history:
    if st.button("🔄 刷新歷史紀錄"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                for index, row in df.iloc[::-1].iterrows():
                    # --- 這裡的 Key 必須跟試算表標題完全一致 ---
                    with st.expander(f"📅 {row['日期']} | {row['學生代號']} ({row['類別']})"):
                        st.write(f"**事實描述：** {row['原始觀察描述']}")
                        st.info(f"**AI 分析結果：**\n{row['AI分析結果']}")
            else: st.warning("尚無資料")
        except Exception as e: st.error(f"讀取異常：{e}")
