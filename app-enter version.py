import streamlit as st
import requests
import os
import time
from duckduckgo_search import DDGS
from dotenv import load_dotenv


# --- 1. 初始化與安全設定 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
# 根據你的檔案名稱修改
dotenv_path = os.path.join(current_dir, "API key.env")
load_dotenv(dotenv_path)
API_KEY = os.getenv("GEMINI_API_KEY")

# 使用你權限內的 3.5 模型
MODEL_NAME = "models/gemini-3.5-flash"

st.set_page_config(page_title="高情商聊天助手", page_icon="🤖")

# --- 2. 記憶初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 3. 核心功能函數 ---

def call_gemini_api(prompt, history=None, retries=3):
    """呼叫 Gemini API，支援歷史紀錄與重試機制"""
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL_NAME}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # 建立內容 Payload
    contents = []
    if history:
        # 只取最近 5 輪對話避免 token 過量
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
                return f"Error: {response.status_code}"
        except Exception as e:
            time.sleep(2)
            continue
            
    return "❌ 無法連線至 Google AI 服務。"

def get_search_results(query):
    """搜尋模組 - 增加結果數量以利篩選"""
    results = []
    try:
        with DDGS() as ddgs:
            # 保持全球搜尋，但將結果增加到 5 條以過濾雜訊
            clean_q = str(query).strip().replace('"', '').replace('\n', ' ')[:50]
            search_gen = ddgs.text(clean_q, region='wt-wt', safesearch='off')
            for r in search_gen:
                results.append(f"**{r['title']}**\n{r['body']}\n[來源]({r['href']})")
                if len(results) >= 5: break
    except:
        pass
    return "\n\n".join(results) if results else "（暫無相關網路查證資料）"

# --- 4. 介面與對話邏輯 ---
st.title("🤖 高情商對話助手")

# 在介面的開頭加上
with st.sidebar:
    password = st.text_input("請輸入邀請碼才能使用：", type="password")

if user_input:
    if password != "654123":
        st.error("邀請碼錯誤，無法進行分析。")
    else:
        # 執行原本的分析邏輯...

# 側邊欄選單
with st.sidebar:
    if st.button("🗑️ 清除對話紀錄"):
        st.session_state.messages = []
        st.rerun()

# 顯示歷史紀錄
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 聊天輸入框 (Enter 傳送)
if user_input := st.chat_input("請描述目前聊天現況..."):
    # 1. 存儲並顯示用戶輸入
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. 助手生成回應
    with st.chat_message("assistant"):
        with st.spinner("🔍 正在聯網查證並思考建議..."):
            
            # 【優化 A】：提取關鍵字 (強制排除歷史干擾)
            kw_prompt = f"""
            你現在是一個搜尋字提取器。請忽略之前聊過的 AI 技術話題。
            僅針對以下這句話提取 2-3 個適合在 Google 搜尋的繁體中文關鍵字：
            "{user_input}"
            只輸出關鍵字，不要有引號或解釋。
            """
            # 注意：這裡 history=None 是關鍵，確保搜尋詞不被歷史帶偏
            search_query = call_gemini_api(kw_prompt, history=None).strip().replace('"', '').replace('*', '')
            
            # 【優化 B】：聯網搜尋
            search_data = get_search_results(search_query)
            
            # 【優化 C】：生成最終建議 (帶入對話歷史以保持連續性)
            final_prompt = f"""
            你是一位高情商對話助手。
            目前的對話現況："{user_input}"
            
            以下是系統為你搜集到的最新網路參考資料：
            ---
            {search_data}
            ---
            
            請根據以上資訊提供：
            1. 【事實查證】：請精準回答搜尋資料中關於"{search_query}"的內容。
               (若搜尋資料與用戶話題無關，請老實說目前搜不到具體數據，不要胡亂連結到 AI 话题)。
            2. 【3個高情商話題建議】：根據目前的語境，提供自然、能延續溫度的接話建議。
            
            語氣要自然、溫暖，像好朋友在出主意。
            """
            response = call_gemini_api(final_prompt, history=st.session_state.messages[:-1])
            
            # 3. 顯示結果
            st.markdown(response)
            
            # 顯示實際搜尋詞與來源 (除錯用)
            with st.expander(f"📌 查看系統搜尋詞：{search_query}"):
                st.markdown(search_data)
            
            # 4. 存入記憶
            st.session_state.messages.append({"role": "assistant", "content": response})