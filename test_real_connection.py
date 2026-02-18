import shioaji as sj
from modules.real_executor import RealExecutor
from config.settings import Settings

print("🔌 連線 Shioaji API...")
api = sj.Shioaji()
api.login(
    api_key=Settings.SHIOAJI_API_KEY, 
    secret_key=Settings.SHIOAJI_SECRET_KEY
)

print("\n🚀 初始化 RealExecutor (自動掃描帳號 + 載入憑證)...")
# 注意: 不需要再傳入 api.stock_account 了
# 設定 dry_run=False 來測試憑證
try:
    executor = RealExecutor(api, dry_run=False)
except SystemExit:
    print("💀 初始化失敗 (可能是憑證問題)")
    exit(1)

if executor.account:
    print(f"✅ 綁定帳號: {executor.account.account_id}")
else:
    print("❌ 未綁定帳號")

print("\n💰 測試權益數 (Margin):")
print(f"   => ${executor.get_balance():,}")

# 測試一個市價單 (價格傳 0)
print("\n📝 測試下單參數生成 (Dry Run 模擬):")
executor.dry_run = True # 臨時開啟 Dry Run 以免真的下單
success, price, msg = executor._execute_impl("BUY", 1, 0) # 0 = 市價
print(f"   => 市價單結果: {msg}")

success, price, msg = executor._execute_impl("SELL", 1, 23000) # 限價
print(f"   => 限價單結果: {msg}")

api.logout()