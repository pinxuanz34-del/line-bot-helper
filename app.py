import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, QuickReply, QuickReplyItem, MessageAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.exceptions import InvalidSignatureError

app = Flask(__name__)

# 從環境變數讀取金鑰，確保安全性
CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
line_bot_api = MessagingApi(ApiClient(configuration))
handler = WebhookHandler(CHANNEL_SECRET)

# 狀態與資料暫存
user_data = {}
user_states = {}

# 台灣縣市與行政區資料
CITIES = ["台北市", "新北市", "桃園市", "台中市", "台南市", "高雄市", "其他"]
DISTRICTS = {
    "台北市": ["信義區", "大安區", "中正區", "中山區", "內湖區", "其他"],
    "新北市": ["板橋區", "三重區", "中和區", "永和區", "新莊區", "其他"],
    "桃園市": ["桃園區", "中壢區", "平鎮區", "八德區", "其他"],
    "台中市": ["西屯區", "北屯區", "南屯區", "豐原區", "其他"],
    "台南市": ["永康區", "安南區", "東區", "其他"],
    "高雄市": ["左營區", "三民區", "鳳山區", "其他"]
}

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = user_states.get(user_id)

    if state is None or text == "重新填寫":
        user_data[user_id] = {}
        user_states[user_id] = "waiting_for_name"
        reply = "您好！我是您的資料收集助手。請問您的【姓名】是？"
    
    elif state == "waiting_for_name":
        user_data[user_id]["name"] = text
        user_states[user_id] = "waiting_for_city"
        items = [QuickReplyItem(action=MessageAction(label=c, text=c)) for c in CITIES]
        reply = TextMessage(text=f"收到！{text}，請問您居住在哪个【縣市】？", quick_reply=QuickReply(items=items))

    elif state == "waiting_for_city":
        user_data[user_id]["city"] = text
        user_states[user_id] = "waiting_for_district"
        dists = DISTRICTS.get(text, ["其他區"])
        items = [QuickReplyItem(action=MessageAction(label=d, text=d)) for d in dists]
        reply = TextMessage(text=f"好的，{text}。請問是哪一個【鄉鎮市區】？", quick_reply=QuickReply(items=items))

    elif state == "waiting_for_district":
        user_data[user_id]["district"] = text
        data = user_data[user_id]
        reply = f"✅ 資料已紀錄！\n\n姓名：{data['name']}\n縣市：{data['city']}\n區域：{data['district']}\n\n若需更改請輸入「重新填寫」。"
        del user_states[user_id]

    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[reply if isinstance(reply, TextMessage) else TextMessage(text=reply)]
    ))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
