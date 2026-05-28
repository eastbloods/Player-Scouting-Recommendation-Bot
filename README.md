# ⚽ Goat Scout — AI Football Player Scouting API

> An AI-powered football player recommendation system. Ask in natural language, get real player suggestions backed by vector search and LLM reasoning.

**Live demo:** [https://goatscout.space](https://goatscout.space)

---

## What It Does

You send a natural language query like:

```
"find a young left-back under 23 who plays in a top league"
```

The system:
1. Extracts structured filters from your query using an LLM (age, position, height, nationality, league)
2. Runs a semantic vector search over 400+ player profiles stored in Qdrant
3. Returns a curated list of real players matching your criteria

No dropdowns. No form fields. Just text.

---

## Architecture

```
SportMonks API
      │
      ▼
  ingest.py
  ┌────────────────────────────────────────────┐
  │  ingest_countries → ingest_leagues          │
  │  → ingest_teams → ingest_players            │
  └─────────────────┬──────────────────────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
     PostgreSQL            Qdrant
     (player data)    (vector embeddings)
                            │
                   all-MiniLM-L6-v2
                   384-dim, Cosine distance
                            │
                    ┌───────┴────────┐
                    │  Search flow   │
                    │                │
              User query             │
                    │                │
             LangChain LLM     LlamaIndex
           (Llama 3.3 70B)    VectorStoreIndex
           structured_output        │
           → PlayerFilter      qdrant_retriever
                    │                │
                    └───────┬────────┘
                            │
                       MetadataFilters
                       (age, position,
                        height, league...)
                            │
                        FastAPI
                     POST /search/
                            │
                          nginx
                     (reverse proxy)
                            │
                    goatscout.space
                       HTTPS ✅
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Data Source | SportMonks Football API |
| Database | PostgreSQL 15 |
| ORM & Migrations | SQLAlchemy 2.0 + Alembic |
| Vector Database | Qdrant |
| Embedding Model | `sentence-transformers/all-MiniLM-L6-v2` (384 dim, Cosine) |
| RAG Framework | LlamaIndex |
| LLM Pipeline | LangChain + Groq (Llama 3.3 70B) |
| API | FastAPI + Uvicorn |
| Containerization | Docker + Docker Compose |
| Infrastructure | AWS EC2 (eu-west-1, t3.small) |
| Reverse Proxy | nginx |
| SSL | Let's Encrypt (Certbot, auto-renewal) |

---

## API Usage

### Endpoint

```
POST https://goatscout.space/search/
Content-Type: application/json
```

### Request

```json
{
  "text": "find a young defender under 25 playing in the Premier League"
}
```

### Response

```json
{
  "text": "- Jordi Altena – 22 years old, right-back, Hearts\n- Benjamin Arthur – 20 years old, centre-back, Celtic\n- Nurudeen Abdulai – 21 years old, centre-back, Dunfermline Athletic"
}
```

### Try it with curl

```bash
curl -X POST https://goatscout.space/search/ \
  -H "Content-Type: application/json" \
  -d '{"text": "find a tall striker over 190cm"}'
```

### Interactive Docs

Swagger UI: [https://goatscout.space/docs](https://goatscout.space/docs)

---

## Run Locally

### Prerequisites

- Docker + Docker Compose
- SportMonks API key ([sportmonks.com](https://sportmonks.com))
- Groq API key ([console.groq.com](https://console.groq.com))

### Setup

```bash
git clone https://github.com/eastbloods/Player_Scouting_Recommendation_Bot.git
cd Player_Scouting_Recommendation_Bot
```

Create `.env` file:

```env
SPORTMONK_TOKEN=your_sportmonks_api_key
APP_PORT=8080
POSTGRES_USER=super
POSTGRES_PASSWORD=super
POSTGRES_DB=moneyball
DATABASE_URL=postgresql://super:super@db/moneyball
SECRET_KEY=your_secret_key
QDRANT_URL=http://qdrant:6333
GROQ_API_KEY=your_groq_api_key
```

### Start

```bash
docker compose up --build -d
```

### Initialize database

```bash
docker compose exec api alembic upgrade head
```

### Load data

```bash
docker compose exec api python -m ingest
```

This fetches players from SportMonks, stores them in PostgreSQL, generates embeddings, and loads ~400 player vectors into Qdrant. Takes 2–3 minutes.

### Test

```bash
curl -X POST http://localhost:8080/search/ \
  -H "Content-Type: application/json" \
  -d '{"text": "find a young goalkeeper under 22"}'
```

---

## Project Structure

```
.
├── main.py                  # FastAPI app entry point
├── ingest.py                # Data ingestion script (SportMonks → DB → Qdrant)
├── schemas.py               # Pydantic request/response models
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── routers/
│   └── search.py            # POST /search/ endpoint
│
├── agents/
│   └── search_agent.py      # LangChain pipeline: LLM → filters → retriever → response
│
├── vector_store/
│   └── retriever.py         # LlamaIndex Qdrant retriever (lazy load + singleton)
│
├── database/
│   ├── models.py            # SQLAlchemy models (Country, League, Team, Player)
│   ├── crud.py              # Upsert functions
│   └── session.py           # DB session + get_db generator
│
├── api/
│   └── sportmonks.py        # SportMonks API client
│
└── alembic/                 # Database migrations
```

---

## Key Design Decisions

**Why Qdrant over a traditional database?**
SQL cannot do semantic similarity search. "Find a player similar to a young creative midfielder" requires vector distance computation — not WHERE clauses.

**Why `all-MiniLM-L6-v2`?**
Lightweight (22M params, 90MB), runs on CPU, no API cost, 384-dim embeddings with Cosine distance. Fast enough for ~400 players on a t3.small instance.

**Why LangChain for query parsing?**
The query "find a defender under 25" needs to be converted into structured filters (`position=defender, age<=25`). `with_structured_output()` + Pydantic model makes this reliable.

**Why not a ReAct agent?**
Groq's Llama 3.3 70B has inconsistent tool-calling behavior. A direct pipeline (LLM → structured output → retriever → LLM) is more predictable and debuggable.

**Why lazy load the embedding model?**
Loading `all-MiniLM-L6-v2` at startup on a t3.small (2GB RAM) caused OOM during ingestion. A singleton pattern loads the model only on the first request and caches it.

---

## Limitations & Known Issues

- Queries in Turkish may produce inconsistent LLM field extraction
- Height filter only supports `<=` (no `>=` for "taller than")
- Position normalization is partial ("Winger" → "attacker" mapping incomplete)
- No authentication on the API endpoint
- Qdrant index is rebuilt on each retriever initialization (performance improvement pending)

---

## Author

**Ardas** — Junior AI Data Engineer candidate  
Building in public. Feedback welcome.

---

## License

MIT
