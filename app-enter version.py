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
# 支援多種檔名：優先支援你原本的 "API key.env"，若無則支援標準 ".env"
dotenv_path = os.path.join(current_dir, "API key.env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    load_dotenv()

# 優先從 Streamlit Secrets 讀取，若無則從環境變數讀取
API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("API_KEY")

# 【修正 A】模型設定：移除 "models/" 前綴，避免網址拼接錯誤
MODEL_NAME = "gemini-3.5-flash"

# --- 3. 記憶初始化 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 4. 核心功能函數 ---

def call_gemini_api(prompt, history=None, retries=3):
    if not API_KEY:
        return "❌ 錯誤：找不到 API Key，請在 Secrets 或 .env 中設定。"
    
    # 這裡的網址手動補上 models/，最符合官方 beta 版規範
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    contents = []
    # 【修正 B】完美重構歷史紀錄轉換邏輯
    if history:
        for msg in history: 
            contents.append({
                "role": "user" if msg["role"] == "user" else "model", 
                "parts": [{"text": msg["content"]}]
            })
        
        # 如果歷史紀錄的最後一筆已經是用戶剛才講的話，就不用在下方重複 append 相同的 prompt
        if contents[-1]["role"] == "user" and prompt == contents[-1]["parts"][0]["text"]:
            pass
        else:
            contents.append({"role": "user", "parts": [{"text": prompt}]})
    else:
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
                # 【進階除錯】如果出錯，直接印出 Google 官方回傳的具體原因，不瞎猜
                try:
                    error_details = response.json()['error']['message']
                    return f"❌ Google API 錯誤 ({response.status_code}): {error_details}"
                except:
                    return f"❌ Error: {response.status_code} - {response.text}"
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

# 🔑 【核心修正】門禁機制：必須放在主邏輯最前端
# 如果邀請碼不正確，直接凍結網頁，不執行後續程式碼
if invite_code != "654123":
    if invite_code != "":  # 使用者有輸入，但輸錯了
        st.error("⚠️ 邀請碼錯誤，無法使用此工具。")
    else:                  # 使用者尚未輸入任何內容
        st.info("🔒 請在左側側邊欄輸入邀請碼以解鎖機器人功能。")
    st.stop()              # 🛑 門禁卡：直接在這裡中斷執行，下方所有聊天介面都會被隱藏

# -------------------------------------------------------------
# 🔓 只有密碼輸入正確（654123），程式才會成功「走過」上面的 st.stop() 來到這裡
# -------------------------------------------------------------

# 顯示歷史紀錄
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 聊天輸入框 (此時不需要再重複檢查邀請碼了)
if user_input := st.chat_input("請描述目前聊天現況..."):
    
    # 1. 存儲並顯示用戶輸入
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. 助手生成回應
    with st.chat_message("assistant"):
        with st.spinner("🔍 正在聯網查證並思考建議..."):
            
            # A. 提取關鍵字 (不帶歷史)
            kw_prompt = f"你現在是一個搜尋字提取器。僅針對以下這句話提取 2-3 個適合在 Google 搜尋的繁體中文關鍵字，只輸出關鍵字，不要有解釋：\n\"{user_input}\""
            search_query = call_gemini_api(kw_prompt, history=None).strip().replace('"', '').replace('*', '')
            
            # B. 聯網搜尋
            search_data = get_search_results(search_query)
            
            # C. 生成最終建議 (帶入包含最新輸入的完整 messages 結構)
            final_prompt = f"""你是一位高情商對話助手。
目前的對話現況："{user_input}"

以下是系統為你搜集到的最新網路參考資料：
---
{search_data}
---

請根據以上資訊提供：
1. 【事實查證】：請精準回答搜尋資料中關於此話題的內容。
2. 【3個高情商話題建議】：根據目前的語境，提供自然、能延續溫度的接話建議。"""
            
            response = call_gemini_api(final_prompt, history=st.session_state.messages)
            
            # 3. 顯示結果
            st.markdown(response)
            with st.expander(f"📌 查看系統搜尋詞：{search_query}"):
                st.markdown(search_data)
            
            # 4. 存入記憶
            st.session_state.messages.append({"role": "assistant", "content": response})