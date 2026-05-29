from langchain_groq import ChatGroq
from vector_store.retriever import qdrant_retriever
from agents.filter_agent import build_filters, PlayerFilter
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are GoatScout, an expert AI football scout assistant.

Given a scout query and player profiles from our database, format ALL provided players.

STRICT output format — one player per line, then a reason on the next line:
Name | Age, Club (League) | position_group (detailed_position) | ★ Rating X.XX | Key: stat1, stat2, stat3
→ One sentence explaining why this player fits the query.

Rules:
- List ALL players from the provided profiles sorted by Rating descending (highest first).
- Do NOT skip any player unless their name is literally "None".
- Do NOT invent players.
- Age should be just the number (e.g. "26").
- Position format: broad group then detail in parentheses, e.g. "attacker (left-wing)", "defender (centre-back)".
- Rating: use the exact number from the profile rounded to 2 decimals, or write N/A.
- Key stats: pick 3-5 stats most relevant to the query from the profile data.
- If no players match, write exactly: No players found matching your criteria.
- No introduction, no summary, no headers. Just the player lines."""


def _merge_filters(
    llm_filter: Filter | None,
    ui_position: str | None,
    ui_min_age: int | None,
    ui_max_age: int | None,
    ui_min_height: int | None,
    ui_max_height: int | None,
    ui_nationality: str | None,
    ui_league: str | None,
) -> Filter | None:
    """
    Merge LLM-extracted filters with explicit UI filters.
    UI filters always override LLM filters for the same field.
    """
    from qdrant_client.models import MinShould
    from agents.filter_agent import DETAILED_MAP, BROAD_POSITIONS, _resolve_position

    must = list((llm_filter.must or []) if llm_filter else [])
    should = []

    # Overwrite position if UI provides one
    if ui_position:
        # Remove any existing position conditions from LLM
        must = [c for c in must if not (
            hasattr(c, 'key') and c.key in ("position", "detailed_position")
        )]
        broad, detailed = _resolve_position(ui_position)
        if detailed == "__winger__":
            should = [
                FieldCondition(key="detailed_position", match=MatchValue(value="left-wing")),
                FieldCondition(key="detailed_position", match=MatchValue(value="right-wing")),
            ]
        elif detailed:
            must.append(FieldCondition(key="detailed_position", match=MatchValue(value=detailed)))
        elif broad:
            must.append(FieldCondition(key="position", match=MatchValue(value=broad)))

    # Age filters
    if ui_min_age is not None:
        must = [c for c in must if not (hasattr(c, 'key') and c.key == "age" and hasattr(c.range, 'gte'))]
        must.append(FieldCondition(key="age", range=Range(gte=ui_min_age)))
    if ui_max_age is not None:
        must = [c for c in must if not (hasattr(c, 'key') and c.key == "age" and hasattr(c.range, 'lte'))]
        must.append(FieldCondition(key="age", range=Range(lte=ui_max_age)))

    # Height filters
    if ui_min_height is not None:
        must.append(FieldCondition(key="height", range=Range(gte=ui_min_height)))
    if ui_max_height is not None:
        must.append(FieldCondition(key="height", range=Range(lte=ui_max_height)))

    # Nationality
    if ui_nationality:
        must.append(FieldCondition(key="nationality", match=MatchValue(value=ui_nationality)))

    # League
    if ui_league:
        must.append(FieldCondition(key="league", match=MatchValue(value=ui_league)))

    if not must and not should:
        return None
    if should and must:
        from qdrant_client.models import MinShould
        return Filter(must=must, min_should=MinShould(conditions=should, min_count=1))
    elif should:
        return Filter(should=should)
    return Filter(must=must)


def search_augmentation(
    content: str,
    ui_position: Optional[str] = None,
    ui_min_age: Optional[int] = None,
    ui_max_age: Optional[int] = None,
    ui_min_height: Optional[int] = None,
    ui_max_height: Optional[int] = None,
    ui_nationality: Optional[str] = None,
    ui_league: Optional[str] = None,
) -> str:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    # Step 1: Extract LLM filters from text query
    llm_filter = None
    try:
        filter_llm = llm.with_structured_output(PlayerFilter)
        player_filter = filter_llm.invoke(
            f"Extract ONLY position, min_age, max_age, min_height, max_height from: {content}"
        )
        llm_filter = build_filters(player_filter)
    except Exception as e:
        print(f"Filter extraction failed: {e} — continuing without LLM filters")

    # Step 2: Merge LLM filters with explicit UI filters
    final_filter = _merge_filters(
        llm_filter,
        ui_position, ui_min_age, ui_max_age,
        ui_min_height, ui_max_height,
        ui_nationality, ui_league,
    )
    print(f"FINAL FILTER: {final_filter}")

    # Step 3: Semantic retrieval
    try:
        results = qdrant_retriever(content or "football player", final_filter, top_k=25)
    except Exception as e:
        print(f"Retriever error: {e}")
        return "Search temporarily unavailable. Please try again."

    if not results:
        return "No players found matching your criteria."

    # Step 4: LLM formats results
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
        return "\n\n".join(results[:5])
