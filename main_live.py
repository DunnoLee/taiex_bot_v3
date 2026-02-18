import sys
import time
import shioaji as sj
from config.settings import Settings
from modules.real_executor import RealExecutor
from modules.shioaji_feeder import ShioajiFeeder
from core.engine import BotEngine

def main():
    print(f"🚀 TaiEx Bot V3 [Live Mode] 啟動中...")
    print(f"==========================================")

    # -----------------------------------------------------
    # 1. 建立 Shioaji 連線
    # -----------------------------------------------------
    print("🔌 [系統] 正在連線 Shioaji API...")
    api = sj.Shioaji()
    try:
        api.login(
            api_key=Settings.SHIOAJI_API_KEY, 
            secret_key=Settings.SHIOAJI_SECRET_KEY
        )
        print("✅ [系統] API 連線成功！")
    except Exception as e:
        print(f"❌ [系統] API 連線失敗: {e}")
        sys.exit(1)

    # -----------------------------------------------------
    # 2. 初始化 真實執行器 (RealExecutor)
    # -----------------------------------------------------
    # 這裡的 dry_run 取決於 .env 設定，這是你的最後一道保險
    print(f"🛡️ [系統] 交易模式: {'DRY RUN (模擬演習)' if Settings.DRY_RUN else 'LIVE (真槍實彈)'}")
    
    try:
        # RealExecutor 會自動掃描帳號、載入憑證(如果是Live)
        executor = RealExecutor(api, dry_run=Settings.DRY_RUN)
    except SystemExit:
        print("💀 [系統] Executor 初始化失敗，程式終止。")
        sys.exit(1)

    if not executor.account:
        print("❌ [系統] 無法綁定期貨帳號，請檢查帳戶狀態。")
        sys.exit(1)

    print(f"💳 [帳號] 綁定成功: {executor.account.account_id}")
    print(f"💰 [權益] 目前權益數: ${executor.get_balance():,}")

    # -----------------------------------------------------
    # 3. 初始化 行情餵食 (ShioajiFeeder)
    # -----------------------------------------------------
    feeder = ShioajiFeeder(api)

    # -----------------------------------------------------
    # 4. 啟動 機器人引擎 (Engine)
    # -----------------------------------------------------
    # Engine 會把 Feeder 的 Tick 轉成 Bar，再餵給策略，最後叫 Executor 下單
    target_symbol = getattr(Settings, "TARGET_CONTRACT", "TMF202603")
    bot = BotEngine(feeder, executor, symbol=target_symbol)

    # -----------------------------------------------------
    # 5. 數據預載 (Warm-up) - 雙軌機制的第一步
    # -----------------------------------------------------
    print("\n📂 [資料] 正在載入歷史資料 (Cold Data)...")
    # 這裡先讀 CSV，讓 MA 線有基礎
    bot.load_warmup_data("data/history/TMF_History.csv")

    # TODO: 未來這裡要加入 Step 5.5: API Backfill (溫數據)
    # bot.fetch_missing_bars_from_api() 

    # -----------------------------------------------------
    # 6. 正式開跑
    # -----------------------------------------------------
    print("\n🟢 [系統] 引擎啟動，開始監聽行情...")
    bot.start() 
    # bot.start() 內部會啟動 feeder，並進入無窮迴圈(如果是 Live 模式)
    # 除非遇到 Ctrl+C 或 /kill 指令

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 [系統] 使用者強制中斷")
        sys.exit(0)