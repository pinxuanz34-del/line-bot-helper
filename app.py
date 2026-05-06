import os
import json
import logging
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    QuickReply, QuickReplyButton, MessageAction
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 設定日誌等級，方便在 Render 的 Logs 查看錯誤
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- 環境變數讀取 ---
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
# 支援兩種可能的變數名稱
GOOGLE_JSON_STR = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON') or os.environ.get('GOOGLE_CREDENTIALS_JSON')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- 台灣行政區數據 (部分示範，請補足完整) ---
TAIWAN_DATA = {
    "台北市": ["中正區", "萬華區", "大同區", "中山區", "松山區", "大安區", "信義區", "內湖區", "南港區", "士林區", "北投區", "文山區"],
    "新北市": ["板橋區", "三重區", "中和區", "永和區", "新莊區", "新店區", "樹林區", "鶯歌區", "三峽區", "淡水區", "汐止區", "瑞芳區", "土城區", "蘆洲區", "五股區", "泰山區", "林口區", "深坑區", "石碇區", "坪林區", "三芝區", "石門區", "八里區", "平溪區", "雙溪區", "貢寮區", "金山區", "萬里區", "烏來區"],
    "桃園市": ["桃園區", "中壢區", "大溪區", "楊梅區", "蘆竹區", "大園區", "龜山區", "八德區", "龍潭區", "平鎮區", "新屋區", "觀音區", "復興區"],
    # ... 其餘縣市請按此格式補齊
}

# 狀態暫存（實務上建議使用 Redis 或資料庫）
user_states = {}

def get_gspread_client():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GOOGLE_JSON_STR)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"Google Sheets 認證失敗: {e}")
        return None

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    if user_id not in user_states:
        user_states[user_id] = {"step": "ASK_NAME"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="您好！請輸入您的姓名以開始填寫問卷："))
        return

    state = user_states[user_id]

    if state["step"] == "ASK_NAME":
        state["name"] = text
        state["step"] = "ASK_CITY"
        cities = list(TAIWAN_DATA.keys())
        buttons = [QuickReplyButton(action=MessageAction(label=c, text=c)) for c in cities[:13]]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"{text} 您好，請選擇您居住的縣市：",
            quick_reply=QuickReply(items=buttons)
        ))

    elif state["step"] == "ASK_CITY":
        if text in TAIWAN_DATA:
            state["city"] = text
            state["step"] = "ASK_DISTRICT"
            districts = TAIWAN_DATA[text]
            
            # --- 關鍵修正：解決 Quick Reply 13 個上限問題 ---
            display_districts = districts[:12]
            buttons = [QuickReplyButton(action=MessageAction(label=d, text=d)) for d in display_districts]
            if len(districts) > 12:
                buttons.append(QuickReplyButton(action=MessageAction(label="其他/請手打", text="請直接輸入區名")))
            
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"請選擇 {text} 的行政區：",
                quick_reply=QuickReply(items=buttons)
            ))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請從下方選單選擇正確的縣市。"))

    elif state["step"] == "ASK_DISTRICT":
        state["district"] = text
        # 準備寫入試算表
        try:
            client = get_gspread_client()
            if client:
                sh = client.open_by_key(SPREADSHEET_ID)
                worksheet = sh.get_worksheet(0)
                worksheet.append_row([state["name"], state["city"], state["district"]])
                
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="資料已成功記錄！謝謝您的填寫。"))
                del user_states[user_id] # 完成後清除狀態
            else:
                raise Exception("無法取得 Google Sheets 客戶端")
        except Exception as e:
            logger.error(f"寫入試算表錯誤: {e}")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="抱歉，系統暫時無法存取試算表，請稍後再試。"))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
