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
        results = qdrant_retriever(content or "football player", final_filter, top_k=20)
    except Exception as e:
        print(f"Retriever error: {e}")
        return "Search temporarily unavailable. Please try again."

    if not results:
        return "No players found matching your criteria."

    # Step 4: Condense profiles for LLM (avoid token overflow)
    condensed = []
    for r in results:
        condensed.append(_condense_profile(r))

    profiles = "\n\n".join(condensed)
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
        # Build parser-friendly fallback from raw data
        return _fallback_format(results)


def _condense_profile(raw: str) -> str:
    """Extract key fields from a raw profile to reduce token count."""
    import re
    lines = raw.strip().split('\n')
    first_line = lines[0] if lines else raw[:200]

    # Extract stats
    rating_m = re.search(r'avg rating (\d+\.\d+)', raw)
    rating = rating_m.group(1) if rating_m else 'N/A'
    goals_m = re.search(r'(\d+) goals', raw)
    assists_m = re.search(r'(\d+) assists', raw)
    shots_m = re.search(r'(\d+) shots', raw)
    tackles_m = re.search(r'(\d+) tackles', raw)
    aerials_m = re.search(r'(\d+) aerials won', raw)
    dribbles_m = re.search(r'(\d+)/\d+ dribbles', raw)
    key_passes_m = re.search(r'(\d+) key passes', raw)
    app_m = re.search(r'(\d+) appearances', raw)
    mins_m = re.search(r'(\d+) minutes', raw)
    pass_acc_m = re.search(r'([\d.]+)% accuracy', raw)
    big_m = re.search(r'(\d+) big chances', raw)

    stats = []
    if goals_m: stats.append(f"{goals_m.group(1)} goals")
    if assists_m: stats.append(f"{assists_m.group(1)} assists")
    if shots_m: stats.append(f"{shots_m.group(1)} shots")
    if tackles_m: stats.append(f"{tackles_m.group(1)} tackles")
    if aerials_m: stats.append(f"{aerials_m.group(1)} aerials won")
    if key_passes_m: stats.append(f"{key_passes_m.group(1)} key passes")
    if dribbles_m: stats.append(f"{dribbles_m.group(1)} dribbles")
    if big_m: stats.append(f"{big_m.group(1)} big chances created")
    if pass_acc_m: stats.append(f"{pass_acc_m.group(1)}% pass accuracy")

    stat_line = ', '.join(stats[:6]) if stats else 'no detailed stats'
    app_info = ''
    if app_m: app_info += f"{app_m.group(1)} apps"
    if mins_m: app_info += f", {mins_m.group(1)} min"

    return f"{first_line}\nRating: {rating}. {app_info}. Key stats: {stat_line}."


def _fallback_format(results: list[str]) -> str:
    """When LLM fails, build pipe-separated format from raw profiles."""
    import re
    output = []
    for raw in results[:15]:
        lines = raw.strip().split('\n')
        first = lines[0] if lines else ''

        name_m = re.match(r'^(.+?)\s*[–-]\s*(\d+)\s*years?\s*old,\s*(\d+)\s*cm,\s*(.+?),\s*nationality:\s*(.+?),\s*(.+?),\s*(.+?)\.', first)
        if not name_m:
            continue

        name = name_m.group(1).strip()
        if name == 'None' or not name:
            continue

        age = name_m.group(2)
        pos = name_m.group(4).strip()
        club = name_m.group(6).strip()
        league = name_m.group(7).strip()

        rating_m = re.search(r'avg rating (\d+\.\d+)', raw)
        rating = rating_m.group(1) if rating_m else 'N/A'

        goals_m = re.search(r'(\d+) goals', raw)
        tackles_m = re.search(r'(\d+) tackles', raw)
        aerials_m = re.search(r'(\d+) aerials won', raw)

        stats = []
        if goals_m: stats.append(f"{goals_m.group(1)} goals")
        if tackles_m: stats.append(f"{tackles_m.group(1)} tackles")
        if aerials_m: stats.append(f"{aerials_m.group(1)} aerials")

        output.append(
            f"{name} | {age}, {club} ({league}) | {pos} | ★ Rating {rating} | Key: {', '.join(stats) or 'N/A'}\n"
            f"→ Matched from database."
        )

    return '\n'.join(output) if output else "No players found matching your criteria."

