# ContagionNet
A real-time systemic risk simulator that mathematically models how a single bank's failure triggers a financial chain reaction. Built with FastAPI, React, and D3.js, it uses real FDIC/BIS data, Maximum-Entropy estimation, and central bank algorithms (DebtRank, Eisenberg-Noe) to visualize contagion, rank systemic importance, and calculate VaR.

# ContagionNet

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python-009688.svg)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/Frontend-React%20%7C%20TypeScript%20%7C%20D3-3178C6.svg)](https://reactjs.org/)
[![Status](https://img.shields.io/badge/Status-Active-success.svg)]()

**Live mathematical modeling of financial collapse, built on real central bank methodologies.**

The **ContagionNet** is an interactive, full-stack platform that mathematically models how a single bank's failure triggers a chain reaction across the global financial system. Utilizing real public data (FDIC, ECB, BIS) and the same rigorous stress-testing algorithms used by central banks, it visualizes collapse propagation in real-time through an interactive network graph driven by a WebSocket.

---
<img width="2752" height="1536" alt="Gemini_Generated_Image_galp01galp01galp" src="https://github.com/user-attachments/assets/1629bebb-a028-459f-8e47-e3280f60aa7c" />
<img width="2752" height="1536" alt="Gemini_Generated_Image_96ssaz96ssaz96ss" src="https://github.com/user-attachments/assets/3f75d887-0ce2-4c43-8485-e83570b929ad" />


## 🚀 Core Capabilities

*   **Real-Time Propagation Visualization:** Select a bank, inject a shock, choose a contagion model, and watch the distress wave spread step-by-step across a D3.js force-directed graph.
*   **Systemic Importance Ranking (SIR):** Precomputes and ranks the absolute systemic risk posed by every institution in the network.
*   **Contagion Heatmap:** Generates a complete $N \times N$ matrix displaying the exact vulnerability of any bank to the failure of any other.
*   **Monte Carlo Systemic VaR:** Simulates thousands of correlated shock scenarios to output a systemic Value-at-Risk (VaR), Conditional VaR (CVaR), and the overall probability of a systemic crisis.

---

## 🏗️ System Architecture: The Six Layers

The platform is built on a highly modular, mathematically rigorous six-layer architecture:

### 1. Data Ingestion & Estimation
Pulls real-world balance sheet data from **FDIC Call Reports** (Top 100 US banks), **BIS Consolidated Banking Statistics**, and the **ECB Statistical Warehouse**. 
*   *The Missing Link:* Because bilateral interbank exposures are strictly confidential, the system uses **Maximum-Entropy (RAS) estimation** to rigorously reconstruct the most probable bilateral exposure matrix from aggregate row/column totals.
*   *Resilience:* Includes a seamless fallback to a synthetic, Basel III-compliant network if external APIs fail.

### 2. Graph Engine
Powered by `NetworkX`, it maps the financial system as a directed, weighted graph. It computes the critical **Vulnerability Matrix** ($V_{ij} = \text{Exposure}_{ij} / \text{Equity}_i$) alongside degree, betweenness, and eigenvector centralities.

### 3. Contagion Algorithms
Implements three distinct, peer-reviewed mathematical models for systemic risk:
*   **DebtRank:** A continuous distress model acting as a propagate-once state machine.
*   **Eisenberg-Noe Clearing:** A classic fictitious default algorithm resolving simultaneous defaults.
*   **Hard-Threshold Domino Cascade:** A binary cascade model where institutions fail entirely upon reaching a specific loss threshold.

### 4. Stress Testing Engine
Conducts exhaustive single-node shock scenarios to precompute the Systemic Importance Ranking (SIR) and $N \times N$ heatmaps, alongside running heavy Monte Carlo simulations for correlated market shocks.

### 5. Backend API & WebSocket
A **FastAPI** REST backend paired with a `/ws/contagion` WebSocket endpoint that streams the simulation state step-by-step to the client. Uses an SQLite database for results caching.

### 6. Frontend Visualization
A rich **React + TypeScript** interface styled with **Tailwind CSS**. It features a live **D3.js** force-directed network graph with real-time node coloring, heatmaps, algorithm comparison charts, Monte Carlo histograms, and live liquidity metrics (including Basel III LCR).

---

## 🛡️ Mathematical Correctness & Self-Testing

Because financial modeling requires absolute precision, the backend server acts as a strict gatekeeper. Upon startup, it executes the full pipeline and runs two mandatory correctness assertions. **The server will refuse to start if either fails:**

1.  **DebtRank Assertion:** Tests the algorithm on a canonical 3-bank chain, guaranteeing it produces exactly 4 steps with mathematically exact distress values ($h(B1)=0.4$, $h(B2)=0.16$), correct `INACTIVE` state transitions, and a total system loss of $\approx 0.4533$.
2.  **Maximum Entropy Assertion:** Guarantees the RAS estimator yields a non-negative matrix with a strict zero diagonal (banks don't lend to themselves) whose row and column sums perfectly match the input margins.

*(Note: Expect a ~60-second delay on the first boot while it ingests data for 100 banks, estimates the matrix, runs all stress tests, and validates these assertions).*

---

## ⚙️ Installation & Execution

### Option A: Docker (Recommended)
The easiest way to run the full stack (API, Frontend, and dependencies).

```bash
# Clone the repository
git clone [https://github.com/purav-12345/ContagionNet.net]
cd ContagionNet
```

### Option B: Local Setup (No Docker)

**1. Backend (Python)**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
**2. Frontend**
```bash
cd frontend
npm install
npm run dev
```
## 📡 API Reference

The backend provides a clean RESTful interface alongside real-time WebSockets.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/api/health` | System status, loaded banks count, and active data source. |
| **GET** | `/api/network` | Retrieves D3 nodes/links and aggregate system totals. |
| **POST** | `/api/simulate` | Executes one contagion algorithm and returns the full step history (cached). |
| **GET** | `/api/stress-test/systemic-importance` | Returns the precomputed Systemic Importance Ranking (SIR). |
| **GET** | `/api/stress-test/heatmap` | Returns the $N \times N$ contagion vulnerability matrix. |
| **GET / POST** | `/api/monte-carlo` | Retrieves precomputed Monte Carlo VaR data or triggers a custom run. |
| **WS** | `/ws/contagion` | WebSocket endpoint broadcasting live, step-by-step shock propagation. |


## 📊 Data Sources & Accounting Notes

The simulator strictly utilizes free, public data (no API keys required):

* **FDIC:** [https://api.fdic.gov/banks/financials](https://api.fdic.gov/banks/financials) *(Values in thousands USD)*
* **BIS:** [https://stats.bis.org/api/v1/](https://stats.bis.org/api/v1/) *(Values in millions USD)*
* **ECB:** [https://data-api.ecb.europa.eu/service/data](https://data-api.ecb.europa.eu/service/data)

**Important Unit Notes:**

* The frontend automatically normalizes and formats all displayed values from thousands.
* **Equity** represents the total loss-absorbing capacity (buffer) of an institution, which serves as the critical denominator in calculating the vulnerability matrix.

# Build and start the containers
docker compose up --build
