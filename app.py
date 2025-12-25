import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd

# --- 1. 核心安全與連線設定 (訴求：核心不變) ---
AUTH_CODE = "1225"  
HUB_NAME = "School_Counseling_Hub"
SHEET_TAB = "Counseling_Logs"
MODEL_NAME = "models/gemini-2.5-flash" 

st.set_page_config(page_title="智慧輔導紀錄系統", layout="wide", page_icon="🏫")

# --- 2. 視覺風格優化 (橫向視窗、限制寬度、文字純白) ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px !important; padding-top: 2rem !important; margin: auto; }
    .stApp { background-color: #1a1c23; color: #e5e9f0; }
    
    /* 標籤文字強制純白 */
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

    /* 橫向卡片樣式 */
    .result-card {
        background-color: #2e3440;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #4c566a;
        height: 100%;
        min-height: 250px;
    }

    .stTextArea textarea { background-color: #2e3440 !important; color: #ffffff !important; border: 1px solid #4c566a !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. 驗證邏輯 (核心功能不變) ---
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
    quick_tags = st.multiselect("💡 常用快速標籤 (點選後會自動填入下方描述)", ["表現優異", "情緒波動", "學習退步", "同儕糾紛", "親師溝通順暢", "建議介入"])
    tag_str = " ".join([f"[{t}]" for t in quick_tags])
    
    # 組合內容
    raw_obs = st.text_area("【事實描述或晤談紀錄摘要】", value=tag_str if tag_str else "", height=250, placeholder="在此輸入觀察事實...")
    
    # [建議 4]: 去識別化勾選
    is_private = st.checkbox("🔒 啟用機密紀錄模式 (存檔時會隱藏此區事實描述，僅保留 AI 分析)")

    st.markdown("<br>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1: gen_formal = st.button("📁 1. 生成優化紀錄文稿", use_container_width=True)
    with b2:
        if "學生" in target_type:
            gen_action = st.button("🎯 2. 生成後續觀察重點", use_container_width=True)
        else:
            gen_action = st.button("💬 2. 撰寫親師合作訊息", use_container_width=True)
    with b3: save_hub = st.button("💾 3. 同步至雲端手冊", use_container_width=True, type="primary")

    # --- 關鍵 AI 觸發邏輯修正 ---
    if gen_formal and raw_obs:
        with st.spinner("AI 文稿優化中..."):
            res = ai_engine.generate_content(f"請將以下導師筆記優化為正式、客觀的輔導紀錄：\n{raw_obs}")
            st.session_state.analysis_1 = res.text

    if gen_action and raw_obs:
        with st.spinner("AI 分析建議中..."):
            if "學生" in target_type:
                prompt = f"請針對此個案事實，提供後續觀察重點與介入建議：\n{raw_obs}"
            else:
                prompt = f"請根據此聯繫紀錄，撰寫一段溫馨且專業的親師聯繫訊息：\n{raw_obs}"
            res = ai_engine.generate_content(prompt)
            st.session_state.analysis_2 = res.text

    st.divider()
    
    # --- 第二步：結果顯示 (強制橫向對話視窗) ---
    st.markdown("### ✨ 第二步：導師輔助分析結果")
    
    res_l, res_r = st.columns(2, gap="large")
    
    with res_l:
        st.markdown("**📋 建議紀錄文稿**")
        if 'analysis_1' in st.session_state:
            st.markdown(f'<div class="result-card">{st.session_state.analysis_1}</div>', unsafe_allow_html=True)
            st.download_button("📥 下載文稿 (.txt)", data=st.session_state.analysis_1, file_name=f"{stu_id}_紀錄.txt", key="dl1")
        else:
            st.markdown('<div class="result-card" style="color:#4c566a;">點擊「1. 生成優化紀錄文稿」後顯示</div>', unsafe_allow_html=True)

    with res_r:
        label_text = "🎯 導師行動建議" if "學生" in target_type else "💬 親師合作草稿"
        st.markdown(f"**{label_text}**")
        if 'analysis_2' in st.session_state:
            st.markdown(f'<div class="result-card" style="border-left:5px solid #88c0d0;">{st.session_state.analysis_2}</div>', unsafe_allow_html=True)
            st.download_button("📥 下載建議 (.txt)", data=st.session_state.analysis_2, file_name=f"{stu_id}_建議.txt", key="dl2")
        else:
            st.markdown('<div class="result-card" style="color:#4c566a;">點擊「2. 生成分析建議」後顯示</div>', unsafe_allow_html=True)

    # --- 儲存邏輯修正 (核心功能) ---
    if save_hub:
        if not stu_id:
            st.error("❌ 儲存失敗：請先輸入【學生代號】")
        else:
            try:
                sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
                # 判斷是否為機密紀錄
                fact_to_save = "[此筆為機密紀錄，內容已隱藏]" if is_private else raw_obs
                
                # 彙整內容
                an1 = st.session_state.get('analysis_1', '(未生成)')
                an2 = st.session_state.get('analysis_2', '(未生成)')
                
                sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                    stu_id,
                    target_type,
                    category,
                    fact_to_save,
                    f"【優化文稿】\n{an1}\n\n【行動建議】\n{an2}"
                ])
                st.balloons()
                st.success(f"✅ 紀錄已成功同步至雲端手冊 ({HUB_NAME})")
                
                # 存完後不清除 analysis，讓導師還能看，直到重新整理
            except Exception as e:
                st.error(f"雲端同步失敗，請檢查權限或試算表名稱：{e}")

# --- 後續 Tab (查詢與統計) ---
with tab_history:
    st.markdown("### 🔍 個案歷程查詢")
    search_id = st.text_input("輸入代號 (例如：809-01)：", key="search_bar")
    if search_id:
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            records = sheet.get_all_records()
            matches = [r for r in records if str(r.get('學生代號', '')) == search_id]
            if matches:
                for r in matches[::-1]:
                    icon = "🚨" if r.get('類別') == "緊急事件" else "📁"
                    with st.expander(f"{icon} {r.get('日期')} | {r.get('類別')} | {r.get('對象')}"):
                        st.write(f"**原始事實：** {r.get('事實描述')}")
                        st.info(f"**AI 分析回顧：**\n{r.get('AI 分析結果')}")
            else: st.warning("查無此學生的歷史紀錄。")
        except: st.error("連線異常")

with tab_report:
    st.markdown("### 📊 班級觀察數據統計")
    if st.button("🔄 載入最新數據分析"):
        try:
            sheet = hub_engine.open(HUB_NAME).worksheet(SHEET_TAB)
            df = pd.DataFrame(sheet.get_all_records())
            st.metric("本學期累積筆數", len(df))
            st.bar_chart(df['類別'].value_counts())
        except: st.error("統計數據讀取失敗")
