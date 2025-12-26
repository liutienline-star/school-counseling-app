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

# --- 2. 視覺風格 (校長風格：深色質感) ---
st.markdown("""
    <style>
    /* 基礎容器樣式 */
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; margin: auto; }
    .stApp { background-color: #1a1c23; color: #e5e9f0; }
    
    /* 1. 修正所有標籤文字 (確保未選中時也清晰) */
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p { 
        color: #FFFFFF !important; 
        font-weight: 700 !important; 
        font-size: 1.15rem !important; 
    }
    
    /* 2. 修正標籤頁文字 (增加未選中狀態的亮度) */
    button[data-baseweb="tab"] p { 
        color: #d1d5db !important; /* 未選中時呈現淺灰色，提高辨識度 */
        font-weight: 700 !important; 
        font-size: 1.2rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] p { 
        color: #88c0d0 !important; /* 選中時呈現亮藍色 */
    }

    /* 3. 修正單選按鈕選項文字 (未選中也保持純白) */
    div[role="radiogroup"] label {
        color: #FFFFFF !important;
        font-weight: 500 !important;
        opacity: 1 !important; /* 消除透明度，使其清晰 */
    }

    /* 4. 修正功能按鈕文字與邊框 (強化視覺邊界) */
    .stButton>button { 
        background-color: #3b4252 !important; 
        color: #ffffff !important; 
        border: 2px solid #88c0d0 !important; /* 加粗邊框 */
        font-weight: 700 !important;
        padding: 0.5rem 1rem !important;
        width: 100% !important;
    }
    .stButton>button:hover {
        border: 2px solid #ffffff !important;
        background-color: #4c566a !important;
    }
    
    /* 5. 標題高度統一化 (解決方塊沒切齊的問題) */
    .column-header {
        height: 50px;
        display: flex;
        align-items: center;
        margin-bottom: 5px;
    }

    /* 結果框樣式 */
    .main-header { text-align: center; background: linear-gradient(90deg, #88c0d0, #5e81ac); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 2.5rem; margin-bottom: 2rem; }
    .result-box { background-color: #2e3440; padding: 20px; border-radius: 12px; border: 1px solid #4c566a; min-height: 400px; white-space: pre-wrap; color: #ffffff; }
    .risk-badge { padding: 5px 15px; border-radius: 20px; font-weight: 800; font-size: 0.9rem; display: inline-block; margin-left: 10px; }
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
        st.markdown("<div style='text-align:center;'><h1>🔐</h1><h2 style='color:#88c0d0;'>導師身分驗證</h2></div>", unsafe_allow_html=True)
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

# --- 5. 主介面內容 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)
tab_input, tab_history, tab_report = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

if 'analysis_1' not in st.session_state: st.session_state.analysis_1 = ""
if 'analysis_2' not in st.session_state: st.session_state.analysis_2 = ""
if 'risk_level' not in st.session_state: st.session_state.risk_level = "低"

with tab_input:
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with c2: stu_id = st.text_input("【學生代號】", placeholder="例如：809-01")
    with c3: category = st.selectbox("【類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    raw_obs = st.text_area("【事實描述摘要】", height=150)
    is_private = st.checkbox("🔒 機密模式 (雲端將僅存入 [機密])")

    st.markdown("<br>", unsafe_allow_html=True)
    col_b1, col_b2, col_b3 = st.columns(3)
    
    if col_b1.button("📁 1. 生成優化紀錄文稿"):
        with st.spinner("生成中..."):
            res = ai_engine.generate_content(f"請優化為專業且客觀的輔導紀錄，保持中立：\n{raw_obs}")
            st.session_state.analysis_1 = res.text

    if col_b2.button("🎯 2. 生成分析與建議"):
        with st.spinner("分析中..."):
            prompt = (f"請針對這份【{target_type}】內容進行分析。\n"
                      f"第一行必須標註：【風險等級：高/中/低】。\n"
                      f"隨後提供：\n1. 初步處理行動建議。\n"
                      f"2. 一份給家長的溝通訊息。要求：語氣溫潤、具備專業關懷，先肯定孩子，避免生硬口吻。\n"
                      f"※ 注意：即便此紀錄是學生個人晤談，也請產出供老師參考發送給家長的溝通/回報訊息格式。\n\n"
                      f"內容：\n{raw_obs}")
            res = ai_engine.generate_content(prompt).text
            st.session_state.analysis_2 = res
            first_line = res.split('\n')[0]
            if "高" in first_line: st.session_state.risk_level = "高"
            elif "中" in first_line: st.session_state.risk_level = "中"
            else: st.session_state.risk_level = "低"

    if col_b3.button("💾 3. 同步至雲端手冊", type="primary"):
        if stu_id:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                fact_to_save = "[機密紀錄]" if is_private else raw_obs
                row_data = [
                    datetime.now().strftime("%Y/%m/%d %H:%M"), 
                    stu_id, 
                    target_type, 
                    category, 
                    st.session_state.risk_level, 
                    fact_to_save, 
                    f"【優化文稿】\n{st.session_state.analysis_1}\n\n【分析建議】\n{st.session_state.analysis_2}"
                ]
                sheet.append_row(row_data)
                st.balloons()
                st.success("✅ 資料已精準同步至雲端表格！")
            except Exception as e:
                st.error(f"同步失敗：{e}")
        else:
            st.error("❌ 請輸入學生代號")

    st.divider()
    res_c1, res_c2 = st.columns(2)
    with res_c1:
        # 使用 column-header class 確保高度對齊
        st.markdown('<div class="column-header">**📋 優化文稿**</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
    with res_c2:
        risk_color = "risk-high" if st.session_state.risk_level == "高" else ("risk-med" if st.session_state.risk_level == "中" else "risk-low")
        # 同樣使用 column-header class
        st.markdown(f'<div class="column-header">**⚠️ 風險評估：** <span class="risk-badge {risk_color}">{st.session_state.risk_level}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-box">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)

# --- 6. 歷史紀錄追蹤 ---
with tab_history:
    st.markdown("### 🔍 個案歷程追蹤")
    if st.button("🔄 刷新歷史紀錄"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                for index, row in df.iloc[::-1].iterrows():
                    with st.expander(f"📅 {row['日期']} | {row['學生代號']} ({row['類別']} - 風險：{row['風險等級']})"):
                        st.write(f"**事實描述：**\n{row['原始觀察描述']}")
                        st.info(f"**AI 分析結果：**\n{row['AI分析結果']}")
            else:
                st.warning("目前試算表中尚無資料。")
        except Exception as e:
            st.error(f"讀取異常，請確認試算表標題是否正確：{e}")

# --- 7. 數據統計 ---
with tab_report:
    st.markdown("### 📊 輔導數據彙整")
    if st.button("📈 重新生成統計圖表"):
        try:
            df = pd.DataFrame(hub_engine.open(HUB_NAME).worksheet(SHEET_TAB).get_all_records())
            if not df.empty:
                st.write("#### 類別分布")
                st.bar_chart(df['類別'].value_counts())
                st.write("#### 最近 5 筆紀錄摘要")
                st.table(df[['日期', '學生代號', '類別', '風險等級']].tail(5))
            else:
                st.info("尚無足夠數據進行分析。")
        except:
            st.error("讀取數據失敗。")
