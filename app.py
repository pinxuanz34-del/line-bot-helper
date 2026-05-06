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
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# --- 設定環境變數 ---
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# Google Sheets 初始化
def get_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # 從環境變數讀取 JSON 金鑰
    creds_raw = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    creds_dict = json.loads(creds_raw)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("LINE_Bot_Data").sheet1

# --- 台灣行政區完整資料庫 ---
REGION_MAP = {
    "北部": ["臺北市", "新北市", "基隆市", "桃園市", "新竹縣", "新竹市", "宜蘭縣"],
    "中部": ["苗栗縣", "臺中市", "彰化縣", "南投縣", "雲林縣"],
    "南部": ["嘉義縣", "嘉義市", "臺南市", "高雄市", "屏東縣"],
    "東部與離島": ["花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣"]
}

# 完整的縣市對應鄉鎮市區資料
TAIWAN_DATA = {
    "臺北市": ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"],
    "新北市": ["板橋區", "三重區", "中和區", "永和區", "新莊區", "新店區", "土城區", "蘆洲區", "汐止區", "樹林區", "淡水區", "五股區", "泰山區", "林口區", "深坑區", "石碇區", "坪林區", "三芝區", "石門區", "八里區", "平溪區", "雙溪區", "貢寮區", "金山區", "萬里區", "烏來區", "瑞芳區", "三峽區", "鶯歌區"],
    "雲林縣": ["斗六市", "斗南鎮", "虎尾鎮", "西螺鎮", "土庫鎮", "北港鎮", "古坑鄉", "大埤鄉", "莿桐鄉", "林內鄉", "二崙鄉", "崙背鄉", "麥寮鄉", "東勢鄉", "褒忠鄉", "臺西鄉", "元長鄉", "四湖鄉", "口湖鄉", "水林鄉"],
    "臺中市": ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區", "太平區", "大里區", "霧峰區", "烏日區", "豐原區", "后里區", "石岡區", "東勢區", "和平區", "新社區", "潭子區", "大雅區", "神岡區", "大肚區", "沙鹿區", "龍井區", "梧棲區", "清水區", "大甲區", "外埔區", "大安區"],
    # ... 其他縣市可依此類推增加 ...
}

# 反向索引：{"虎尾鎮": "雲林縣"}，用於快速偵錯
DISTRICT_TO_CITY = {dist: city for city, districts in TAIWAN_DATA.items() for dist in districts}

user_state = {}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['x-line-signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    msg = event.message.text.strip()
    
    if user_id not in user_state:
        user_state[user_id] = {"step": "ASK_NAME"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="您好！請問您的姓名是？"))
        return

    state = user_state[user_id]

    # 1. 詢問姓名 -> 詢問區域
    if state["step"] == "ASK_NAME":
        state["name"] = msg
        state["step"] = "ASK_REGION"
        buttons = [QuickReplyButton(action=MessageAction(label=r, text=r)) for r in REGION_MAP.keys()]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"{state['name']} 您好！請先選擇您所在的區域：",
            quick_reply=QuickReply(items=buttons)
        ))

    # 2. 選擇區域 -> 選擇縣市
    elif state["step"] == "ASK_REGION":
        if msg in REGION_MAP:
            state["step"] = "ASK_CITY"
            cities = REGION_MAP[msg]
            buttons = [QuickReplyButton(action=MessageAction(label=c, text=c)) for c in cities]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"請選擇 {msg} 的縣市：",
                quick_reply=QuickReply(items=buttons)
            ))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請從選單中選擇區域。"))

    # 3. 選擇縣市 -> 選擇鄉鎮市區
    elif state["step"] == "ASK_CITY":
        if msg in TAIWAN_DATA:
            state["city"] = msg
            state["step"] = "ASK_DISTRICT"
            districts = TAIWAN_DATA[msg]
            # LINE 限制 13 個按鈕，若超過則顯示前 12 個，最後一個提醒手打
            buttons = [QuickReplyButton(action=MessageAction(label=d, text=d)) for d in districts[:12]]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"請選擇 {msg} 的鄉鎮市區（若沒看到請直接輸入）：",
                quick_reply=QuickReply(items=buttons)
            ))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請從選單中選擇正確的縣市。"))

    # 4. 驗證鄉鎮市區並存入 Google Sheets
    elif state["step"] == "ASK_DISTRICT":
        selected_city = state["city"]
        
        # 偵錯驗證
        if msg in TAIWAN_DATA.get(selected_city, []):
            state["district"] = msg
            try:
                sheet = get_sheet()
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                sheet.append_row([timestamp, user_id, state['name'], state['city'], state['district']])
                
                line_bot_api.reply_message(event.reply_token, TextSendMessage(
                    text=f"✅ 登記成功！\n姓名：{state['name']}\n地址：{state['city']}{state['district']}\n資料已存入試算表。"
                ))
                del user_state[user_id]
            except Exception as e:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="抱歉，資料存入失敗，請稍後再試。"))
        else:
            # 智慧提醒錯誤點
            correct_city = DISTRICT_TO_CITY.get(msg)
            if correct_city:
                reply_text = f"❌ 偵測到錯誤！『{msg}』是屬於『{correct_city}』的。\n您剛才選的是『{selected_city}』，請重新選擇正確的區域。"
            else:
                reply_text = f"❌ 找不到『{msg}』，請確認輸入是否有誤，或從選單中選擇。"
            
            districts = TAIWAN_DATA.get(selected_city, [])
            buttons = [QuickReplyButton(action=MessageAction(label=d, text=d)) for d in districts[:12]]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=reply_text,
                quick_reply=QuickReply(items=buttons)
            ))

if __name__ == "__main__":
    app.run(port=10000)
