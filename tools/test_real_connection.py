import shioaji as sj
from modules.real_executor import RealExecutor
from config.settings import Settings
import sys

# ---------------------------------------------------------
# 1. 連線 Shioaji
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# 2. 初始化 Executor (自動掃描帳號 + 載入憑證)
# ---------------------------------------------------------
print("\n🚀 [測試] 初始化 RealExecutor...")
try:
    # 設定 dry_run=False 來測試憑證載入是否正常
    executor = RealExecutor(api, dry_run=False)
except SystemExit:
    print("💀 [測試] 初始化失敗 (憑證錯誤)")
    sys.exit(1)

if executor.account:
    print(f"✅ [測試] 已綁定帳號: {executor.account.account_id}")
else:
    print("❌ [測試] 未綁定帳號 (嚴重錯誤)")
    sys.exit(1)

# ---------------------------------------------------------
# 3. 測試功能
# ---------------------------------------------------------

# --- 權益數 ---
print("\n💰 [測試 1] 查詢權益數 (Margin):")
balance = executor.get_balance()
print(f"   => ${balance:,} TWD")

# --- 持倉數 (新增的部分) ---
print("\n📊 [測試 2] 查詢真實持倉 (Positions):")
try:
    # 這裡會呼叫 api.list_positions 並過濾 TMF
    position = executor.get_position()
    
    pos_text = "⚪️ 空手 (Flat)"
    if position > 0: pos_text = f"🔴 多單 {position} 口"
    elif position < 0: pos_text = f"🟢 空單 {abs(position)} 口"
    
    print(f"   => TMF 持倉: {position}")
    print(f"   => 狀態: {pos_text}")

except Exception as e:
    print(f"❌ [測試] 查詢持倉失敗: {e}")

# --- 合約抓取 ---
print("\n📝 [測試 3] 取得合約資訊:")
contract = executor._get_contract()
if contract:
    print(f"   => {contract.name} ({contract.code})")
else:
    print("   => 失敗")

# --- 下單參數模擬 ---
print("\n⚡ [測試 4] 下單參數模擬 (Dry Run):")
# 為了不真的下單，我們臨時開啟 dry_run
#xecutor.dry_run = True 

# 測試市價 (Price=0)
success, price, msg = executor._execute_impl("BUY", 1, 0)
print(f"   => 市價單: {msg}")

# 測試限價 (Price=23000)
success, price, msg = executor._execute_impl("SELL", 1, 33900)
print(f"   => 限價單: {msg}")

# ---------------------------------------------------------
# 4. 結束
# ---------------------------------------------------------
print("\n🏁 測試結束，登出 API。")
api.logout()