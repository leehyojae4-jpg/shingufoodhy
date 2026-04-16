import urllib.request
import json
import os

# -----------------------------------------------------------------------------
# 설정 / Configuration
# -----------------------------------------------------------------------------
# 'telegram api 활용방법.txt' 파일 내용에서 추출한 토큰과 ID입니다.
TELEGRAM_BOT_TOKEN = '8768200515:AAFfCvsejDrc6yL1jXhXVfCC8xtNhB7Bwz8'
TELEGRAM_CHAT_ID = '8763479451'

def send_to_telegram(text):
    """텔레그램으로 메시지를 전송합니다."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # 텔레그램 메시지 길이 제한(약 4096자)을 고려하여 필요시 분할 전송이 필요할 수 있으나,
    # 현재 파일은 약 3200바이트이므로 한 번에 전송 가능합니다.
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    data_json = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=data_json, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result.get("ok", False)
    except Exception as e:
        print(f"전송 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    file_path = "telegram api 활용방법.txt"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
    else:
        print(f"Reading file: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        print("Attempting to send to Telegram...")
        # 마크다운 특수문자 처리가 복잡할 수 있으므로, 
        # 실패 시 parse_mode 없이 재시도하는 로직을 추가합니다.
        if send_to_telegram(content):
            print("Success: File content sent to Telegram!")
        else:
            print("Markdown send failed, retrying with plain text...")
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": content}
            data_json = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_json, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req) as response:
                    if json.loads(response.read().decode()).get("ok", False):
                        print("Success: Sent as plain text!")
                    else:
                        print("Error: Failed to send message.")
            except Exception as e:
                print(f"Retry error: {e}")
