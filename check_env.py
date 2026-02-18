import sys
import shioaji
import pandas
import dotenv

def check_environment():
    print("🔍 環境檢查中...")
    print("-" * 30)
    
    # 1. 檢查 Python 版本
    py_ver = sys.version_info
    print(f"🐍 Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    
    if py_ver.major == 3 and py_ver.minor == 12:
        print("✅ Python 版本正確 (3.12)")
    else:
        print(f"⚠️ 警告: 你正在使用 Python {py_ver.major}.{py_ver.minor}，建議切換回 3.12")

    # 2. 檢查套件導入
    print(f"📦 Shioaji Version: {shioaji.__version__}")
    print(f"📦 Pandas Version: {pandas.__version__}")
    
    try:
        from config.settings import Settings
        print(f"✅ Settings 載入成功 (API Key 前三碼: {Settings.SHIOAJI_API_KEY[:3]}***)")
    except Exception as e:
        print(f"❌ Settings 載入失敗: {e}")

    print("-" * 30)
    print("🎉 環境準備完成！")

if __name__ == "__main__":
    check_environment()