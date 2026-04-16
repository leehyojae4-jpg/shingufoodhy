import os
import requests
import datetime
import urllib3
import ssl
import json
import sys
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_

# -----------------------------------------------------------------------------
# 설정 / Configuration (GitHub Secrets에서 가져오기)
# -----------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# 신구대학교 API URL
API_URL = "https://www.shingu.ac.kr/ajaxf/FR_BST_SVC/BistroCarteInfo.do"
MENU_ID = "1630"

# 식당 정보
BISTROS = [
    {"name": "교직원식당", "seq": "6", "icon": "🏫"},
    {"name": "학생식당(미래창의관)", "seq": "5", "icon": "🎓"},
    {"name": "학생식당(서관)", "seq": "7", "icon": "🍱"}
]

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -----------------------------------------------------------------------------
# SSL Adapter
# -----------------------------------------------------------------------------
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl_.create_urllib3_context(ciphers='DEFAULT:@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=ctx
        )

def get_kst_now():
    """한국 시간(KST) 현재 시간 반환"""
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)

def get_menu_data(seq, target_date):
    """API를 통해 특정 식당의 주간 식단 데이터를 가져옴"""
    monday = target_date - datetime.timedelta(days=target_date.weekday())
    friday = monday + datetime.timedelta(days=6)
    
    start_day_str = monday.strftime("%Y.%m.%d")
    end_day_str = friday.strftime("%Y.%m.%d")
    
    payload = {
        'MENU_ID': MENU_ID,
        'BISTRO_SEQ': seq,
        'START_DAY': start_day_str,
        'END_DAY': end_day_str
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    
    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())
    
    try:
        response = session.post(API_URL, data=payload, headers=headers, verify=False, timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[{seq}] API 호출 실패: {e}")
        return None

def format_menu(menu_item):
    """메뉴 아이템을 보기 좋은 텍스트로 변환"""
    message_lines = []
    found_any = False
    
    for i in range(1, 7):
        nm_key = f'CARTE{i}_NM'
        cont_key = f'CARTE{i}_CONT'
        
        title = (menu_item.get(nm_key) or '').strip()
        content = (menu_item.get(cont_key) or '').strip()
        
        if title or content:
            found_any = True
            if title:
                message_lines.append(f"🔸 <b>{title}</b>")
            if content:
                content = content.replace('\r\n', '\n')
                message_lines.append(content)
            message_lines.append("")
            
    if not found_any:
        return "🍽 등록된 메뉴가 없습니다."
        
    return "\n".join(message_lines).strip()

def send_to_telegram(text):
    """텔레그램으로 메시지를 전송합니다."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 오류: TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 환경 변수가 설정되지 않았습니다.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_json = response.json()
        if not res_json.get("ok"):
            print(f"❌ 텔레그램 응답 에러: {res_json.get('description')}")
        return res_json.get("ok", False)
    except Exception as e:
        print(f"텔레그램 전송 오류: {e}")
        return False

def main():
    kst_now = get_kst_now()
    target_date = kst_now
    target_date_key = target_date.strftime("%Y%m%d")
    display_date = target_date.strftime("%Y년 %m월 %d일 (%a)")

    print(f"📅 날짜: {display_date}")
    
    telegram_message = f"🏫 <b>신구대학교 오늘의 학식</b>\n"
    telegram_message += f"📅 {display_date}\n\n"

    success_count = 0
    for bistro in BISTROS:
        bistro_name = bistro['name']
        bistro_seq = bistro['seq']
        bistro_icon = bistro['icon']
        
        print(f"🔍 {bistro_name} 식단 가져오는 중...")
        json_data = get_menu_data(bistro_seq, target_date)
        menu_content = "❌ 식단 데이터가 없습니다."
        
        if json_data:
            items = []
            if isinstance(json_data, dict) and 'data' in json_data:
                items = json_data['data']
            elif isinstance(json_data, list):
                items = json_data
            
            todays_item = None
            for item in items:
                item_date = item.get('STD_DT')
                if not item_date:
                    ym = item.get('STD_YM', '').replace('.', '')
                    dd = item.get('STD_DD', '')
                    if ym and dd:
                        item_date = f"{ym}{dd}"
                
                if item_date == target_date_key:
                    todays_item = item
                    break
            
            if todays_item:
                menu_content = format_menu(todays_item)
                success_count += 1
        
        telegram_message += f"{bistro_icon} <b>{bistro_name}</b>\n{menu_content}\n\n"

    telegram_message += "맛있게 드세요! 😋"

    if success_count > 0:
        print("🚀 텔레그램으로 전송 시도 중...")
        if send_to_telegram(telegram_message):
            print("✅ 성공: 오늘의 식단이 텔레그램으로 전송되었습니다!")
            sys.exit(0)
        else:
            print("❌ 실패: 메시지 전송에 실패했습니다.")
            sys.exit(1)
    else:
        print("❌ 실패: 식단 데이터를 하나도 찾을 수 없습니다.")
        # 데이터가 없을 때는 에러는 아니지만 전송은 안 함 (0으로 종료하거나 상황에 맞게 조절)
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"💥 치명적 오류 발생: {e}")
        sys.exit(1)
