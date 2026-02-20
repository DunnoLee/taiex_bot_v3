import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

class Settings:
    # --- 帳戶與 API 設定 ---
    SHIOAJI_API_KEY = os.getenv("SHIOAJI_API_KEY")
    SHIOAJI_SECRET_KEY = os.getenv("SHIOAJI_SECRET_KEY")
    SHIOAJI_ACC_ID = os.getenv("SHIOAJI_ACC_ID")  # 帳號 ID (身分證字號或子帳號)
    
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

    # --- 系統設定 ---
    LOG_LEVEL = "INFO"
    TIMEZONE = "Asia/Taipei"

    DRY_RUN=True

    # 檢查必要設定是否存在
    @classmethod
    def validate(cls):
        required_vars = ["SHIOAJI_API_KEY", "SHIOAJI_SECRET_KEY", "TELEGRAM_TOKEN"]
        missing = [var for var in required_vars if not getattr(cls, var)]
        if missing:
            raise ValueError(f"缺少必要環境變數: {', '.join(missing)}")



# 驗證設定
Settings.validate()