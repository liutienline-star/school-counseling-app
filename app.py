import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import smtplib
from email.mime.text import MIMEText

# --- 1. 核心安全與連線設定 ---
AUTH_CODE = "641101"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.0-flash" 

# 郵件設定 (從您剛剛設定好的 Secrets 抓取)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
try:
    SENDER_EMAIL = st.secrets["email"]["sender"]
    SENDER_PASSWORD = st.secrets["email"]["password"]
except:
    SENDER_EMAIL = None
    SENDER_PASSWORD = None

RECEIVER_EMAIL = "counseling_office@school.edu.tw" # 請改為學校專責單位的收件信箱

st.set_page_config(page_title="智慧輔導紀錄系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格 (校長風格：深色質感、視覺完美對齊) ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; margin: auto; }
    .stApp { background-color: #1a1c23; color: #e5e9f0; }
    
    /* 1. 強化標籤與按鈕文字辨識度 (針對手機 LINE 優化) */
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p { color: #FFFFFF !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    button[data-baseweb="tab"] p { color: #d1d5db !important; font-weight: 700 !important; font-size: 1.15rem !important; }
    button[data-baseweb="tab"][aria-selected="true"] p { color: #88c0d0 !important; }
    div[role="radiogroup"] label { color: #FFFFFF !important; font-weight: 500 !important; opacity: 1 !important; }

    /* 2. 按鈕視覺強化 */
    .stButton>button { background-color: #3b4252 !important; color: #ffffff !important; border: 2px solid #88c0d0 !important; font-weight: 700 !important; width: 100% !important; height: 50px; }
    .stButton>button:hover { border: 2px solid #ffffff !important; background-color: #4c566a !important; }
    
    /* 3. 標題高度固定，確保左右方塊完美切齊 */
    .column-header { height: 55px; display: flex; align-items: center; margin-bottom: 5px; font-size: 1.1rem; font-weight: bold; }
    .result-box { background-color: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #4c566a; min-height: 400px; white-space: pre-wrap; color: #ffffff; }
    
    /* 4. 風險標籤樣式 */
    .risk-badge { padding: 5px 15px; border-radius: 20px; font-weight: 800; font-size: 0.9rem; display: inline-block; margin-left: 10px; }
    .risk-high { background-color: #bf616a; color: white; border: 1px solid #ff0000; }
    .risk-med { background-color: #ebcb8b; color: #2e3440; }
    .risk-low { background-color: #a3be8c; color: white; }
    
    /* 5. LINE 專用防呆警告框 */
    .confirm-alert { background-color: #442a2d; border: 3px solid #bf616a; padding: 15px; border-radius: 10px; text-align: center; margin: 15px 0px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 功能：發送緊急通報郵件 ---
def send_high_risk_email(stu_id, category, obs_text):
    if not SENDER_EMAIL or not SENDER_PASSWORD: return False
    try:
        subject = f"🚨 【緊急通報】高風險個案警示：{stu_id}"
        body = f"""校方專責單位您好：\n\n系統偵測到一筆【高風險】輔導紀錄。\n\n學生代號：{stu_id}\n紀錄類別：{category}\n發生時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n請立即處理。"""
        msg = MIMEText(body); msg['Subject'] = subject; msg['From'] = SENDER_EMAIL; msg['To'] = RECEIVER_EMAIL
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(); server.login(SENDER_EMAIL, SENDER_PASSWORD); server.send_message(msg)
        return True
    except: return False

# --- 4. 初始化 (保持功能穩定) ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if not st.session_state.authenticated:
    _, col_m, _ = st.columns([1, 1.5, 1])
    with col_m:
        st.markdown("<div style='text-align:center;'><h1>🔐</h1><h2 style='color:#88c0d0;'>導師身分驗證</h2></div>", unsafe_allow_html=True)
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
    except: return None, None

ai_engine, hub_engine = init_services()

# --- 5. 主介面內容 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)
tab_input, tab_history, tab_report = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

# 初始化狀態變數
if 'analysis_1' not in st.session_state: st.session_state.analysis_1 = ""
if 'analysis_2' not in st.session_state: st.session_state.analysis_2 = ""
if 'risk_level' not in st.session_state: st.session_state.risk_level = "低"
if 'needs_confirm' not in st.session_state: st.session_state.needs_confirm = False

with tab_input:
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with c2: stu_id = st.text_input("【學生代號】", placeholder="例如：809-01")
    with c3: category = st.selectbox("【類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    raw_obs = st.text_area("【事實描述摘要】", height=150)
    is_private = st.checkbox("🔒 機密模式 (雲端僅存入 [機密])")

    st.markdown("<br>", unsafe_allow_html=True)
    col_b1, col_b2, col_b3 = st.columns(3)
    
    if col_b1.button("📁 1. 生成優化紀錄文稿"):
        with st.spinner("AI 轉化中..."):
            res = ai_engine.generate_content(f"請優化為專業、客觀且中立的輔導紀錄，適合成校內公文或紀錄存檔：\n{raw_obs}")
            st.session_state.analysis_1 = res.text

    if col_b2.button("🎯 2. 生成分析與建議"):
        with st.spinner("AI 分析中..."):
            prompt = (f"請分析風險等級(第一行標註：【風險等級：高/中/低】)，並提供處理行動建議與一份溫潤的家長溝通訊息：\n{raw_obs}")
            res = ai_engine.generate_content(prompt).text
            st.session_state.analysis_2 = res
            st.session_state.risk_level = "高" if "高" in res.split('\n')[0] else ("中" if "中" in res.split('\n')[0] else "低")

    if col_b3.button("💾 3. 同步至雲端手冊", type="primary"):
        if stu_id:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                fact_to_save = "[機密紀錄]" if is_private else raw_obs
                row_data = [datetime.now().strftime("%Y/%m/%d %H:%M"), stu_id, target_type, category, st.session_state.risk_level, fact_to_save, f"【優化文稿】\n{st.session_state.analysis_1}\n\n【分析建議】\n{st.session_state.analysis_2}"]
                sheet.append_row(row_data)
                
                if st.session_state.risk_level == "高":
                    st.session_state.needs_confirm = True # 觸發保險機制
                else:
                    st.balloons(); st.success("✅ 資料已成功同步至試算表！")
            except Exception as e: st.error(f"同步失敗：{e}")
        else: st.error("❌ 請輸入學生代號")

    # --- 雙重防呆：確認發送通報信 ---
    if st.session_state.needs_confirm:
        st.markdown(f"""<div class="confirm-alert"><h3 style="color:#ff4b4b;">🚨 緊急通報確認</h3><p style="color:white;">系統判定此筆紀錄為<b>高風險</b>，是否要同步發送 Email 警示給專職單位？</p></div>""", unsafe_allow_html=True)
        if st.button("🚀 我已確認，立即發送緊急通報信"):
            if send_high_risk_email(stu_id, category, raw_obs):
                st.success("📩 通報信件已送達！")
                st.session_state.needs_confirm = False
            else: st.error("發信失敗，請檢查系統 Secrets 設定。")

    st.divider()
    res_c1, res_c2 = st.columns(2)
    with res_c1:
        st.markdown('<div class="column-header">**📋 優化文稿**</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
    with res_c2:
        risk_color = "risk-high" if st.session_state.risk_level == "高" else ("risk-med" if st.session_state.risk_level == "中" else "risk-low")
        st.markdown(f'<div class="column-header">**⚠️ 風險評估：** <span class="risk-badge {risk_color}">{st.session_state.risk_level}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-box">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

# (歷史紀錄與統計圖表維持原樣...)
