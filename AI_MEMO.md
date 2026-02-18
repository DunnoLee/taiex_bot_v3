# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures) - Point Value: 10 TWD, Fee: 22 TWD.
> **Architecture:** Engine-Centric (Feeder -> Engine -> Strategy -> Executor)

## 0. 開發協議 (Development Protocol) - STRICT
* **Logic Persistence:** DO NOT silently refactor user-defined logic.
* **Engine-First:** All business logic resides in `core/engine.py`. `main_live` is the MASTER branch; `main_simulation` is the SHADOW branch.
* **Consistency:** Mock and Real executors must share logic via `BaseExecutor`.

## 1. 核心哲學 (Core Philosophy)
1.  **Main_Live is King:** All logic is designed for real execution first. Simulation exists only to verify the live code path.
2.  **Shadow Ledger:** `BaseExecutor` handles all PnL/Position logic. `RealExecutor` only handles IO.
3.  **Data-Driven:** Parameters verified by 70k bars backtest (MA 30/240).

## 2. 系統架構 (System Architecture)
* **Brain:** `core/engine.py` (Smart Order Logic, Telegram, Data Flow).
* **Execution:**
    * `BaseExecutor`: Shared logic (Pyramiding, PnL, Position tracking).
    * `RealExecutor` (V3.7): **Production Ready**.
        * Auto-scans `FutureAccount` (no manual binding).
        * Validates CA Cert on startup (Exit on failure).
    * `MockExecutor`: Simple "Return True" dummy.

### 2.1 Shioaji API 實戰規範 (API Protocol) - CRITICAL
* **Order Types:**
    * **Market Order (MKT):** MUST use `OrderType.IOC` (Immediate-or-Cancel).
    * **Limit Order (LMT):** MUST use `OrderType.ROD` (Rest-of-Day).
    * *Violation of this rule causes immediate order rejection.*
* **Data Types:**
    * API returns `Decimal` types. MUST convert to `float` or `int` immediately upon receipt to prevent serialization errors.
* **Account Binding:**
    * Do not assume default account. Must iterate `api.list_accounts()` and find `account.FutureAccount`.

## 3. 獲利模型 (The Holy Grail Parameters)
* **Strategy:** MA(30/240) + Filter(5.0) + SL(300).
* **Performance:** Net Profit **+$69,520 TWD** (Win Rate ~36%).

## 4. 開發日誌 (Development Log)
- [x] **Phase 1-6:** Foundation, Interactive Commander.
- [x] **Phase 7:** **Engine Refactoring & Tools** (Recorder, Visualizer).
- [x] **Phase 8:** **Executor Architecture (Completed)**
    * [x] Implemented `BaseExecutor` (Shadow Ledger).
    * [x] Implemented `RealExecutor` V3.7 with proven logic (ROD/IOC, Account Scan, Cert Check).
    * [x] Verified connection with `test_real_connection.py`.
- [ ] **Phase 9:** **Dual-Track Data Feed** (Next Step)
    * [ ] Implement API Backfill (Hot Data) to bridge CSV and Real-time.

## 5. 待辦事項 (User Wishlist)
* **Dual-Track Data:** Seamlessly merge CSV history + API recent bars + Live Ticks.
* **Real Execution:** Connect `RealExecutor` to Shioaji Order API.