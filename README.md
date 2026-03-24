# EnergyOrchestrator

> A mini energy asset optimization platform simulating solar + battery operations, electricity market participation, and TSO integration.

Built as a structured learning project to understand and demonstrate skills relevant to energy tech companies operating battery storage assets, solar plants, and grid-connected systems.

---

## What this is

EnergyOrchestrator simulates the core workflow of a battery asset optimization company:

1. A Python simulator generates realistic telemetry — solar production, battery state of charge, site load, market prices, and TSO events
2. Data flows over MQTT, as it would from real plant controllers and market feeds
3. A .NET backend ingests, stores, and processes that data
4. Optimization logic decides when to charge, discharge, or hold based on prices and grid signals
5. Grafana visualizes telemetry, battery behavior, and simulated revenue
6. Sentry tracks application errors and ingestion failures
7. An IEC 104 mock simulates the external SCADA/grid interface
8. The whole stack runs on a Hetzner VM via Docker Compose

---

## Business context

Battery storage assets earn revenue through multiple mechanisms:

- **Energy arbitrage** — charge when electricity prices are low, discharge when prices are high
- **Ancillary services** — provide frequency response or reserve capacity to the TSO
- **Peak shaving** — reduce site import during expensive peak periods
- **Flexibility trading** — participate in balancing and intraday markets

Managing this manually is slow and leaves money on the table. EnergyOrchestrator automates the dispatch decisions and gives operators full visibility into what the assets are doing and why.

### Key actors in the electricity system

| Actor | Role |
|---|---|
| TSO | Transmission System Operator — manages the high-voltage grid, procures ancillary services |
| DSO | Distribution System Operator — manages the local distribution network |
| Market operator | Runs spot, intraday, and balancing markets |
| Asset owner | Operates solar plants and batteries, wants to maximize revenue |
| Aggregator / optimizer | Software layer that makes dispatch decisions and submits market bids |

EnergyOrchestrator sits in the aggregator/optimizer role.

---

## Architecture

```
+------------------+        MQTT        +-------------------+
|  Python          |  ----------------> |  .NET Backend     |
|  Simulator       |  <---------------- |                   |
|                  |   dispatch cmds    |  - Ingest API     |
|  - Solar plant   |                    |  - Background     |
|  - Battery       |                    |    worker         |
|  - Site load     |                    |  - Optimization   |
|  - Market prices |                    |    engine         |
|  - TSO events    |                    |  - Postgres       |
+------------------+                    +-------------------+
                                                 |
                          +----------------------+---------------------+
                          |                      |                     |
                   +------+------+     +---------+------+    +--------+-------+
                   |  Grafana    |     |   Sentry       |    |  IEC 104 mock  |
                   |  dashboards |     |   error        |    |  (SCADA layer) |
                   |             |     |   tracking     |    |                |
                   +-------------+     +----------------+    +----------------+
```

### MQTT topic structure

```
site/{site_id}/pv/power              # solar production in kW
site/{site_id}/battery/soc           # battery state of charge 0-100%
site/{site_id}/battery/power         # battery charge/discharge power in kW
site/{site_id}/meter/import          # site import from grid in kW
site/{site_id}/meter/export          # site export to grid in kW
site/{site_id}/market/price          # current spot price EUR/MWh
site/{site_id}/tso/event             # TSO signal (type, duration, required_mw)
site/{site_id}/dispatch/command      # command from optimizer to battery controller
```

---

## Components

### Python Simulator (`/simulator`)

Simulates one full site over time, stepping every 60 seconds (configurable).

- Solar production follows a realistic daily curve with cloud noise
- Battery SOC changes based on dispatch commands and self-discharge
- Site load follows a household/commercial demand profile
- Market prices follow a day-ahead profile with intraday noise
- TSO events fire randomly with configurable probability
- Fault injection: missing data, out-of-range values, delayed messages

Publishes all telemetry to MQTT. Subscribes to dispatch commands from the backend.

#### Implementation steps

**Step 1: Project scaffold**
- Create `/simulator/` directory with `main.py`, `requirements.txt`, `config.py`
- Dependencies: `paho-mqtt`, `python-dotenv`
- Config: `SITE_ID`, `MQTT_HOST`, `STEP_INTERVAL_S` (default 60), `START_TIME`

**Step 2: Simulation clock**
- A `SimClock` that tracks simulated time (starts at midnight, advances by `STEP_INTERVAL_S` per tick)
- Exposes `time_of_day_fraction` (0.0–1.0) used by all signal generators

**Step 3: Solar production model**
- Sine-curve over daylight hours (~6am–8pm), zero outside
- Add Gaussian noise per step to simulate cloud cover
- Output: `pv_power_kw` (0–max_kw)
- Publish to `site/{site_id}/pv/power`

**Step 4: Site load model**
- Morning and evening peaks (household profile), flat commercial baseline
- Add small random noise
- Output: `load_kw`
- Publish to `site/{site_id}/meter/import` and `meter/export` (derived from net power)

**Step 5: Market price model**
- Day-ahead hourly profile (low overnight, peaks morning/evening)
- Add intraday Gaussian noise per step
- Output: `price_eur_mwh`
- Publish to `site/{site_id}/market/price`

**Step 6: Battery state model**
- Track `soc` (0–100%), `power_kw` (+ = charging, - = discharging)
- Each step: apply self-discharge, then apply last received dispatch command
- Clamp SOC to [0, 100], clamp power to battery limits
- Publish to `site/{site_id}/battery/soc` and `battery/power`

**Step 7: TSO event generator**
- Each step: roll against configurable probability (e.g. 0.5% per step)
- If triggered: publish event with random `type` (FCR/aFRR/mFRR), `duration_s`, `required_mw`
- Publish to `site/{site_id}/tso/event`

**Step 8: MQTT dispatch command subscriber**
- Subscribe to `site/{site_id}/dispatch/command`
- Parse command (`charge` / `discharge` / `hold` / `standby`) and target power
- Store as latest command; battery model reads it each step

**Step 9: Fault injection layer**
- Wrap publish calls with a `FaultInjector`
- Modes (each configurable by probability per message):
  - **Missing data** — skip publishing entirely
  - **Out-of-range** — multiply value by a large factor
  - **Delayed message** — sleep before publishing
- Controlled by env vars or config flags, off by default

**Step 10: Main loop**
- Tick the clock, run all models in order, publish all topics, sleep until next step
- Handle `KeyboardInterrupt` cleanly
- Add basic logging (step number, simulated time, key values)

#### File structure

```
/simulator
├── main.py            # main loop
├── config.py          # env-driven config
├── clock.py           # SimClock
├── models/
│   ├── solar.py
│   ├── battery.py
│   ├── load.py
│   ├── market.py
│   └── tso.py
├── mqtt_client.py     # publish/subscribe wrapper
├── fault_injector.py
└── requirements.txt
```

### .NET Backend (`/backend`)

ASP.NET Core service with a hosted background worker.

**Domain models:**

- `TelemetryPoint` — timestamped measurement from any device
- `BatteryState` — SOC, power, temperature, health, available capacity
- `MarketPrice` — interval, price, market type (spot / intraday / balancing)
- `DispatchInstruction` — command to battery (charge / discharge / hold / standby)
- `TsoSignal` — event type, required response, duration, activation time
- `RevenueRecord` — interval, market, actual dispatch, estimated revenue

**Services:**

- MQTT ingestion worker — subscribes to all site topics, normalizes payloads, persists
- Optimization engine — evaluates battery state + prices + TSO signals, generates dispatch instructions
- REST API — exposes telemetry, battery state, market prices, dispatch history, revenue summary
- KPI calculator — rolling 15-min, hourly, and daily aggregates

**Optimization logic (simple rule-based v1):**

```
if tso_event_active:
    respond to TSO signal first (reserve trumps arbitrage)
elif price > high_threshold and soc > minimum_reserve:
    discharge
elif price < low_threshold and soc < maximum_soc:
    charge
else:
    hold
```

### Grafana Dashboards (`/grafana`)

- **Site overview** — PV production, battery SOC, site import/export, net power
- **Market & dispatch** — spot price, dispatch decisions, arbitrage windows
- **Revenue** — daily/weekly simulated revenue by market, cumulative
- **System health** — MQTT message rate, ingestion latency, missed intervals

### Sentry Integration

- Backend tracks ingestion failures, bad payloads, optimization errors
- Simulator tracks connection failures, out-of-range generation
- Alerts on sustained message gaps (plant offline scenario)

### IEC 104 Mock (`/iec104-mock`)

Simulates a remote SCADA or grid connection using the IEC 60870-5-104 protocol.

- Acts as a server (outstation) sending spontaneous measurement updates
- Accepts command objects from the backend (single command, setpoint)
- Maps IEC 104 information objects to internal domain model
- Demonstrates: session establishment, STARTDT/STOPDT, ASDU types 1/3/9/11/45/50

This is a learning mock — not a production-grade IEC 104 implementation.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | .NET 10, ASP.NET Core, Entity Framework Core |
| Database | PostgreSQL |
| Messaging | MQTT (Mosquitto broker), MQTTnet (.NET client) |
| Simulator | Python 3.12, paho-mqtt |
| Dashboards | Grafana + Prometheus or direct Postgres datasource |
| Error tracking | Sentry (self-hosted or cloud) |
| Protocol mock | IEC 60870-5-104 via lib60870.NET |
| Deployment | Docker Compose, Hetzner Cloud VM |
| Reverse proxy | Caddy or Nginx |

---

## Roadmap

### MVP
- [ ] .NET REST API with domain models
- [ ] Background MQTT ingestion worker
- [ ] Python plant + battery + price simulator
- [ ] MQTT broker (Mosquitto) integration
- [ ] SQLite (local) / Postgres (deployed) persistence
- [ ] Simple charge/discharge optimization logic
- [ ] Grafana dashboard — SOC, PV, prices

### V2
- [ ] TSO event simulator and backend handler
- [ ] Revenue calculation per market interval
- [ ] Fault injection in simulator (missing data, bad values)
- [ ] Sentry integration on backend and simulator
- [ ] Docker Compose local stack

### V3
- [ ] IEC 104 mock outstation
- [ ] Backend IEC 104 client adapter
- [ ] Hetzner deployment with Docker Compose
- [ ] Auth on REST API (API key)
- [ ] Historical replay mode (feed recorded data at 10x speed)
- [ ] More realistic optimization (price forecast-aware)

---

## Phase deliverables

| Phase | Deliverable |
|---|---|
| 1 — Domain | One-page explanation of battery revenue stacking and data flows |
| 2 — Backend | Running .NET API with ingestion, storage, and dispatch endpoint |
| 3 — Simulator | Python simulator generating 24h of realistic site telemetry |
| 4 — MQTT | End-to-end message flow: simulator publishes, backend consumes, command sent back |
| 5 — Optimization | Dispatch decisions visible in API response and Grafana |
| 6 — Observability | Grafana dashboards live, Sentry catching injected errors |
| 7 — IEC 104 | Mock outstation integrated, measurements mapped to domain model |
| 8 — Deployment | Full stack running on Hetzner, accessible over HTTPS |

---

## Getting started (local)

Requirements: Docker, Docker Compose, Python 3.12+, .NET 10 SDK

```bash
# Start broker, database, Grafana
docker compose up -d mosquitto postgres grafana

# Run backend
cd backend
dotnet run

# Run simulator
cd simulator
pip install -r requirements.txt
python main.py --site-id 1 --interval 60
```

The simulator will begin publishing telemetry. The backend will ingest it, evaluate dispatch instructions every interval, and publish commands back.

Grafana is available at `http://localhost:3000`.

---

## Project name

Working name is **EnergyOrchestrator** — operating at the edge of the grid, extracting maximum value from controllable assets.

---

## Skills demonstrated

- Backend service design in .NET (API, worker, domain model, persistence)
- Event-driven architecture with MQTT
- Telemetry ingestion and normalization
- Simple optimization / rules engine
- Observability with Grafana and Sentry
- Industrial protocol adaptation (IEC 60870-5-104)
- Cloud deployment with Docker Compose
- Energy tech domain understanding (battery storage, electricity markets, TSO integration)
