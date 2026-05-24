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
        f"Answer ONLY using the search results below. Do not use your own knowledge.\n\nUser query: {content}\n\nSearch results: {results}\n\nAnswer:")
    return response.content
