import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

class Settings:
    # --- 帳戶與 API 設定 ---
    API_KEY = os.getenv("SHIOAJI_API_KEY")
    API_SECRET = os.getenv("SHIOAJI_SECRET_KEY")
    ACC_ID = os.getenv("SHIOAJI_ACC_ID")  # 帳號 ID (身分證字號或子帳號)
    
    # Telegram 設定
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # --- 交易標的設定 ---
    # 商品代碼 (例如 'TMF') - 這裡只寫代碼，具體合約(如 TMF202603)由程式動態抓取或指定
    SYMBOL_CODE = "TMF" 
    EXCHANGE = "TAIFEX"

    # --- 策略參數 (禁止在策略程式碼中寫死) ---
    STRATEGY_MA_FAST = 10
    STRATEGY_MA_SLOW = 240
    STOP_LOSS_POINT = 400  # 硬止損點數
    
    # --- 系統設定 ---
    LOG_LEVEL = "INFO"
    TIMEZONE = "Asia/Taipei"

    # 檢查必要設定是否存在
    @classmethod
    def validate(cls):
        required_vars = ["API_KEY", "API_SECRET", "TELEGRAM_TOKEN"]
        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            raise ValueError(f"缺少必要環境變數: {', '.join(missing)}")

# 驗證設定
Settings.validate()