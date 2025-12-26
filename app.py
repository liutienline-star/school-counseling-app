import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

# --- 1. 核心安全與連線設定 ---
AUTH_CODE = "641101"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.0-flash" 

# [郵件設定] 從 Secrets 讀取
try:
    SENDER_EMAIL = st.secrets["email"]["sender"]
    SENDER_PASSWORD = st.secrets["email"]["password"]
    # 測試階段：收件人設定為校長您自己
    RECEIVER_EMAIL = SENDER_EMAIL 
except:
    st.error("❌ 偵測不到 Secrets 中的 Email 設定，請檢查 Streamlit 後台。")
    SENDER_EMAIL = SENDER_PASSWORD = RECEIVER_EMAIL = None

st.set_page_config(page_title="智慧輔導紀錄系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格 (校長版：視覺切齊、高對比度、手機優化) ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; margin: auto; }
    .stApp { background-color: #1a1c23; color: #e5e9f0; }
    
    /* 文字與標籤辨識度 */
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p { color: #FFFFFF !important; font-weight: 700 !important; font-size: 1.1rem !important; }
    button[data-baseweb="tab"] p { color: #d1d5db !important; font-weight: 700 !important; font-size: 1.15rem !important; }
    button[data-baseweb="tab"][aria-selected="true"] p { color: #88c0d0 !important; }

    /* 按鈕強化 */
    .stButton>button { background-color: #3b4252 !important; color: #ffffff !important; border: 2px solid #88c0d0 !important; font-weight: 700 !important; width: 100% !important; height: 50px; }
    .stButton>button:hover { border: 2px solid #ffffff !important; }
    
    /* 關鍵：標題高度固定，確保左右方塊完美切齊 */
    .column-header { height: 60px; display: flex; align-items: center; margin-bottom: 5px; font-weight: bold; font-size: 1.1rem; }
    .result-box { background-color: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #4c566a; min-height: 400px; white-space: pre-wrap; color: #ffffff; }
    
    /* 風險與警示樣式 */
    .risk-badge { padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 0.9rem; margin-left: 10px; }
    .risk-high { background-color: #bf616a; color: white; border: 1px solid #ff0000; }
    .risk-med { background-color: #ebcb8b; color: #2e3440; }
    .risk-low { background-color: #a3be8c; color: white; }
    
    .confirm-alert { background-color: #442a2d; border: 3px solid #bf616a; padding: 20px; border-radius: 10px; text-align: center; margin: 20px 0px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 功能：發送電子郵件 ---
def send_alert_email(stu_id, category, content):
    if not SENDER_EMAIL or not SENDER_PASSWORD: return False
    try:
        subject = f"🚨 【測試通報】高風險個案警示：{stu_id}"
        body = f"校長您好：\n\n系統偵測到一筆【高風險】輔導紀錄。\n\n學生代號：{stu_id}\n類別：{category}\n時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n這是一封自動測試信件，代表系統通報功能運作正常。"
        msg = MIMEText(body); msg['Subject'] = subject; msg['From'] = SENDER_EMAIL; msg['To'] = RECEIVER_EMAIL
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls(); server.login(SENDER_EMAIL, SENDER_PASSWORD); server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"郵件發送失敗：{e}")
        return False

# --- 4. 系統初始化 ---
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

# 初始化 Session State
for key in ['analysis_1', 'analysis_2', 'risk_level', 'needs_confirm']:
    if key not in st.session_state:
        st.session_state[key] = "" if key != 'risk_level' else "低"
        if key == 'needs_confirm': st.session_state[key] = False

# --- 5. 主介面 ---
st.markdown('<h1 style="text-align:center; color:#88c0d0; margin-bottom:30px;">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

with tab1:
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with c2: stu_id = st.text_input("【學生代號】", placeholder="例如：809-01")
    with c3: category = st.selectbox("【類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    raw_obs = st.text_area("【事實描述摘要】", height=150, placeholder="請輸入老師觀察到的客觀事實...")
    is_private = st.checkbox("🔒 機密模式 (雲端將不存入事實內容)")

    st.markdown("<br>", unsafe_allow_html=True)
    btn_c1, btn_c2, btn_c3 = st.columns(3)
    
    if btn_c1.button("📁 1. 生成優化紀錄文稿"):
        with st.spinner("AI 轉化中..."):
            res = ai_engine.generate_content(f"請將以下事實描述優化為專業的輔導紀錄，保持客觀中立：\n{raw_obs}")
            st.session_state.analysis_1 = res.text

    if btn_c2.button("🎯 2. 生成分析與建議"):
        with st.spinner("AI 分析中..."):
            prompt = (f"請分析風險等級(請務必標註：【風險等級：高/中/低】)，並提供專業建議與家長溝通訊息：\n{raw_obs}")
            res = ai_engine.generate_content(prompt).text
            st.session_state.analysis_2 = res
            # 強化偵測：檢查前 100 個字
            preview = res[:100]
            if "高" in preview: st.session_state.risk_level = "高"
            elif "中" in preview: st.session_state.risk_level = "中"
            else: st.session_state.risk_level = "低"

    if btn_c3.button("💾 3. 同步至雲端手冊", type="primary"):
        if stu_id:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                fact_content = "[機密紀錄]" if is_private else raw_obs
                row = [datetime.now().strftime("%Y/%m/%d %H:%M"), stu_id, target_type, category, st.session_state.risk_level, fact_content, f"{st.session_state.analysis_1}\n---\n{st.session_state.analysis_2}"]
                sheet.append_row(row)
                
                if st.session_state.risk_level == "高":
                    st.session_state.needs_confirm = True # 觸發保險
                    st.rerun()
                else:
                    st.balloons(); st.success("✅ 資料同步成功！")
            except Exception as e: st.error(f"連線失敗：{e}")
        else: st.error("❌ 請填寫學生代號")

    # --- 第二道保險：高風險確認發信區塊 ---
    if st.session_state.needs_confirm:
        st.markdown(f"""
            <div class="confirm-alert">
                <h2 style="color:#ff4b4b; margin-top:0;">🚨 偵測到高風險：{stu_id}</h2>
                <p style="font-size:1.1rem;">資料已存入雲端。是否要額外發送<b>緊急通報郵件</b>？</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("🚀 確認發送緊急通報信 (發送至您的信箱)"):
            if send_alert_email(stu_id, category, raw_obs):
                st.success("📩 測試信件已成功發出，請檢查您的信箱！")
                st.session_state.needs_confirm = False
            else:
                st.error("郵件發送失敗。")

    st.divider()
    
    # --- 顯示區：視覺切齊優化 ---
    res_c1, res_c2 = st.columns(2)
    with res_c1:
        st.markdown('<div class="column-header">📋 優化文稿</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
    with res_c2:
        risk_class = "risk-high" if st.session_state.risk_level == "高" else ("risk-med" if st.session_state.risk_level == "中" else "risk-low")
        st.markdown(f'<div class="column-header">⚠️ 風險評估：<span class="risk-badge {risk_class}">{st.session_state.risk_level}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-box">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)
