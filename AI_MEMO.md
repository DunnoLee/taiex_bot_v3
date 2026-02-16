# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures)
> **Architecture:** Event-Driven (Feeder -> Aggregator -> Strategy -> Execution)

## 0. 開發協議 (Development Protocol) - STRICT
* **Logic Persistence:** DO NOT silently refactor user-defined logic. If a change is needed, explain "WHY the current approach fails" first.
* **Consistency:** `main_live.py` and `main_simulation.py` must share the exact same core modules (`loader`, `strategy`) to prevent logic divergence.

## 1. 核心哲學 (Core Philosophy)
1.  **Strict Modularity:** Strategy is pure logic; Execution is separate.
2.  **Simulation Parity:** Live & Backtest share the exact same logic code.
3.  **Data-Driven:** All parameters are verified by optimization (70k bars backtest).
4.  **Interactive Control:** The bot must be controllable via Telegram (Bi-directional).

## 2. 系統架構 (System Architecture)
* **Core Modules:**
    * `core/loader.py`: **Centralized History Loader**. Handles CSV parsing, column mapping, and standardization for BOTH Live and Sim modes.
    * `core/aggregator.py`: Converts Ticks to 1-min Bars.
* **Feeder:**
    * `ShioajiFeeder`: Live Market Data.
    * `CsvHistoryFeeder`: For Simulation.
* **Strategy:** `MAStrategy` (V3.5)
    * **Logic:** Dual MA Cross (Fast/Slow) on **Resampled K-Bars**.
    * **Buffer:** Increased `maxlen=5000` to accommodate deep history loading.
    * **Warm-up:** Uses `core/loader.py` to pre-fill MA buffers instantly.
* **Notification:** `TelegramCommander` (V3.2)
    * Bi-directional control (`/start`, `/stop`, `/status`, `/kill`).
    * Zombie Message Protection (ignores commands sent before startup).

## 3. 獲利模型 (The Holy Grail Parameters)
* **Optimization Date:** 2026-02-16
* **Data Source:** TMF History (70,000 bars)
* **Best Parameters (Champion Set):**
    * **Timeframe:** 5 min Resample.
    * **Fast Window:** 30 (approx. 2.5 hours).
    * **Slow Window:** 240 (approx. 20 hours).
    * **Filter Threshold:** 5.0 pts.
    * **Stop Loss:** **300 pts**.
* **Performance:** Net Profit **+$69,520 TWD** (Win Rate ~36%).

## 4. 開發日誌 (Development Log)
- [x] **Phase 1-3:** Skeleton, Strategy Porting, Mock Replay.
- [x] **Phase 4:** Live Data Connection (Shioaji TMF).
- [x] **Phase 5:** Optimization (Found optimal params: 30/240/300).
- [x] **Phase 6:** **Interactive Commander** (Completed).
- [x] **Phase 7:** **Refactoring & Warm-up** (Current)
    - [x] Created `core/loader.py` to unify CSV reading logic.
    - [x] Updated `MAStrategy` buffer to 5000.
    - [x] Standardized `main_live` and `main_simulation` to use the same loader.
- [ ] **Phase 8:** **Dual-Track Data Feed** (Next Step)
    - [ ] Implement API Backfill (Hot Data) to bridge the gap between CSV (Cold Data) and Real-time (WebSocket).

## 5. 待辦事項 (User Wishlist from My_MEMO)
* *Pending User Input: Retrieve features from past versions to re-integrate.*
* Refine "Dual-Track" mechanism for seamless data continuity.