from langchain_groq import ChatGroq
from vector_store.retriever import qdrant_retriever
import os
from dotenv import load_dotenv
from agents.filter_agent import build_filters, PlayerFilter

load_dotenv()


def search_augmentation(content):
    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    structured_llm = llm.with_structured_output(PlayerFilter)
    player_filter = structured_llm.invoke(content)
    print("FILTER:", player_filter)

    metadata_filters = build_filters(player_filter)

    results = qdrant_retriever(content, metadata_filters)

    response = llm.invoke(
        f"List ONLY the players from the search results below. "
        f"Use this exact format for each player, one per line:\n"
        f"- Player Name – X years old, Y cm, position, Club (League)\n"
        f"Do not add any extra text, introduction, or summary. "
        f"If no results found, write: No players found.\n\n"
        f"User query: {content}\n\n"
        f"Search results: {results}\n\n"
        f"Players:"
    )

    return response.content
