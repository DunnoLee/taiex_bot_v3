import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

class Settings:
    # --- 帳戶與 API 設定 ---
    API_KEY = os.getenv("SHIOAJI_API_KEY")
    API_SECRET = os.getenv("SHIOAJI_SECRET_KEY")
    ACC_ID = os.getenv("SHIOAJI_ACC_ID")  # 帳號 ID (身分證字號或子帳號)
    
    _cert_path = os.getenv("SHIOAJI_CERT_PATH")
    
    # 如果有設定路徑，就把它轉成電腦的絕對路徑
    if _cert_path:
        SHIOAJI_CERT_PATH = os.path.abspath(_cert_path)
    else:
        SHIOAJI_CERT_PATH = None
        
    SHIOAJI_CERT_PASSWORD = os.getenv("SHIOAJI_CERT_PASSWORD")
    SHIOAJI_PERSON_ID = os.getenv("SHIOAJI_PERSON_ID")


    # Telegram 設定
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # --- 交易標的設定 ---
    # 商品代碼 (例如 'TMF') - 這裡只寫代碼，具體合約(如 TMF202603)由程式動態抓取或指定
    SYMBOL_CODE = "TMF" 
    EXCHANGE = "TAIFEX"
    TARGET_CONTRACT = os.getenv("TARGET_CONTRACT", "TMF202603")

    # --- 策略參數 (冠軍組合 2026-02-16) ---
    # Fast: 30 * 5min = 150 min
    # Slow: 240 * 5min = 1200 min
    STRATEGY_MA_FAST = 30
    STRATEGY_MA_SLOW = 240
    
    # 記得我們還有 Threshold 跟 Resample，這兩個原本沒寫在 Settings 裡
    # 建議加進去，或是直接改策略預設值
    STRATEGY_THRESHOLD = 5.0
    STRATEGY_RESAMPLE_MIN = 5

    # --- 風險控管 ---
    STOP_LOSS_POINT = 300.0     # 硬止損 (點數)
    
    # --- 系統設定 ---
    LOG_LEVEL = "INFO"
    TIMEZONE = "Asia/Taipei"

    DRY_RUN=True

    # 檢查必要設定是否存在
    @classmethod
    def validate(cls):
        required_vars = ["API_KEY", "API_SECRET", "TELEGRAM_TOKEN"]
        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            raise ValueError(f"缺少必要環境變數: {', '.join(missing)}")



# 驗證設定
Settings.validate()