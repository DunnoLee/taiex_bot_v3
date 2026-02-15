# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.10+ / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures)
> **Architecture:** Event-Driven (DataFeeder -> Strategy -> Execution)

## 1. 核心哲學 (Core Philosophy)
1.  **Strict Modularity:** - `Strategy` 絕對不可包含 `shioaji` API 代碼。
    - `Execution` 負責處理 API、滑價與重連，策略不需關心。
    - `Commander` (Telegram) 只發送控制訊號，不修改策略變數。
2.  **Simulation Parity:** - `Mock Replay` (回測/模擬) 必須使用與 `Live` (實盤) 完全相同的 `DataFeeder` 介面。
    - 系統應無法區分當前是「週六的回測」還是「週三的實盤」。
3.  **Config Centralization:**
    - 所有參數 (MA 週期、止損點數、商品代碼) 必須在 `config/settings.py` 定義，禁止 Hard-code。

## 2. 系統架構 (Architecture)
* **DataFeeder:** 統一數據源接口 (Live: Shioaji / Backtest: CSV)。
* **Event Engine:** 系統骨幹，傳遞 `TickEvent`, `BarEvent`, `SignalEvent`。
* **Strategy:** 純邏輯計算 (Input: Bar -> Output: Signal)。
* **Execution:** 下單執行與倉位同步。

## 3. 開發進度 (Development Log)
- [x] **Phase 0:** Project Initialization & Clean Slate.
- [ ] **Phase 1: Skeleton & Data Flow**
    - [ ] Create `config/settings.py`
    - [ ] Define Event classes in `core/event.py`
    - [ ] Implement basic `DataFeeder` interface
- [ ] **Phase 2: Strategy Porting** (Pure logic, no API)
- [ ] **Phase 3: Mock Replay Environment**
- [ ] **Phase 4: Live Connection (Shioaji)**

## 3.5 開發環境規範 (Environment Specs)
* **Python Version:** 3.12 (Strictly enforced to avoid Shioaji/Pydantic conflicts)
* **OS:** macOS (Apple Silicon M-series optimized)
* **Virtual Env:** `.venv` in project root
* **Key Dependencies:**
    - `shioaji`: API interaction
    - `pandas`: Data manipulation
    - `python-dotenv`: Environment variable management
    - `matplotlib` / `mplfinance`: Visualization (Planned)
    
## 4. 當前狀態 (Current Context)
* **Last Updated:** 2026-02-15
* **Focus:** Building the skeleton (`config` and `event` classes).
* **User Constraints:** VS Code, Mac, Git Flow.

---
*此檔案由 AI 維護，作為長期記憶與架構守門員。每次重大更新請同步修改此檔。*