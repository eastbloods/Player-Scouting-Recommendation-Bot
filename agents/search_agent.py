from langchain_groq import ChatGroq
from vector_store.retriever import qdrant_retriever
import os
from dotenv import load_dotenv
from agents.filter_agent import build_filters, PlayerFilter

load_dotenv()

SYSTEM_PROMPT = """You are GoatScout, an expert AI football scout assistant.

Your job: given a scout query and player profiles, identify and present the best matching players.

Rules:
- List ONLY players from the provided profiles. Never invent players.
- For each player, highlight the stats most relevant to the query.
- Use this format for each player (one per line):
  **Name** | Age, Club (League) | Position | ★ Rating X.XX | Key: [2-3 most relevant stats]
  → [One sentence explaining why this player fits the query]
- If fewer than 5 players found, list all of them.
- If no players found, say: "No players found matching your criteria."
- Be concise. No introduction, no summary at the end."""


def search_augmentation(content: str) -> str:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    # Step 1: Extract reliable hard filters
    filter_llm = llm.with_structured_output(PlayerFilter)
    player_filter = filter_llm.invoke(
        f"Extract position/age/height filters only from this scout query: {content}"
    )
    print("FILTER:", player_filter)

    qdrant_filter = build_filters(player_filter)

    # Step 2: Semantic retrieval — full original query goes here
    results = qdrant_retriever(content, qdrant_filter, top_k=8)

    if not results:
        return "No players found matching your criteria."

    # Step 3: LLM formats results
    profiles = "\n\n---\n".join(results)
    response = llm.invoke(
        f"{SYSTEM_PROMPT}\n\n"
        f"Scout Query: {content}\n\n"
        f"Player Profiles:\n{profiles}\n\n"
        f"Best Matches:"
    )
    return response.content
