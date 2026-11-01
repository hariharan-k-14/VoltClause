# VoltClause

[![CI](https://github.com/hariharan-k-14/VoltClause/actions/workflows/ci.yml/badge.svg)](https://github.com/hariharan-k-14/VoltClause/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)
![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg)

> Gives electrical engineers the currently valid CEA safety and technical clause, and shows what changed.

---

## Problem
Central Electricity Authority (CEA) safety and technical standards regulations are amended often, and site teams still carry old printouts. A wrong clearance or earthing value can fail an inspection or cause an accident.

## Who it is for
Electrical design engineer at an EPC firm building rooftop solar and substations in Tiruppur.

## Signature feature
**Clause diff card**: pick any regulation number and see old text, new text, and the amendment that changed it.

## Hardest problem (my interview story)
**Versioning: latest valid version**. Many CEA rules exist in a 2010 version, a 2023 version, and later amendments. The system tracks which version is in force for a given date and shows a clause-by-clause "what changed" diff, so an engineer never quotes a repealed value.

## Dataset
| Source | Link | Documents | Pages | Licence / terms |
|---|---|---|---|---|
| Central Electricity Authority (CEA) Regulations | [cea.nic.in/regulations](https://cea.nic.in/regulations/) | 45+ | 1,200+ | Official Gazette / Public Domain (Govt of India Open Access) |

Full dataset catalog: see [DATASET.md](DATASET.md).

## 10 real questions
See [docs/QUESTIONS.md](docs/QUESTIONS.md).
Key questions addressed:
1. *What is the minimum vertical clearance for a 33 kV line over a road?* (CEA Safety Regs 2023, Reg 58: 6.1m)
2. *What changed in the safety regulations between 2010 and 2023 on earthing?* (CEA Safety Regs Reg 41/42/48: maintenance-free chemical earthing, dual neutral earthing)
3. *Which regulation covers grid connectivity for rooftop solar inverters?* (CEA Grid Connectivity 2019, Reg B2: anti-islanding within 2.0s, harmonics, FRT)
4. *(Unanswerable from CEA docs)*: *What is the per-unit feed-in tariff paid by TANGEDCO in Tiruppur?* (Regulated by TNERC state commission, not CEA national technical standards)

---

## System Design & Architecture
See comprehensive technical specification in [DESIGN.md](DESIGN.md).

### Week 2 Capabilities
- **POST /chat**: Structured JSON responses with verified CEA citations, prompt/completion token accounting, and dollar cost calculation.
- **Resilience & Fallback**: Automatic retry loop with exponential backoff on primary LLM (`gpt-4o-mini`), falling back gracefully to domain expert engine (`mock-cea-expert`) on timeouts, rate limits, or missing API keys.
- **SSE Streaming (`POST /chat/stream`)**: Real-time token delivery via Server-Sent Events with a terminal completion event containing full usage metrics.
- **Usage & Cost Ledger (`GET /usage`)**: Real-time tracking of cumulative requests, prompt tokens, completion tokens, total cost in USD, and per-model breakdown.
- **Docker & Compose**: Containerized multi-service setup (`api` + `db` with pgvector).

---

## Live link
- **Production URL**: [https://voltclause.onrender.com](https://voltclause.onrender.com) (or deployed container on free host)
- **Health Check**: [https://voltclause.onrender.com/health](https://voltclause.onrender.com/health)

---

## Run it locally

### Option A: Local Python virtual environment
```bash
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env             # On Windows: copy .env.example .env
uvicorn app.main:app --reload
```
Test health:
```bash
curl http://localhost:8000/health
```

### Option B: Docker
```bash
docker build -t voltclause:latest .
docker run -p 8000:8000 --env-file .env voltclause:latest
```

### Option C: Docker Compose (API + pgvector)
```bash
docker compose up -d
curl http://localhost:8000/health
```

---

## API Examples

### 1. Ask a Technical Clause Question
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the minimum vertical clearance for a 33 kV line over a road?",
    "project_type": "substation",
    "voltage_level_kv": 33.0
  }'
```

### 2. Stream Tokens (Server-Sent Events)
```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What changed in safety regulations between 2010 and 2023 on earthing?",
    "stream": true
  }'
```

### 3. Inspect Token Usage & Cost
```bash
curl http://localhost:8000/usage
```

---

## Download Source PDFs (Data Pipeline)
To refresh the regulatory corpus from CEA:
```bash
python tools/download.py tools/urls.txt
```
PDFs and documents are saved under `data/raw/` with a download log in `data/manifest.csv`.

---

## Tests & Linting
Run the full test suite (16 tests, 100% offline-compatible):
```bash
pytest -q
ruff check .
```
