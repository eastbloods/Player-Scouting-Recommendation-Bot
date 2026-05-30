# ⚽ GoatScout — AI Football Player Scouting Platform

[![Live Demo](https://img.shields.io/badge/demo-goatscout.space-22c55e?style=flat-square&logo=globe)](https://goatscout.space)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-vector_db-dc143c?style=flat-square)](https://qdrant.tech)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://docker.com)
[![AWS](https://img.shields.io/badge/AWS-EC2_eu--west--1-FF9900?style=flat-square&logo=amazonaws)](https://aws.amazon.com)

> **Find the next hidden gem — before 32 other scouts do.**  
> Natural language player search over 33,000+ real football players, powered by vector search and LLM reasoning.

**🌐 Live:** [https://goatscout.space](https://goatscout.space) &nbsp;|&nbsp; **📖 API Docs:** [https://goatscout.space/docs](https://goatscout.space/docs)

---

## What It Does

Traditional scouting tools require you to know exactly what to filter. GoatScout lets you think like a scout:

```
"box-to-box midfielder, good under pressure, under 24, in Portugal or France"
"tall aerial threat striker over 190cm, experienced, La Liga"
"young creative left-back who overlaps and delivers crosses"
```

The system extracts structured filters from your query, runs semantic vector search across 33,000+ player profiles, and returns real, ranked candidates — not hallucinated names.

**Two search modes:**
- **⚡ AI Scout** — Natural language prompt, results with scout notes explaining *why* each player fits
- **🎛️ Filter Scout** — Structured filters: position → subposition → country → league → nationality → age → height

---

## Architecture

```
SportMonks Football API
        │
        ▼
   ingest.py  ──────────────────────────────────────────────────┐
   ┌─ ingest_countries → ingest_leagues → ingest_teams ─┐       │
   │  → ingest_players (33,000+ players)                 │       │
   └─────────────────────────────────────────────────────┘       │
        │                                                         │
   ┌────┴────┐                                                    │
   │         │                                                    │
PostgreSQL  Qdrant  ◄── sentence-transformers/all-MiniLM-L6-v2  │
(metadata)  (384-dim vectors, Cosine distance)                   │
                │                                                 │
         Search Pipeline ◄───────────────────────────────────────┘
                │
   User Query (text + optional filters)
                │
        ┌───────┴────────────────────────┐
        │                                │
   Regex Extraction              LangChain LLM
   (age, height — fast,          (Llama 3.3 70B via Groq)
    reliable)                    structured_output → PlayerFilter
        │                                │
        └───────────┬────────────────────┘
                    │
             _merge_filters()
             (UI filters > LLM filters > regex)
                    │
             Qdrant Filtered ANN
             (pre-filter → vector search)
                    │
              top-12 results
                    │
               LLM formats
               response + scout note
                    │
                 FastAPI
              POST /search/
                    │
                  nginx
             (reverse proxy)
                    │
          https://goatscout.space
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Data Source** | SportMonks Football API | 33,000+ players, real stats, current seasons |
| **Database** | PostgreSQL 15 | Structured player metadata, FK relationships |
| **ORM & Migrations** | SQLAlchemy 2.0 + Alembic | Type-safe models, zero-downtime schema changes |
| **Vector Database** | Qdrant | Filtered ANN search, payload metadata, HNSW indexing |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` | 22M params, 384-dim, local/free, Cosine-ready |
| **RAG Framework** | LlamaIndex | VectorStoreIndex + metadata filter integration |
| **LLM Pipeline** | LangChain + Groq (Llama 3.3 70B) | Structured output extraction, scout note generation |
| **API** | FastAPI + Uvicorn | Async, auto-docs, Pydantic validation |
| **Containerization** | Docker + Docker Compose | 3-service stack: api + db + qdrant |
| **Infrastructure** | AWS EC2 t3.small (eu-west-1) | 2GB RAM, 20GB EBS, cost-efficient |
| **Reverse Proxy** | nginx | SSL termination, port routing |
| **SSL** | Let's Encrypt (Certbot) | Auto-renewal, HTTPS in production |

---

## Filter System

GoatScout supports two types of filters that stack on top of each other:

**Hard filters (Qdrant metadata — exact match):**
- `position` — Goalkeeper / Defender / Midfielder / Attacker + sub-position
- `min_age` / `max_age` — numeric range
- `min_height` / `max_height` — cm range
- `nationality` — player's nationality (e.g. "France", "Brazil")
- `league` — exact league name (e.g. "Super Lig", "Premier League")
- `team_country` — expands to all domestic leagues of that country

**Semantic filters (vector search):**
- Everything else in the text query ("good under pressure", "overlapping runs", "aerial threat")

**Filter priority:** UI explicit filters > regex-extracted numbers > LLM-extracted filters

```json
// Example request
{
  "text": "creative, good under pressure",
  "position": "centre-back",
  "max_age": 23,
  "min_height": 185,
  "team_country": "Portugal"
}
// → Qdrant filter: age ≤ 23, height ≥ 185, league IN ["Primeira Liga", "Liga Portugal 2", ...]
// → Vector search: "creative, good under pressure" over filtered subset
```

---

## API Usage

### Endpoint

```
POST https://goatscout.space/search/
Content-Type: application/json
```

### Request Schema

```json
{
  "text": "string (natural language query)",
  "position": "string (optional) — e.g. centre-back, left-back, striker",
  "min_age": "integer (optional)",
  "max_age": "integer (optional)",
  "min_height": "integer (optional, cm)",
  "max_height": "integer (optional, cm)",
  "nationality": "string (optional) — player nationality",
  "league": "string (optional) — exact league name",
  "team_country": "string (optional) — expands to all leagues of that country"
}
```

### Examples

```bash
# Natural language only
curl -X POST https://goatscout.space/search/ \
  -H "Content-Type: application/json" \
  -d '{"text": "tall aerial striker over 190cm, good in the air"}'

# Combined: semantic + hard filters
curl -X POST https://goatscout.space/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "text": "creative, good under pressure",
    "position": "centre-back",
    "max_age": 23,
    "team_country": "Germany"
  }'

# Filter-only (no text needed)
curl -X POST https://goatscout.space/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "nationality": "Brazil",
    "league": "Super Lig",
    "position": "attacking-midfielder"
  }'
```

### Response

```json
{
  "text": "Ruairi McConville | 21, Norwich City (Championship) | defender (centre-back) | ★ Rating 6.96 | Key: 29 tackles, 77 aerials won\n→ Young centre-back with dominant aerial presence and strong defensive output across 25 appearances this season."
}
```

---

## Run Locally

### Prerequisites

- Docker + Docker Compose
- [SportMonks API key](https://sportmonks.com) (free tier available)
- [Groq API key](https://console.groq.com) (free tier available)

### Setup

```bash
git clone https://github.com/eastbloods/Player_Scouting_Recommendation_Bot.git
cd Player_Scouting_Recommendation_Bot
```

Create `.env`:

```env
SPORTMONK_TOKEN=your_sportmonks_api_key
GROQ_API_KEY=your_groq_api_key
APP_PORT=8080
POSTGRES_USER=super
POSTGRES_PASSWORD=super
POSTGRES_DB=moneyball
DATABASE_URL=postgresql://super:super@db/moneyball
SECRET_KEY=your_secret_key_here
QDRANT_URL=http://qdrant:6333
```

### Start

```bash
# Build and start all 3 services (api + db + qdrant)
docker compose up --build -d

# Check status
docker compose ps
docker compose logs api
```

### Initialize

```bash
# Run database migrations
docker compose exec api alembic upgrade head

# Ingest player data (SportMonks → PostgreSQL → Qdrant)
# Fetches leagues, teams, players; generates embeddings; loads vectors
docker compose run --rm api python3 ingest.py
```

> ⏱ Ingestion takes 5–15 minutes depending on the number of leagues configured. Progress is logged to stdout.

### Test

```bash
curl -X POST http://localhost:8080/search/ \
  -H "Content-Type: application/json" \
  -d '{"text": "young goalkeeper under 22, good with feet"}'
```

Open [http://localhost:8080/docs](http://localhost:8080/docs) for Swagger UI.

---

## Project Structure

```
.
├── main.py                  # FastAPI app entry point
├── ingest.py                # Data pipeline: SportMonks → PostgreSQL → Qdrant
├── schemas.py               # Pydantic request/response models
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── routers/
│   ├── search.py            # POST /search/ endpoint
│   └── meta.py              # GET /meta/leagues, /meta/nationalities (autocomplete data)
│
├── agents/
│   ├── search_agent.py      # Core pipeline: regex + LLM filters → Qdrant → LLM format
│   └── filter_agent.py      # Position mapping + Pydantic PlayerFilter model
│
├── vector_store/
│   └── retriever.py         # LlamaIndex Qdrant retriever (lazy load singleton)
│
├── database/
│   ├── models.py            # SQLAlchemy models: Country, League, Team, Player
│   ├── crud.py              # Upsert functions (on_conflict_do_update)
│   └── database.py          # Engine + SessionLocal + get_db generator
│
├── api/
│   ├── sportmonks.py        # SportMonks API client (paginated GET)
│   └── parser.py            # Raw JSON → clean Python dicts
│
└── alembic/                 # Database migrations
    └── versions/
```

---

## Key Design Decisions

**Why Qdrant over a traditional database?**  
SQL cannot compute semantic similarity. `WHERE description LIKE '%creative midfielder%'` is keyword matching, not understanding. Qdrant stores 384-dimensional vectors and finds the nearest neighbors in vector space — "what players are semantically similar to this description?"

**Why `all-MiniLM-L6-v2`?**  
Lightweight (22M params, 90MB), runs entirely on CPU, zero API cost, produces normalized 384-dim vectors. Fast enough for 33,000 players on a t3.small. Changing the model would require re-embedding the entire dataset.

**Why regex-first filter extraction (not LLM-first)?**  
LLMs are non-deterministic. "Under 25" sometimes becomes `max_age=24`, sometimes `max_age=25`, sometimes nothing. Regex is deterministic: `r'\bunder\s+(\d{2})\b'` always works. LLM handles position semantics where regex falls short.

**Why not a ReAct agent?**  
Groq's Llama 3.3 70B has inconsistent tool-calling behavior — `BadRequestError: tool_use_failed` appears unpredictably. A direct pipeline (LLM → structured output → retriever) is deterministic, debuggable, and production-safe.

**Why Filtered ANN (pre-filter, not post-filter)?**  
Post-filter: retrieve top-100 by vector, then filter → if only 3 results pass the filter, you wasted a big search. Pre-filter: apply metadata filter first (`age ≤ 23, position = left-back` → 800 candidates), then do ANN over that subset → better recall, no wasted retrieval.

**Why lazy load the embedding model?**  
Loading `sentence-transformers` at startup on a t3.small (2GB RAM) caused OOM during container startup. Singleton pattern: model loads on first request, cached for all subsequent requests. Startup stays fast.

---

## Limitations & Roadmap

**Current limitations:**
- No user authentication on the API
- LLM scout notes fall back to stat-based summaries when Groq rate-limits
- Position semantic search occasionally returns nearby positions (left-back query → right-back result) — hard filter recommended for strict position requirements

**Planned improvements:**
- [ ] 2025/26 season data refresh
- [ ] CQI (Contextual Quality Index): normalize ratings by league strength
- [ ] Re-ranking layer: cross-encoder to reorder raw vector results
- [ ] Airflow DAG for scheduled weekly data updates
- [ ] Player comparison endpoint: `POST /compare/`

---

## Author

**Ardas** — Junior AI Data Engineer  
Building production ML systems. Feedback and contributions welcome.

[LinkedIn](https://linkedin.com) · [GitHub](https://github.com/eastbloods)

---

## License

MIT
