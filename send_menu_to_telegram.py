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
        print(f"⚠️ [{seq}] API 호출 중 오류 발생: {e}")
        return None

def format_menu(menu_item):
    """메뉴 아이템을 보기 좋은 텍스트로 변환"""
    if not menu_item:
        return "🍽 등록된 메뉴가 없습니다."
        
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
                # 불필요한 줄바꿈 정리
                clean_content = content.replace('\r\n', '\n').strip()
                message_lines.append(clean_content)
            message_lines.append("")
            
    if not found_any:
        return "🍽 등록된 메뉴가 없습니다."
        
    return "\n".join(message_lines).strip()

def send_to_telegram(text):
    """텔레그램으로 메시지를 전송합니다."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ 설정 오류: TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 환경 변수가 없습니다.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        res_json = response.json()
        if not res_json.get("ok"):
            print(f"❌ 텔레그램 서버 응답 오류: {res_json.get('description')}")
        return res_json.get("ok", False)
    except Exception as e:
        print(f"⚠️ 텔레그램 메시지 전송 중 예외 발생: {e}")
        return False

def main():
    print("🚀 신구대학교 식단 크롤러 시작")
    
    kst_now = get_kst_now()
    target_date = kst_now
    
    # 디버깅을 위해 다양한 날짜 형식 준비
    date_formats = [
        target_date.strftime("%Y%m%d"),    # 20260416
        target_date.strftime("%Y.%m.%d")  # 2026.04.16
    ]
    display_date = target_date.strftime("%Y년 %m월 %d일 (%a)")

    print(f"📅 대상 날짜: {display_date} (포맷: {date_formats})")
    
    telegram_message = f"🏫 <b>신구대학교 오늘의 학식</b>\n"
    telegram_message += f"📅 {display_date}\n\n"

    total_success = 0
    for bistro in BISTROS:
        bistro_name = bistro['name']
        bistro_seq = bistro['seq']
        bistro_icon = bistro['icon']
        
        print(f"🔍 {bistro_name} (SEQ: {bistro_seq}) 데이터 요청 중...")
        json_data = get_menu_data(bistro_seq, target_date)
        
        todays_item = None
        if json_data:
            # API 응답 구조 분석 (data 키가 있을 수도 있고, 자체가 리스트일 수도 있음)
            items = []
            if isinstance(json_data, dict):
                items = json_data.get('data', [])
                if not items and 'STD_DT' in json_data: # 단일 객체인 경우
                    items = [json_data]
            elif isinstance(json_data, list):
                items = json_data
            
            print(f"   ∟ 총 {len(items)}개의 데이터 수신")
            
            for item in items:
                # 날짜 키 확인
                item_date = str(item.get('STD_DT', '')).replace('.', '').replace('-', '')
                if not item_date:
                    ym = str(item.get('STD_YM', '')).replace('.', '').replace('-', '')
                    dd = str(item.get('STD_DD', ''))
                    if ym and dd:
                        item_date = f"{ym}{dd}"
                
                if item_date in date_formats:
                    todays_item = item
                    break
        
        menu_text = format_menu(todays_item)
        if todays_item:
            total_success += 1
            print(f"   ✅ {bistro_name}: 식단 찾음")
        else:
            print(f"   ℹ️ {bistro_name}: 해당 날짜 식단 없음")
            
        telegram_message += f"{bistro_icon} <b>{bistro_name}</b>\n{menu_text}\n\n"

    telegram_message += "맛있게 드세요! 😋"

    # 메시지 전송
    print("📤 텔레그램 전송 중...")
    if send_to_telegram(telegram_message):
        print("🎉 모든 작업 성공!")
        sys.exit(0)
    else:
        print("终止: 텔레그램 전송에 실패했습니다.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ 예기치 못한 치명적 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
