# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures) - Point Value: 10 TWD, Fee: 22 TWD.
> **Architecture:** Engine-Centric (Feeder -> Engine -> Strategy -> Executor)

## 0. 開發協議 (Development Protocol) - STRICT
* **Logic Persistence:** DO NOT silently refactor user-defined logic.
* **Engine-First:** `core/engine.py` is the centralized brain. `main_live` is the MASTER; `main_simulation` is the SHADOW.
* **Shadow Ledger:** `BaseExecutor` handles all PnL/Position logic. `RealExecutor` only handles IO.

## 1. 核心哲學 (Core Philosophy)
1.  **Main_Live is King:** All logic is designed for real execution first.
2.  **Real-Time Transparency:** `/balance` and `/status` must distinguish between "Shadow PnL" (Strategy view) and "Real Equity" (Broker view).
3.  **Safety First:** Dry Run mode and CA Cert checks are mandatory for Live execution.

## 2. 系統架構 (System Architecture)
* **Brain:** `core/engine.py` (V3.8)
    * **Smart Reporting:** Automatically switches between Mock/Real data for Telegram reports.
    * **Smart Order Logic:** Auto-reverse, Flatten detection.
* **Execution:**
    * `BaseExecutor`: Shared logic (Pyramiding, PnL, Position tracking).
    * `RealExecutor` (V3.7): **Production Ready**.
        * Auto-scans `FutureAccount`.
        * Validates CA Cert on startup.
        * **API Protocol:** Enforces MKT+IOC / LMT+ROD.
    * `MockExecutor`: Dummy implementation for logic verification.
* **Data Flow (Planned Phase 9):**
    * **Cold:** CSV History (Yesterday).
    * **Warm:** API Backfill (Today's market open to Now).
    * **Hot:** WebSocket Ticks (Real-time).

### 2.1 Shioaji API 實戰規範 (API Protocol)
* **Order Types:** MKT -> IOC; LMT -> ROD.
* **Data Types:** Convert `Decimal` to `float/int` immediately.
* **Contract:** Use logic to resolve `TMF202603` to `TMFC6`.

## 3. 獲利模型 (The Holy Grail Parameters)
* **Strategy:** MA(30/240) + Filter(5.0) + SL(300).
* **Performance:** Net Profit **+$69,520 TWD** (Win Rate ~36%).

## 4. 開發日誌 (Development Log)
- [x] **Phase 1-7:** Foundation, Tools, Recorder.
- [x] **Phase 8:** **Executor Architecture (Completed)**
    * [x] **BaseExecutor:** Unified logic for PnL and Position tracking.
    * [x] **RealExecutor:** Implemented Account Scan, CA Cert Check, and Dry Run safety.
    * [x] **BotEngine V3.8:** Updated `/balance` and `/status` to report Real vs. Shadow data.
    * [x] **Verification:** Passed connection, account binding, and order parameter tests.
- [ ] **Phase 9:** **Dual-Track Data Feed** (Current Focus)
    * [ ] **Goal:** Bridge the gap between CSV (Cold) and WebSocket (Hot).
    * [ ] Implement `fetch_kbars` in ShioajiFeeder.
    * [ ] Implement merge logic in Engine.

## 5. 待辦事項 (User Wishlist)
* **Dual-Track Data:** Seamlessly merge CSV history + API recent bars + Live Ticks.
* **Real Execution:** Connect `RealExecutor` to Shioaji Order API (Done, pending final "DryRun=False" trade).