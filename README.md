## VoltClause



## Problem
CEA safety and technical standards regulations are amended often, and site teams still carry old printouts. A wrong clearance or earthing value can fail an inspection or cause an accident.

## Who it is for
Electrical design engineer at an EPC firm building rooftop solar and substations in Tiruppur

## Signature feature
Clause diff card: pick any regulation number and see old text, new text and the amendment that changed it.

## Hardest problem (my interview story)
Versioning: latest valid version. Many CEA rules exist in a 2010 version, a 2023 version and later amendments. The system tracks which version is in force for a given date and shows a clause-by-clause 'what changed' diff, so an engineer never quotes a repealed value.

## Dataset
| Source | Link | Documents | Pages | Licence / terms |
|---|---|---|---|---|
| <name> | <url> | <n> | <n> | <licence> |

## 10 real questions
See [docs/QUESTIONS.md](docs/QUESTIONS.md).

## Run it
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                 # Windows: copy .env.example .env
uvicorn app.main:app --reload
curl localhost:8000/health
```

## Live link
<Added in Week 2>
