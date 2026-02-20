# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures) - Point Value: 10 TWD, Fee: 22 TWD.
> **Architecture:** Engine-Centric (Feeder -> Engine -> Strategy -> Executor)

## 0. 開發協議 (Development Protocol) - STRICT
* **Codebase Integrity:** Always prioritize existing class names, variable names, and method signatures found in the user's GitHub code.
* **Non-Destructive Editing:** Do NOT rename or refactor working logic unless explicitly requested.
* **Shadow Ledger:** `BaseExecutor` handles all PnL/Position logic. `RealExecutor` only handles IO.

## 1. 核心哲學 (Core Philosophy)
1.  **Main_Live is King:** All logic is designed for real execution first.
2.  **Real-Time Transparency:** `/balance` and `/status` must distinguish between "Shadow PnL" and "Real Equity".
3.  **Data Continuity:** The system must seamlessly bridge historical CSV data with real-time API ticks, with built-in gap detection.

## 2. 系統架構 (System Architecture)
* **Brain:** `core/engine.py` (V3.9)
    * **Data Bridge:** Automatically backfills missing warm data via Shioaji `kbars` API on startup.
    * **Gap Detection:** Alerts user via Telegram if data lags >10 mins (trading hours) or >5 days (holidays).
* **Strategy (The Cartridge):** `core/base_strategy.py`
    * Standardized interface for hot-swapping strategies.
    * `MAStrategy` successfully decoupled and inherited from `BaseStrategy`.
* **Execution:** `RealExecutor` (V3.7) & `MockExecutor`.
* **Feeder:** `ShioajiFeeder` (Live/API Backfill) & `CsvHistoryFeeder` (Threaded Replay).

### 2.1 雙軌數據流 (The Dual-Track Pipeline)
1.  **Cold Data:** Read from `TMF_History.csv` into memory (Managed by `universal_downloader.py`).
2.  **Warm Data (Backfill):** API fetches `kbars` from the last CSV timestamp to NOW. Duplicates are filtered.
3.  **Hot Data:** Real-time WebSocket ticks stream into the Aggregator.
*Note: The Engine operates entirely in-memory during Live mode to prevent IO bottlenecks.*

## 3. 獲利模型 (The Holy Grail Parameters)
* **Strategy:** MA(30/240) + Filter(5.0) + SL(300).
* **Performance:** Net Profit **+$69,520 TWD** (Win Rate ~36%).

## 4. 開發日誌 (Development Log)
- [x] **Phase 1-7:** Foundation, Tools, Recorder.
- [x] **Phase 8:** **Executor Architecture (Completed)**
    * Implemented Account Scan, CA Cert Check, and Dry Run safety.
- [x] **Phase 9:** **Dual-Track Data Feed & Strategy Interface (Completed)**
    * [x] Refactored `BaseStrategy` for plug-and-play strategy modules.
    * [x] Implemented `fetch_kbars` in `ShioajiFeeder`.
    * [x] Developed `sync_warmup_data_from_api` with anti-duplication and Freshness Gap Check.
    * [x] Threaded `CsvHistoryFeeder` to fix simulation blocking issues.

## 5. 待辦事項 (User Wishlist)
* **Live Observation:** Await market open to observe real-time Tick-to-Bar aggregation and actual API order placement (DryRun=False).
* **Future Expansion:** Add new strategies (e.g., RSI, ADX) using the new `BaseStrategy` cartridge system.