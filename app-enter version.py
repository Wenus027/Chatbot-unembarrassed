import streamlit as st
import requests
import os
import time
from duckduckgo_search import DDGS
from dotenv import load_dotenv

# --- 1. 初始化設定 (必須是 Streamlit 的第一個指令) ---
st.set_page_config(page_title="輔助聊天機器人", page_icon="🤖")

# --- 2. 安全載入 API Key ---
current_dir = os.path.dirname(os.path.abspath(__file__))
# 支援本地 .env 檔案 (本地開發用)
dotenv_path = os.path.join(current_dir, "API key.env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# 優先從 Streamlit Secrets 讀取 (雲端部署用)，若無則從環境變數讀取
API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

# 模型設定
MODEL_NAME = "models/gemini-3.5-flash"

# --- 3. 記憶初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 4. 核心功能函數 ---

def call_gemini_api(prompt, history=None, retries=3):
    if not API_KEY:
        return "❌ 錯誤：找不到 API Key，請在 Secrets 或 .env 中設定。"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    contents = []
    if history:
        for msg in history[-5:]: 
            contents.append({
                "role": "user" if msg["role"] == "user" else "model", 
                "parts": [{"text": msg["content"]}]
            })
    
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    payload = {"contents": contents}
    
    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                if response.status_code in [503, 429]:
                    time.sleep((attempt + 1) * 2)
                    continue
                return f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            time.sleep(2)
            continue
    return "❌ 無法連線至 Google AI 服務，請檢查網路或金鑰權限。"

def get_search_results(query):
    results = []
    try:
        with DDGS() as ddgs:
            clean_q = str(query).strip().replace('"', '').replace('\n', ' ')[:50]
            search_gen = ddgs.text(clean_q, region='wt-wt', safesearch='off')
            for r in search_gen:
                results.append(f"**{r['title']}**\n{r['body']}\n[來源]({r['href']})")
                if len(results) >= 5: break
    except:
        pass
    return "\n\n".join(results) if results else "（暫無相關網路查證資料）"

# --- 5. 介面設計 ---
st.title("🤖 輔助聊天機器人")

# 側邊欄：邀請碼與清除紀錄
with st.sidebar:
    st.header("驗證與設定")
    invite_code = st.text_input("請輸入邀請碼：", type="password")
    st.divider()
    if st.button("🗑️ 清除對話紀錄"):
        st.session_state.messages = []
        st.rerun()

# 顯示歷史紀錄
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 聊天輸入框
if user_input := st.chat_input("請描述目前聊天現況..."):
    # 檢查邀請碼
    if invite_code != "654123":
        st.error("⚠️ 邀請碼錯誤，請在側邊欄輸入正確代碼後再發送訊息。")
    else:
        # 1. 存儲並顯示用戶輸入
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 2. 助手生成回應
        with st.chat_message("assistant"):
            with st.spinner("🔍 正在聯網查證並思考建議..."):
                
                # A. 提取關鍵字 (不帶歷史)
                kw_prompt = f"提取搜尋關鍵字：{user_input}。只輸出關鍵字。"
                search_query = call_gemini_api(kw_prompt, history=None).strip().replace('"', '').replace('*', '')
                
                # B. 聯網搜尋
                search_data = get_search_results(search_query)
                
                # C. 生成最終建議 (帶入對話歷史)
                final_prompt = f"對話現況：{user_input}\n參考資料：{search_data}\n請提供事實查證與3個高情商話題建議。語氣自然。"
                response = call_gemini_api(final_prompt, history=st.session_state.messages[:-1])
                
                # 3. 顯示結果
                st.markdown(response)
                with st.expander(f"📌 查看系統搜尋詞：{search_query}"):
                    st.markdown(search_data)
                
                # 4. 存入記憶
                st.session_state.messages.append({"role": "assistant", "content": response})