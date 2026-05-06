import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent,
    QuickReply, QuickReplyButton, MessageAction
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

# --- 環境變數 ---
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- 台灣縣市與行政區資料 ---
TAIWAN_DATA = {
    "台北市": ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"],
    "新北市": ["板橋區", "三重區", "中和區", "永和區", "新莊區", "新店區", "樹林區", "鶯歌區", "三峽區", "淡水區", "汐止區", "瑞芳區", "土城區", "蘆洲區", "五股區", "泰山區", "林口區", "深坑區", "石碇區", "坪林區", "三芝區", "石門區", "八里區", "平溪區", "雙溪區", "貢寮區", "金山區", "萬里區", "烏來區"],
    "桃園市": ["桃園區", "中壢區", "大溪區", "楊梅區", "蘆竹區", "大園區", "龜山區", "八德區", "龍潭區", "平鎮區", "新屋區", "觀音區", "復興區"],
    "台中市": ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區", "太平區", "大里區", "霧峰區", "烏日區", "豐原區", "后里區", "石岡區", "東勢區", "和平區", "新社區", "潭子區", "大雅區", "神岡區", "大肚區", "龍井區", "沙鹿區", "梧棲區", "清水區", "大甲區", "外埔區", "大安區"],
    "台南市": ["中西區", "東區", "南區", "北區", "安平區", "安南區", "永康區", "歸仁區", "新化區", "左鎮區", "玉井區", "楠西區", "南化區", "仁德區", "關廟區", "龍崎區", "官田區", "麻豆區", "佳里區", "西港區", "七股區", "將軍區", "學甲區", "北門區", "新營區", "後壁區", "白河區", "東山區", "六甲區", "下營區", "柳營區", "鹽水區", "善化區", "大內區", "山上區", "新市區", "安定區"],
    "高雄市": ["新興區", "前金區", "苓雅區", "鹽埕區", "鼓山區", "旗津區", "前鎮區", "三民區", "楠梓區", "小港區", "左營區", "仁武區", "大社區", "岡山區", "路竹區", "阿蓮區", "田寮區", "燕巢區", "橋頭區", "梓官區", "彌陀區", "永安區", "湖內區", "鳳山區", "大寮區", "林園區", "鳥松區", "大樹區", "旗山區", "美濃區", "六龜區", "內門區", "杉林區", "甲仙區", "桃源區", "那瑪夏區", "茂林區", "茄萣區"],
    "基隆市": ["仁愛區", "信義區", "中正區", "中山區", "安樂區", "暖暖區", "七堵區"],
    "新竹市": ["東區", "北區", "香山區"],
    "新竹縣": ["竹北市", "竹東鎮", "新埔鎮", "關西鎮", "湖口鄉", "新豐鄉", "芎林鄉", "橫山鄉", "北埔鄉", "寶山鄉", "峨眉鄉", "尖石鄉", "五峰鄉"],
    "苗栗縣": ["苗栗市", "頭份市", "竹南鎮", "後龍鎮", "通霄鎮", "苑裡鎮", "造橋鄉", "西湖鄉", "頭屋鄉", "公館鄉", "銅鑼鄉", "三義鄉", "大湖鄉", "獅潭鄉", "三灣鄉", "南庄鄉", "卓蘭鎮"],
    "彰化縣": ["彰化市", "鹿港鎮", "和美鎮", "線西鄉", "伸港鄉", "福興鄉", "秀水鄉", "花壇鄉", "芬園鄉", "員林市", "溪湖鎮", "田中鎮", "大村鄉", "埔鹽鄉", "埔心鄉", "永靖鄉", "社頭鄉", "二水鄉", "北斗鎮", "二林鎮", "田尾鄉", "埤頭鄉", "芳苑鄉", "大城鄉", "竹塘鄉", "溪州鄉"],
    "南投縣": ["南投市", "埔里鎮", "草屯鎮", "竹山鎮", "集集鎮", "名間鄉", "鹿谷鄉", "中寮鄉", "魚池鄉", "國姓鄉", "水里鄉", "信義鄉", "仁愛鄉"],
    "雲林縣": ["斗六市", "斗南鎮", "虎尾鎮", "西螺鎮", "土庫鎮", "北港鎮", "古坑鄉", "大埤鄉", "莿桐鄉", "林內鄉", "二崙鄉", "崙背鄉", "麥寮鄉", "東勢鄉", "褒忠鄉", "台西鄉", "元長鄉", "四湖鄉", "口湖鄉", "水林鄉"],
    "嘉義市": ["東區", "西區"],
    "嘉義縣": ["太保市", "朴子市", "布袋鎮", "大林鎮", "民雄鄉", "溪口鄉", "新港鄉", "六腳鄉", "東石鄉", "義竹鄉", "鹿草鄉", "水上鄉", "中埔鄉", "竹崎鄉", "梅山鄉", "番路鄉", "大埔鄉", "阿里山鄉"],
    "屏東縣": ["屏東市", "三地門鄉", "霧台鄉", "瑪家鄉", "九如鄉", "里港鄉", "高樹鄉", "鹽埔鄉", "長治鄉", "麟洛鄉", "竹田鄉", "內埔鄉", "萬丹鄉", "泰武鄉", "來義鄉", "萬巒鄉", "崁頂鄉", "新埤鄉", "南州鄉", "林邊鄉", "東港鎮", "琉球鄉", "佳冬鄉", "新園鄉", "枋寮鄉", "枋山鄉", "春日鄉", "獅子鄉", "牡丹鄉", "車城鄉", "滿州鄉", "恆春鎮"],
    "宜蘭縣": ["宜蘭市", "羅東鎮", "蘇澳鎮", "頭城鎮", "礁溪鄉", "壯圍鄉", "員山鄉", "冬山鄉", "五結鄉", "三星鄉", "大同鄉", "南澳鄉"],
    "花蓮縣": ["花蓮市", "鳳林鎮", "玉里鎮", "新城鄉", "吉安鄉", "壽豐鄉", "光復鄉", "豐濱鄉", "瑞穗鄉", "富里鄉", "秀林鄉", "萬榮鄉", "卓溪鄉"],
    "台東縣": ["台東市", "成功鎮", "關山鎮", "卑南鄉", "鹿野鄉", "池上鄉", "東河鄉", "長濱鄉", "太麻里鄉", "大武鄉", "綠島鄉", "海端鄉", "延平鄉", "金峰鄉", "達仁鄉", "蘭嶼鄉"],
    "澎湖縣": ["馬公市", "湖西鄉", "白沙鄉", "西嶼鄉", "望安鄉", "七美鄉"],
    "金門縣": ["金城鎮", "金湖鎮", "金沙鎮", "金寧鄉", "烈嶼鄉", "烏坵鄉"],
    "連江縣": ["南竿鄉", "北竿鄉", "莒光鄉", "東引鄉"]
}

user_states = {}

def get_google_worksheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SPREADSHEET_ID).sheet1
    except: return None

def get_city_options(page=0):
    cities = list(TAIWAN_DATA.keys())
    start = page * 11
    end = start + 11
    current_cities = cities[start:end]
    items = [QuickReplyButton(action=MessageAction(label=c, text=c)) for c in current_cities]
    
    if end < len(cities):
        items.append(QuickReplyButton(action=MessageAction(label="更多縣市 ➔", text="更多縣市")))
    if page > 0:
        items.append(QuickReplyButton(action=MessageAction(label="⬅ 回前頁", text="回前頁")))
    return QuickReply(items=items)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try: handler.handle(body, signature)
    except InvalidSignatureError: abort(400)
    return 'OK'

# --- 1. 新增：加入好友即自動歡迎與引導 ---
@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text="感謝您加入！請點擊下方按鈕或輸入「我要報名」來開始建立您的資料。",
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="點我開始報名", text="我要報名"))
            ])
        )
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # --- 2. 觸發報名邏輯 ---
    if text in ["重新開始", "我要報名"]:
        user_states[user_id] = {"step": "ASK_NAME", "city_page": 0}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="好的，請輸入您的姓名："))
        return

    # 3. 如果狀態是 FINISHED，且不是要重新開始，則不回覆
    if user_id in user_states and user_states[user_id].get("step") == "FINISHED":
        return

    # --- 4. 自動偵測：非認識的訊息也自動啟動報名 ---
    if user_id not in user_states:
        user_states[user_id] = {"step": "ASK_NAME", "city_page": 0}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="您好！偵測到您尚未建立資料，請先輸入您的姓名："))
        return 

    state = user_states[user_id]

    if state["step"] == "ASK_NAME":
        state["name"] = text
        state["step"] = "ASK_CITY"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"{text} 您好！請選擇居住縣市：",
            quick_reply=get_city_options(0)
        ))

    elif state["step"] == "ASK_CITY":
        if text == "更多縣市":
            state["city_page"] += 1
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請選擇縣市：", quick_reply=get_city_options(state["city_page"])))
        elif text == "回前頁":
            state["city_page"] -= 1
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請選擇縣市：", quick_reply=get_city_options(state["city_page"])))
        elif text in TAIWAN_DATA:
            state["city"] = text
            state["step"] = "ASK_DISTRICT"
            districts = TAIWAN_DATA[text]
            items = [QuickReplyButton(action=MessageAction(label=d, text=d)) for d in districts[:11]]
            items.append(QuickReplyButton(action=MessageAction(label="其他/請手打", text="請直接輸入區名")))
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"請選擇 {text} 的行政區：", quick_reply=QuickReply(items=items)
            ))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請由選單選擇縣市。", quick_reply=get_city_options(state["city_page"])))

    elif state["step"] == "ASK_DISTRICT":
        if text == "請直接輸入區名":
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"好的，請直接輸入「{state['city']}」的行政區名稱："))
            return

        valid_districts = TAIWAN_DATA.get(state["city"], [])
        if text not in valid_districts:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"❌ 錯誤：『{text}』似乎不屬於『{state['city']}』。\n請重新輸入正確的行政區（例如：{valid_districts[0]}）："
            ))
            return

        state["district"] = text
        worksheet = get_google_worksheet()
        if worksheet:
            tw_time = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
            worksheet.append_row([tw_time, user_id, state["name"], state["city"], state["district"]])
            state["step"] = "FINISHED"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已收到您的相關資料，謝謝"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 系統暫時無法存取試算表。"))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
