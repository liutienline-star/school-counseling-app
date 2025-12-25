import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心安全與連線設定 (完全維持校長原始設定) ---
AUTH_CODE = "641101"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.0-flash" # 註：建議維持 2.0-flash 以確保連線穩定

st.set_page_config(page_title="智慧輔導紀錄系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格優化 (完全維持校長原始 CSS) ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; margin: auto; }
    .stApp { background-color: #1a1c23; color: #e5e9f0; }
    
    [data-testid="stWidgetLabel"] p, label, .stMarkdown p {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 1.15rem !important;
    }
    
    .main-header { 
        text-align: center; 
        background: linear-gradient(90deg, #88c0d0, #5e81ac);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800; font-size: 2.5rem; margin-bottom: 2rem;
    }

    .result-box {
        background-color: #2e3440;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #4c566a;
        min-height: 300px;
        margin-top: 10px;
        white-space: pre-wrap; /* 確保 AI 回傳的換行能正確顯示 */
    }

    .risk-badge {
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: 800;
        font-size: 0.9rem;
        margin-bottom: 10px;
        display: inline-block;
    }
    .risk-high { background-color: #bf616a; color: white; border: 1px solid #ff0000; }
    .risk-med { background-color: #ebcb8b; color: #2e3440; }
    .risk-low { background-color: #a3be8c; color: white; }
    
    .stTextArea textarea { background-color: #2e3440 !important; color: #ffffff !important; border: 1px solid #4c566a !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 驗證邏輯 ---
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

# --- 5. 主介面 ---
st.markdown('<h1 class="main-header">🏫 智慧輔導紀錄與親師生溝通系統</h1>', unsafe_allow_html=True)
tab_input, tab_history, tab_report = st.tabs(["📝 觀察紀錄錄入", "🔍 個案歷程追蹤", "📊 數據彙整筆記"])

if 'analysis_1' not in st.session_state: st.session_state.analysis_1 = ""
if 'analysis_2' not in st.session_state: st.session_state.analysis_2 = ""
if 'risk_level' not in st.session_state: st.session_state.risk_level = ""

with tab_input:
    st.markdown("### ✍️ 第一步：觀察錄入與功能選擇")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1: target_type = st.radio("【對象類型】", ["學生 (個人晤談)", "家長 (親師聯繫)"], horizontal=True)
    with c2: stu_id = st.text_input("【學生代號】", placeholder="例如：809-01")
    with c3: category = st.selectbox("【事件類別】", ["常規指導", "人際衝突", "情緒支持", "學習適應", "家長聯繫", "緊急事件"])
    
    raw_obs = st.text_area("【事實描述或晤談紀錄摘要】", height=200, placeholder="在此輸入內容...")
    is_private = st.checkbox("🔒 機密紀錄模式 (隱藏事實描述)")

    st.markdown("<br>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    
    with b1: gen_1 = st.button("📁 1. 生成優化紀錄文稿", use_container_width=True)
    with b2: 
        btn_label = "🎯 2. 生成分析與預警" if "學生" in target_type else "💬 2. 撰寫親師訊息"
        gen_2 = st.button(btn_label, use_container_width=True)
    with b3: save_trigger = st.button("💾 3. 同步至雲端手冊", use_container_width=True, type="primary")

    # --- AI 邏輯修正：加入口語化 LINE 訊息指令 ---
    if gen_1 and raw_obs:
        with st.spinner("優化中..."):
            st.session_state.analysis_1 = ai_engine.generate_content(f"請優化為正式、客觀的輔導紀錄：\n{raw_obs}").text

    if gen_2 and raw_obs:
        with st.spinner("分析與撰寫中..."):
            if "學生" in target_type:
                # 學生模式：維持專業分析
                prompt = (f"請針對以下內容進行分析：1. 評估情感風險等級(高/中/低)。2. 提供行動建議。 "
                          f"回覆格式第一行標註：【風險等級：高/中/低】。內容如下：\n{raw_obs}")
            else:
                # 家長模式：增設口語化 LINE 訊息要求
                prompt = (f"請針對以下內容進行分析：\n"
                          f"1. 評估情感風險等級(高/中/低)並於第一行標註：【風險等級：高/中/低】。\n"
                          f"2. 撰寫一份『正式親師訊息』(格式正式、語氣委婉)。\n\n"
                          f"3. 撰寫一份『LINE 口語化溝通建議』：\n"
                          f"   - 語氣要像朋友般親切、輕鬆但具專業關懷。\n"
                          f"   - 善用口語化語助詞(如：囉、唷、喔)。\n"
                          f"   - 適度使用表情符號(Emoji)。\n"
                          f"   - 重點在於先肯定孩子，再溫柔帶出需要配合的事項。\n\n"
                          f"內容如下：\n{raw_obs}")
            
            res_text = ai_engine.generate_content(prompt).text
            st.session_state.analysis_2 = res_text
            
            # 風險等級判斷 (維持原邏輯)
            if "高" in res_text.split('\n')[0]: st.session_state.risk_level = "HIGH"
            elif "中" in res_text.split('\n')[0]: st.session_state.risk_level = "MED"
            else: st.session_state.risk_level = "LOW"

    st.divider()
    
    # --- 第二步：橫向視窗 (Side-by-Side) ---
    st.markdown("### ✨ 第二步：導師輔助分析結果 (已整合 LINE 口語建議)")
    res_c1, res_c2 = st.columns(2)
    
    with res_c1:
        st.markdown("**📋 優化文稿**")
        if st.session_state.analysis_1:
            st.markdown(f'<div class="result-box">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="result-box" style="color:#666;">等待生成...</div>', unsafe_allow_html=True)

    with res_c2:
        label = "🎯 行動建議與預警" if "學生" in target_type else "💬 親師訊息 (正式 + LINE 口語)"
        st.markdown(f"**{label}**")
        
        # 顯示風險標籤 (維持原樣)
        if st.session_state.risk_level == "HIGH":
            st.markdown('<div class="risk-badge risk-high">⚠️ 高風險警示：請立刻關注</div>', unsafe_allow_html=True)
        elif st.session_state.risk_level == "MED":
            st.markdown('<div class="risk-badge risk-med">🔔 中風險：建議持續追蹤</div>', unsafe_allow_html=True)
        elif st.session_state.risk_level == "LOW":
            st.markdown('<div class="risk-badge risk-low">✅ 低風險：常規輔導即可</div>', unsafe_allow_html=True)

        if st.session_state.analysis_2:
            st.markdown(f'<div class="result-box" style="border-left:5px solid #88c0d0;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="result-box" style="color:#666;">等待生成...</div>', unsafe_allow_html=True)

    # --- 儲存邏輯 (維持原格式) ---
    if save_trigger:
        if not stu_id:
            st.error("❌ 失敗：請輸入學生代號")
        else:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                fact = "[機密]" if is_private else raw_obs
                sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    stu_id, target_type, category, fact,
                    f"【風險：{st.session_state.risk_level}】\n{st.session_state.analysis_1}\n\n{st.session_state.analysis_2}"
                ])
                st.balloons(); st.success("✅ 已同步至雲端表格")
            except Exception as e: st.error(f"同步失敗：{e}")

# --- 後續 Tab (穩定維持) ---
with tab_history:
    st.markdown("### 🔍 個案歷程查詢")
    q_id = st.text_input("輸入代號：")
    if q_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            recs = sheet.get_all_records()
            matches = [r for r in recs if str(r.get('學生代號','')) == q_id]
            for r in matches[::-1]:
                with st.expander(f"📅 {r.get('日期')} | {r.get('類別')}"):
                    st.write(f"事實：{r.get('事實描述')}")
                    st.info(f"AI內容：\n{r.get('AI 分析結果')}")
        except: st.error("連線異常")

with tab_report:
    st.markdown("### 📊 班級數據統計")
    if st.button("🔄 更新統計"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            st.bar_chart(df['類別'].value_counts())
        except: st.error("讀取失敗")
