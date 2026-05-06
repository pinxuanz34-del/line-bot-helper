import os
import json
import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# --- 初始化設定 ---
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# Google Sheets 初始化
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(os.getenv('SPREADSHEET_ID')).sheet1

# --- 全台灣行政區資料庫 ---
# 這裡定義了 22 縣市與其對應區域
TAIWAN_DATA = {
    "基隆市": ["仁愛區", "信義區", "中正區", "中山區", "安樂區", "暖暖區", "七堵區"],
    "台北市": ["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區"],
    "新北市": ["板橋區", "三重區", "中和區", "永和區", "新莊區", "新店區", "土城區", "蘆洲區", "樹林區", "汐止區", "三峽區", "淡水區", "鶯歌區", "五股區", "泰山區", "林口區", "深坑區", "石碇區", "坪林區", "三芝區", "石門區", "八里區", "平溪區", "雙溪區", "貢寮區", "金山區", "萬里區", "烏來區", "瑞芳區"],
    "桃園市": ["桃園區", "中壢區", "大溪區", "楊梅區", "蘆竹區", "大園區", "龜山區", "八德區", "龍潭區", "平鎮區", "新屋區", "觀音區", "復興區"],
    "新竹市": ["東區", "北區", "香山區"],
    "新竹縣": ["竹北市", "竹東鎮", "新埔鎮", "關西鎮", "湖口鄉", "新豐鄉", "芎林鄉", "橫山鄉", "北埔鄉", "寶山鄉", "峨眉鄉", "尖石鄉", "五峰鄉"],
    "苗栗縣": ["苗栗市", "頭份市", "竹南鎮", "後龍鎮", "通霄鎮", "苑裡鎮", "卓蘭鎮", "造橋鄉", "西湖鄉", "頭屋鄉", "公館鄉", "銅鑼鄉", "三義鄉", "大湖鄉", "獅潭鄉", "三灣鄉", "南庄鄉", "泰安鄉"],
    "台中市": ["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區", "太平區", "大里區", "霧峰區", "烏日區", "豐原區", "後里區", "石岡區", "東勢區", "和平區", "新社區", "潭子區", "大雅區", "神岡區", "大肚區", "沙鹿區", "龍井區", "梧棲區", "清水區", "大甲區", "外埔區", "大安區"],
    "彰化縣": ["彰化市", "鹿港鎮", "和美鎮", "線西鄉", "伸港鄉", "福興鄉", "秀水鄉", "花壇鄉", "芬園鄉", "員林市", "溪湖鎮", "田中鎮", "大村鄉", "埔鹽鄉", "埔心鄉", "永靖鄉", "社頭鄉", "二水鄉", "北斗鎮", "二林鎮", "田尾鄉", "埤頭鄉", "芳苑鄉", "大城鄉", "竹塘鄉", "溪州鄉"],
    "南投縣": ["南投市", "埔里鎮", "草屯鎮", "竹山鎮", "集集鎮", "名間鄉", "鹿谷鄉", "中寮鄉", "魚池鄉", "國姓鄉", "水里鄉", "信義鄉", "仁愛鄉"],
    "雲林縣": ["斗六市", "斗南鎮", "虎尾鎮", "西螺鎮", "土庫鎮", "北港鎮", "古坑鄉", "大埤鄉", "莿桐鄉", "林內鄉", "二崙鄉", "崙背鄉", "麥寮鄉", "東勢鄉", "褒忠鄉", "台西鄉", "元長鄉", "四湖鄉", "口湖鄉", "水林鄉"],
    "嘉義市": ["東區", "西區"],
    "嘉義縣": ["太保市", "朴子市", "布袋鎮", "大林鎮", "民雄鄉", "溪口鄉", "新港鄉", "六腳鄉", "東石鄉", "義竹鄉", "鹿草鄉", "水上鄉", "中埔鄉", "竹崎鄉", "梅山鄉", "番路鄉", "大埔鄉", "阿里山鄉"],
    "台南市": ["中西區", "東區", "南區", "北區", "安平區", "安南區", "永康區", "歸仁區", "新化區", "左鎮區", "玉井區", "楠西區", "南化區", "仁德區", "關廟區", "龍崎區", "官田區", "麻豆區", "佳里區", "西港區", "七股區", "將軍區", "學甲區", "北門區", "新營區", "後壁區", "白河區", "東山區", "六甲區", "下營區", "柳營區", "鹽水區", "善化區", "大內區", "山上區", "新市區", "安定區"],
    "高雄市": ["新興區", "前金區", "苓雅區", "鹽埕區", "鼓山區", "旗津區", "前鎮區", "三民區", "楠梓區", "小港區", "左營區", "仁武區", "大社區", "岡山區", "路竹區", "阿蓮區", "田寮區", "燕巢區", "橋頭區", "梓官區", "彌陀區", "永安區", "湖內區", "鳳山區", "大寮區", "林園區", "鳥松區", "大樹區", "旗山區", "美濃區", "六龜區", "內門區", "杉林區", "甲仙區", "桃源區", "那瑪夏區", "茂林區", "茄萣區"],
    "屏東縣": ["屏東市", "三地門鄉", "霧台鄉", "瑪家鄉", "九如鄉", "里港鄉", "高樹鄉", "鹽埔鄉", "長治鄉", "麟洛鄉", "竹田鄉", "內埔鄉", "萬丹鄉", "潮州鎮", "泰武鄉", "來義鄉", "萬巒鄉", "崁頂鄉", "新埤鄉", "南州鄉", "林邊鄉", "東港鎮", "琉球鄉", "佳冬鄉", "新園鄉", "枋寮鄉", "枋山鄉", "春日鄉", "獅子鄉", "車城鄉", "牡丹鄉", "恆春鎮", "滿州鄉"],
    "宜蘭縣": ["宜蘭市", "羅東鎮", "蘇澳鎮", "頭城鎮", "礁溪鄉", "壯圍鄉", "員山鄉", "冬山鄉", "五結鄉", "三星鄉", "大同鄉", "南澳鄉"],
    "花蓮縣": ["花蓮市", "鳳林鎮", "玉里鎮", "新城鄉", "吉安鄉", "壽豐鄉", "光復鄉", "豐濱鄉", "瑞穗鄉", "富里鄉", "秀林鄉", "萬榮鄉", "卓溪鄉"],
    "台東縣": ["台東市", "成功鎮", "關山鎮", "卑南鄉", "鹿野鄉", "池上鄉", "東河鄉", "長濱鄉", "太麻里鄉", "大武鄉", "綠島鄉", "海端鄉", "延平鄉", "金峰鄉", "達仁鄉", "蘭嶼鄉"],
    "澎湖縣": ["馬公市", "湖西鄉", "白沙鄉", "西嶼鄉", "望安鄉", "七美鄉"],
    "金門縣": ["金城鎮", "金湖鎮", "金沙鎮", "金寧鄉", "烈嶼鄉", "烏坵鄉"],
    "連江縣": ["南竿鄉", "北竿鄉", "莒光鄉", "東引鄉"]
}

user_states = {}

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
    msg = event.message.text.strip()

    # 初始化狀態
    if user_id not in user_states:
        user_states[user_id] = {"state": "IDLE"}

    current_state = user_states[user_id]["state"]

    # 開始對話
    if msg == "開始" or current_state == "IDLE":
        user_states[user_id] = {"state": "ASK_NAME"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="您好！請問您的姓名是？"))
        return

    # 1. 處理姓名
    if current_state == "ASK_NAME":
        user_states[user_id]["name"] = msg
        user_states[user_id]["state"] = "ASK_COUNTY"
        # 準備縣市選單 (前12個)
        counties = list(TAIWAN_DATA.keys())
        items = [QuickReplyButton(action=MessageAction(label=c, text=c)) for c in counties[:12]]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{msg} 您好！請選擇您所在的【縣市】？", quick_reply=QuickReply(items=items))
        )

    # 2. 處理縣市 (嚴格驗證)
    elif current_state == "ASK_COUNTY":
        if msg in TAIWAN_DATA:
            user_states[user_id]["county"] = msg
            user_states[user_id]["state"] = "ASK_DISTRICT"
            # 準備該縣市區域選單 (前12個)
            districts = TAIWAN_DATA[msg]
            items = [QuickReplyButton(action=MessageAction(label=d, text=d)) for d in districts[:12]]
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"好的，那【{msg}】的哪個【鄉鎮市區】呢？", quick_reply=QuickReply(items=items))
            )
        else:
            # 偵錯：不在名單內
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="抱歉，找不到該縣市。請直接點選下方選單中的正確縣市名稱："))

    # 3. 處理區域 (偵錯與 Google Sheets 寫入)
    elif current_state == "ASK_DISTRICT":
        county = user_states[user_id]["county"]
        if msg in TAIWAN_DATA[county]:
            # 驗證成功！
            name = user_states[user_id]["name"]
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            try:
                # 寫入 Google Sheets
                sheet = get_sheet()
                sheet.append_row([now, name, county, msg])
                
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"✅ 登記成功！\n姓名：{name}\n地點：{county}{msg}\n\n資料已存入 Google 表格。")
                )
                user_states[user_id] = {"state": "IDLE"} # 重設狀態
            except Exception as e:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="系統繁忙，請稍後再試。"))
        else:
            # --- 偵錯功能核心 ---
            found_county = None
            for c, ds in TAIWAN_DATA.items():
                if msg in ds:
                    found_county = c
                    break
            
            if found_county:
                error_txt = f"❌ 偵測到錯誤！\n【{msg}】位於【{found_county}】，不是【{county}】。\n請重新輸入正確的 {county} 區域："
            else:
                error_txt = f"❌ 找不到區域【{msg}】。\n請確認名稱（如：中正區）並重新輸入 {county} 的正確區域："
                
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=error_txt))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
