import os
import json
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    QuickReply, QuickReplyButton, MessageAction
)
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# --- 環境變數與設定 ---
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 初始化 Google Sheets
try:
    info = json.loads(creds_json)
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(info, scopes=scope)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
except Exception as e:
    print(f"Google Sheets 初始化失敗: {e}")

# 縣市資料分頁處理
COUNTIES_P1 = ["臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹縣", "新竹市", "苗栗縣", "彰化縣"]
COUNTIES_P2 = ["南投縣", "雲林縣", "嘉義縣", "嘉義市", "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"]

# 狀態管理
user_sessions = {}

@app.route("/callback", method=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

def get_county_quick_reply(page=1):
    items = []
    target_list = COUNTIES_P1 if page == 1 else COUNTIES_P2
    
    for c in target_list:
        items.append(QuickReplyButton(action=MessageAction(label=c, text=c)))
    
    if page == 1:
        items.append(QuickReplyButton(action=MessageAction(label="➡️ 下一頁", text="下一頁")))
    else:
        items.append(QuickReplyButton(action=MessageAction(label="⬅️ 回首頁", text="回首頁")))
    
    return QuickReply(items=items)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text == "重新填寫" or user_id not in user_sessions:
        user_sessions[user_id] = {'state': 'ASK_NAME'}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="您好！請問您的姓名是？"))
        return

    state = user_sessions[user_id].get('state')

    if state == 'ASK_NAME':
        user_sessions[user_id]['name'] = text
        user_sessions[user_id]['state'] = 'ASK_COUNTY'
        reply_text = f"{text} 您好！請選擇您所在的【縣市】？"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text, quick_reply=get_county_quick_reply(1)))

    elif state == 'ASK_COUNTY':
        if text == "下一頁":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請選擇縣市（第 2 頁）：", quick_reply=get_county_quick_reply(2)))
        elif text == "回首頁":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請選擇縣市（第 1 頁）：", quick_reply=get_county_quick_reply(1)))
        else:
            user_sessions[user_id]['county'] = text
            user_sessions[user_id]['state'] = 'ASK_DISTRICT'
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"好的，那【{text}】的哪個【鄉鎮市區】呢？"))

    elif state == 'ASK_DISTRICT':
        user_sessions[user_id]['district'] = text
        name = user_sessions[user_id]['name']
        county = user_sessions[user_id]['county']
        
        try:
            # 嘗試寫入 Google Sheets
            sheet.append_row([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                name, county, text
            ])
            reply_text = f"完成！已記錄您的資訊：\n姓名：{name}\n地點：{county}{text}\n感謝您的填寫！"
            del user_sessions[user_id]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        except Exception as e:
            print(f"寫入試算表錯誤: {e}") # 這會在 Render 的 Logs 顯示
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="系統繁忙（寫入失敗），請確認試算表共用權限或稍後再試。"))

if __name__ == "__main__":
    app.run()
