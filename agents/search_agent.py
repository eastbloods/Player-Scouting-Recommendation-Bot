from langchain_groq import ChatGroq
from vector_store.retriever import qdrant_retriever
import os
from dotenv import load_dotenv
from agents.filter_agent import build_filters, PlayerFilter

load_dotenv()

SYSTEM_PROMPT = """You are GoatScout, an expert AI football scout assistant.

Given a scout query and player profiles from our database, identify the best matches.

STRICT output format — one player per line, then a reason on the next line:
**Player Name** | Age, Club (League) | Position | ★ Rating X.XX | Key: stat1, stat2, stat3
→ One sentence explaining why this player fits the query.

Rules:
- List ONLY players from the provided profiles. Do NOT invent players.
- Skip any player whose name is "None" or unknown.
- Age should be just the number (e.g. "26", not "26 years old").
- Rating: use the exact number from the profile, or write N/A if not available.
- Key stats: pick 2-3 stats most relevant to the query (e.g. tackles, dribbles, goals, passes).
- If no players match, write exactly: No players found matching your criteria.
- No introduction, no summary. Just the player lines."""


def search_augmentation(content: str) -> str:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    # Step 1: Extract hard filters — gracefully fall back if LLM fails
    try:
        filter_llm = llm.with_structured_output(PlayerFilter)
        player_filter = filter_llm.invoke(
            f"Extract ONLY position, min_age, max_age, min_height, max_height from: {content}"
        )
    except Exception as e:
        print(f"Filter extraction failed: {e} — proceeding without filters.")
        player_filter = PlayerFilter()

    print("FILTER:", player_filter)
    qdrant_filter = build_filters(player_filter)

    # Step 2: Semantic retrieval
    try:
        results = qdrant_retriever(content, qdrant_filter, top_k=8)
    except Exception as e:
        print(f"Retriever error: {e}")
        return "Search temporarily unavailable. Please try again."

    if not results:
        return "No players found matching your criteria."

    # Step 3: LLM formats results
    profiles = "\n\n---\n".join(results)
    try:
        response = llm.invoke(
            f"{SYSTEM_PROMPT}\n\n"
            f"Scout Query: {content}\n\n"
            f"Player Profiles:\n{profiles}\n\n"
            f"Best Matches:"
        )
        return response.content
    except Exception as e:
        print(f"LLM formatting error: {e}")
        # Fallback: return raw profiles
        return "\n\n".join(results[:5])
