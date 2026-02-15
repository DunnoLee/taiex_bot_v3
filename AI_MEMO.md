# TaiEx Bot V3 - Project Manifesto & AI Memory

> **System Identity:** TaiEx Bot V3 (Python 3.12 / Mac Silicon)
> **Target:** TMF (Micro Taiwan Index Futures)
> **Architecture:** Event-Driven (Feeder -> Aggregator -> Strategy -> Execution)

## 1. 核心哲學 (Core Philosophy)
1.  **Strict Modularity:**
    - `Strategy` (Brain) is pure logic. It consumes `BarEvent` and produces `SignalEvent`.
    - `ShioajiFeeder` (Live) and `CsvHistoryFeeder` (Mock) must be interchangeable.
2.  **Simulation Parity:**
    - The `BarAggregator` translates real-time Ticks into Bars, ensuring the Strategy sees the same data structure in Live mode as it does in Backtest mode.
3.  **Config Centralization:**
    - All params in `config/settings.py`. No hard-coding.

## 2. 系統架構 (System Architecture)
* **DataFeeder:**
    * `CsvHistoryFeeder`: Reads historical CSV (Time/Open/High/Low/Close/Volume) for backtesting.
    * `ShioajiFeeder`: Connects to API, auto-selects Front Month contract (e.g., TMFB6), streams Ticks.
* **Translator:**
    * `BarAggregator`: Accumulates Ticks -> Generates 1-min `BarEvent`.
* **Strategy:**
    * `MAStrategy`: Dual MA Cross (Fast/Slow). Pure logic, API-agnostic.
* **Execution:**
    * `MockExecutor`: Calculates PnL instantly for backtesting.
    * `RealExecutor`: (Pending Implementation) Handles Shioaji orders.

## 3. 開發日誌 (Development Log)
- [x] **Phase 0:** Environment Setup (Python 3.12, .venv, settings.py).
- [x] **Phase 1: Skeleton & Data Flow:** Defined `Event` classes (Tick, Bar, Signal).
- [x] **Phase 2: Strategy Porting:** Implemented `MAStrategy` (TaLib-free).
- [x] **Phase 3: Mock Replay:** Validated strategy with `CsvHistoryFeeder` & `MockExecutor` (Found -370k loss in range market).
- [x] **Phase 4: Live Data Connection:**
    - Implemented `ShioajiFeeder` with robust contract lookup.
    - Implemented `BarAggregator` to bridge Tick -> Strategy.
    - Verified `main_live.py` connection to TMF.
- [ ] **Phase 5: Remote Control (Commander):** Telegram integration.
- [ ] **Phase 6: Live Execution:** Real order placement logic.

## 4. 當前狀態 (Current Context)
* **Last Updated:** 2026-02-16
* **Status:** System is "Live-Ready" for monitoring. Data pipeline is complete.
* **Next Priority:** Telegram Integration (`Commander`) to allow mobile monitoring of "System Ready" status.
* **Note:** `main.py` is for Mock Replay; `main_live.py` is for Real Trading.

---
*此檔案由 AI 維護，作為長期記憶與架構守門員。每次重大更新請同步修改此檔。*