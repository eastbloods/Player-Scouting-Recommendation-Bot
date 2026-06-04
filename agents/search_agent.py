from langchain_groq import ChatGroq
from vector_store.retriever import qdrant_retriever
from agents.filter_agent import build_filters, PlayerFilter
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
import os
import re
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ── Normalization maps ──────────────────────────────────────────────────────
# Qdrant stores league names exactly as ingested from SportMonks.
# The UI may send friendly/branded names that don't match exactly.
LEAGUE_NORM: dict[str, str] = {
    "trendyol super lig": "Super Lig",
    "trendyol sÜper lig": "Super Lig",
    "sÜper lig": "Super Lig",
    "super lig": "Super Lig",
    "turkish super lig": "Super Lig",
    "tff 1. lig": "1. Lig",
    "1. lig": "1. Lig",
    "tff first league": "1. Lig",
    "tff second league": "2. Lig",
    "seria a": "Serie A",
    "serie a tim": "Serie A",
    "ligue 1 uber eats": "Ligue 1",
    "laliga": "La Liga",
    "la liga": "La Liga",
    "laliga ea sports": "La Liga",
    "sky bet championship": "Championship",
    "efl championship": "Championship",
    "premier league": "Premier League",
    "english premier league": "Premier League",
    "bpl": "Premier League",
    "bundesliga 1": "Bundesliga",
    "saudi pro league": "Saudi Pro League",
    "roshn saudi league": "Saudi Pro League",
}

# Nationality names — Qdrant stores the SportMonks value (often English)
NAT_NORM: dict[str, str] = {
    "turkey": "Turkey",
    "tÜrkiye": "Turkey",
    "turkiye": "Turkey",
    "türkiye": "Turkey",
    "england": "England",
    "united states": "United States",
    "usa": "United States",
    "south korea": "South Korea",
    "korea republic": "South Korea",
    "ivory coast": "Côte d'Ivoire",
    "cote d'ivoire": "Côte d'Ivoire",
    "czech republic": "Czech Republic",
    "czechia": "Czech Republic",
    "dr congo": "DR Congo",
    "democratic republic of congo": "DR Congo",
}


def _norm_league(v: str) -> str:
    return LEAGUE_NORM.get(v.lower().strip(), v.strip())


def _norm_nationality(v: str) -> str:
    return NAT_NORM.get(v.lower().strip(), v.strip())


# ── Country → domestic league names (stored in Qdrant) ────────────────────────
COUNTRY_LEAGUES: dict[str, list[str]] = {
    "England":     ["Premier League", "Championship", "League One", "League Two", "Enterprise National League"],
    "Spain":       ["La Liga", "Segunda División"],
    "Germany":     ["Bundesliga", "2. Bundesliga"],
    "Italy":       ["Serie A", "Serie B"],
    "France":      ["Ligue 1", "Ligue 2", "National", "Championnat National"],
    "Portugal":    ["Primeira Liga", "Liga Portugal 2", "Liga Portugal"],
    "Netherlands": ["Eredivisie", "Eerste Divisie"],
    "Turkey":      ["Super Lig", "1. Lig"],
    "Poland":      ["Ekstraklasa", "I liga"],
    "Belgium":     ["Belgian Pro League", "Challenger Pro League"],
    "Austria":     ["Austrian Bundesliga", "2. Liga"],
    "Scotland":    ["Scottish Premiership", "Scottish Championship"],
    "Switzerland": ["Super League", "Challenge League"],
    "Sweden":      ["Allsvenskan", "Superettan"],
    "Norway":      ["Eliteserien", "OBOS-ligaen"],
    "Denmark":     ["Danish Superliga", "1. Division"],
    "Czech Republic": ["Czech First League", "FNL"],
    "Hungary":     ["NB I", "NB II"],
    "Greece":      ["Super League", "Super League 2"],
    "Russia":      ["Russian Premier League", "FNL"],
    "Serbia":      ["Super Liga"],
    "Croatia":     ["HNL"],
    "Romania":     ["Liga I"],
    "Slovakia":    ["Niké Liga"],
    "Brazil":      ["Brasileirão", "Série B"],
    "Argentina":   ["Argentine Primera División", "Primera Nacional"],
    "Mexico":      ["Liga MX"],
    "Colombia":    ["Categoría Primera A"],
    "United States": ["MLS"],
    "Saudi Arabia": ["Saudi Pro League"],
    "Iran":        ["Persian Gulf Pro League"],
    "Egypt":       ["Egyptian Premier League"],
    "Morocco":     ["Botola Pro"],
    "Australia":   ["A-League Men"],
    "Japan":       ["J1 League"],
    "South Korea": ["K League 1"],
    "India":       ["Indian Super League"],
}


def _leagues_for_country(country: str) -> list[str]:
    """Return known league names for a given country name."""
    normalized = country.strip()
    # Try direct match
    leagues = COUNTRY_LEAGUES.get(normalized)
    if leagues:
        return leagues
    # Try case-insensitive match
    for k, v in COUNTRY_LEAGUES.items():
        if k.lower() == normalized.lower():
            return v
    return []


def _extract_numeric_from_query(query: str) -> dict:
    """Reliably extract age/height constraints via regex — faster and more accurate than LLM."""
    result = {}
    q = query.lower()

    # ─ Keyword-based age hints (no explicit number) ─
    if re.search(r'\bteenager\b|\bteenage\b|\byouth\b', q) and 'max_age' not in result:
        result['max_age'] = 19
    elif re.search(r'\byoung\b|\byoungster\b|\bprodigy\b', q) and 'max_age' not in result:
        result['max_age'] = 23
    elif re.search(r'\bveteran\b', q) and 'min_age' not in result:
        result['min_age'] = 32
    elif re.search(r'\bexperienced\b', q) and 'min_age' not in result:
        result['min_age'] = 28

    # ─ Explicit numeric age ─
    m = re.search(r'\bunder\s+(\d{2})\b(?!\s*cm)|\byounger\s+than\s+(\d{2})|\bno\s+older\s+than\s+(\d{2})', q)
    if m:
        val = next(v for v in m.groups() if v)
        result['max_age'] = int(val)  # overrides keyword hint
    m = re.search(r'\bover\s+(\d{2})\b(?!\s*cm)|\bolder\s+than\s+(\d{2})|\bat\s+least\s+(\d{2})\s*(?:years|yr)', q)
    if m:
        val = next(v for v in m.groups() if v)
        result['min_age'] = int(val)

    # ─ Height ─
    m = re.search(r'\bover\s+(\d{3})\s*cm|\b(\d{3})\s*cm\s*\+|taller\s+than\s+(\d{3})|at\s+least\s+(\d{3})\s*cm', q)
    if m:
        val = next(v for v in m.groups() if v)
        result['min_height'] = int(val)
    m = re.search(r'\bunder\s+(\d{3})\s*cm|shorter\s+than\s+(\d{3})', q)
    if m:
        val = next(v for v in m.groups() if v)
        result['max_height'] = int(val)
    return result


SYSTEM_PROMPT = """You are GoatScout, an expert AI football scout assistant.

Given a scout query and player profiles, format ALL provided players.

STRICT output format — one player per line, then a scout note on the next line:
Name | Age, Club (League) | position_group (detailed_position) | ★ Rating X.XX | Key: stat1, stat2, stat3
→ Scout note here.

Rules:
- List ALL players sorted by Rating descending (highest first).
- Do NOT skip any player unless their name is literally "None".
- Do NOT invent players.
- Age should be just the number (e.g. "26").
- Position format: broad group then detail in parentheses, e.g. "attacker (left-wing)", "defender (centre-back)".
- Rating: exact number from profile rounded to 2 decimals, or N/A.
- Key stats: pick 3-5 stats most relevant to the scout query.
- If no players match, write exactly: No players found matching your criteria.
- No introduction, no summary, no headers. Just the player lines.

For the scout note (→ line):
- Write 1-2 sentences as an experienced football scout.
- Describe what the stats reveal about this player's game: their strengths, how they play, what role they'd suit.
- Be specific and use football language (e.g. "drives past defenders", "presses high", "links play", "reads the game early").
- Never write generic phrases like 'fits the query', 'does not fit', 'matches the criteria'.
- Never repeat the position or age — those are already in the header line."""


def _merge_filters(
    llm_filter: Filter | None,
    ui_position: str | None,
    ui_min_age: int | None,
    ui_max_age: int | None,
    ui_min_height: int | None,
    ui_max_height: int | None,
    ui_nationality: str | None,
    ui_league: str | None,
    ui_team_country: str | None = None,
) -> Filter | None:
    """
    Merge LLM-extracted filters with explicit UI filters.
    UI filters always override LLM filters for the same field.
    """
    from qdrant_client.models import MinShould
    from agents.filter_agent import DETAILED_MAP, BROAD_POSITIONS, _resolve_position

    must = list((llm_filter.must or []) if llm_filter else [])
    # Read should conditions from llm_filter (e.g. wing OR filter: left-wing | right-wing)
    should = list((llm_filter.should or []) if llm_filter else [])
    # Also pick up min_should conditions if present
    if llm_filter and llm_filter.min_should:
        should.extend(llm_filter.min_should.conditions or [])

    # Overwrite position if UI provides one
    if ui_position:
        # Remove any existing position conditions from LLM
        must = [c for c in must if not (
            hasattr(c, 'key') and c.key in ("position", "detailed_position")
        )]
        broad, detailed = _resolve_position(ui_position)
        if detailed == "__wing__":
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

    # Nationality — normalise before exact match
    if ui_nationality:
        must.append(FieldCondition(key="nationality", match=MatchValue(value=_norm_nationality(ui_nationality))))

    # League — exact league name OR expanded from team_country
    if ui_league:
        must.append(FieldCondition(key="league", match=MatchValue(value=_norm_league(ui_league))))
    elif ui_team_country:
        # Expand country → list of domestic league names → OR filter
        country_leagues = _leagues_for_country(ui_team_country)
        if country_leagues:
            league_conditions = [
                FieldCondition(key="league", match=MatchValue(value=lg))
                for lg in country_leagues
            ]
            # We need these as a should (OR) block within must
            from qdrant_client.models import NestedCondition
            # Qdrant supports nested should via Filter nested
            # Use MinShould pattern for league OR filter
            country_should = league_conditions
        else:
            country_should = []

        if country_should:
            # Inject country OR leagues into must via nested filter
            must.append(Filter(should=country_should))

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
    ui_team_country: Optional[str] = None,
    ui_team: Optional[str] = None,
) -> str:
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    # Step 1a: Regex-based extraction (reliable, runs always)
    regex_nums = _extract_numeric_from_query(content or "")
    print(f"REGEX FILTERS: {regex_nums}")

    # Step 1b: LLM filter extraction for position (less critical if it fails)
    llm_filter = None
    try:
        filter_llm = llm.with_structured_output(PlayerFilter)
        player_filter = filter_llm.invoke(
            f"Extract ONLY position from this query (ignore age/height, those are handled): {content}"
        )
        llm_filter = build_filters(player_filter)
    except Exception as e:
        print(f"Filter extraction failed: {e} — continuing without LLM filters")

    # Step 2: Merge — regex numbers override LLM, UI overrides everything
    # Apply regex-extracted numbers as fallback when UI doesn't provide them
    eff_min_age    = ui_min_age    or regex_nums.get('min_age')
    eff_max_age    = ui_max_age    or regex_nums.get('max_age')
    eff_min_height = ui_min_height or regex_nums.get('min_height')
    eff_max_height = ui_max_height or regex_nums.get('max_height')

    final_filter = _merge_filters(
        llm_filter,
        ui_position, eff_min_age, eff_max_age,
        eff_min_height, eff_max_height,
        ui_nationality, ui_league,
        ui_team_country=ui_team_country,
    )
    print(f"FINAL FILTER: {final_filter}")

    # If team specified, add it to semantic query
    effective_query = content or ""
    if ui_team and ui_team not in effective_query:
        effective_query = f"{effective_query} team:{ui_team}".strip()

    # Step 3: Semantic retrieval
    try:
        results = qdrant_retriever(effective_query or "football player", final_filter, top_k=12)
    except Exception as e:
        print(f"Retriever error: {e}")
        return "Search temporarily unavailable. Please try again."

    if not results:
        return "No players found matching your criteria."

    # Step 4: Condense profiles for LLM (avoid token overflow)
    condensed = [_condense_profile(r) for r in results]
    profiles_text = "\n\n".join(condensed)

    from langchain_core.messages import SystemMessage, HumanMessage
    for attempt in range(2):
        try:
            response = llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"Scout Query: {content or 'football player'}\n\n"
                    f"Player Profiles:\n{profiles_text}\n\n"
                    f"Format all players now:"
                ))
            ])
            result_text = response.content.strip()
            # Accept any non-empty response (don't require |, LLM sometimes uses different separators)
            if result_text and len(result_text) > 30:
                return result_text
            print(f"LLM attempt {attempt+1} returned too-short response, retrying...")
        except Exception as e:
            print(f"LLM formatting error (attempt {attempt+1}): {e}")

    # Both attempts failed — build stat-based summaries from raw data
    return _fallback_format(results)



def _condense_profile(raw: str) -> str:
    """Extract key fields from a raw profile to reduce token count."""
    import re
    lines = raw.strip().split('\n')
    first_line = lines[0] if lines else raw[:200]

    # Extract stats — NOTE: exclude "goals conceded" (defensive stat, not goals scored)
    rating_m    = re.search(r'avg rating (\d+\.\d+)', raw)
    rating      = rating_m.group(1) if rating_m else 'N/A'
    goals_m     = re.search(r'(\d+) goals(?! conceded)', raw)  # scored goals only
    assists_m   = re.search(r'(\d+) assists', raw)
    shots_m     = re.search(r'(\d+) shots', raw)
    tackles_m   = re.search(r'(\d+) tackles', raw)
    aerials_m   = re.search(r'(\d+) aerials won', raw)
    dribbles_m  = re.search(r'(\d+)/\d+ dribbles', raw)
    key_passes_m = re.search(r'(\d+) key passes', raw)
    app_m       = re.search(r'(\d+) appearances', raw)
    mins_m      = re.search(r'(\d+) minutes', raw)
    pass_acc_m  = re.search(r'([\d.]+)% accuracy', raw)
    big_m       = re.search(r'(\d+) big chances', raw)

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
    """When LLM fails, build pipe-separated format with real stat summaries."""
    output = []
    for raw in results[:12]:
        lines = raw.strip().split('\n')
        first = lines[0] if lines else ''

        name_m = re.match(
            r'^(.+?)\s*[–-]\s*(\d+)\s*years?\s*old,\s*(\d+)\s*cm,\s*(.+?),\s*nationality:\s*(.+?),\s*(.+?),\s*(.+?)\.',
            first
        )
        if not name_m:
            continue

        name = name_m.group(1).strip()
        if not name or name == 'None':
            continue

        age    = name_m.group(2)
        height = name_m.group(3)
        pos    = name_m.group(4).strip()
        nat    = name_m.group(5).strip()
        club   = name_m.group(6).strip()
        league = name_m.group(7).strip()

        rating_m   = re.search(r'avg rating (\d+\.\d+)', raw)
        rating     = rating_m.group(1) if rating_m else 'N/A'
        goals_m    = re.search(r'(\d+) goals(?! conceded)', raw)  # scored goals only
        assists_m  = re.search(r'(\d+) assists', raw)
        shots_m    = re.search(r'(\d+) shots', raw)
        tackles_m  = re.search(r'(\d+) tackles', raw)
        aerials_m  = re.search(r'(\d+) aerials won', raw)
        kp_m       = re.search(r'(\d+) key passes', raw)
        app_m      = re.search(r'(\d+) appearances', raw)
        drib_m     = re.search(r'(\d+)/\d+ dribbles', raw)

        # Key stats for pipe field
        key_stats = []
        if goals_m:   key_stats.append(f"{goals_m.group(1)} goals")
        if assists_m: key_stats.append(f"{assists_m.group(1)} assists")
        if tackles_m: key_stats.append(f"{tackles_m.group(1)} tackles")
        if aerials_m: key_stats.append(f"{aerials_m.group(1)} aerials won")
        if kp_m:      key_stats.append(f"{kp_m.group(1)} key passes")
        if drib_m:    key_stats.append(f"{drib_m.group(1)} dribbles")

        # Generate a real summary sentence
        facts = []
        if app_m: facts.append(f"{app_m.group(1)} appearances")
        if goals_m and int(goals_m.group(1)) > 0:
            g = goals_m.group(1)
            a = assists_m.group(1) if assists_m else '0'
            facts.append(f"{g} goals and {a} assists")
        if tackles_m and int(tackles_m.group(1)) > 0:
            facts.append(f"{tackles_m.group(1)} tackles")
        if aerials_m and int(aerials_m.group(1)) > 0:
            facts.append(f"{aerials_m.group(1)} aerials won")
        if kp_m and int(kp_m.group(1)) > 0:
            facts.append(f"{kp_m.group(1)} key passes")
        if shots_m and int(shots_m.group(1)) > 0:
            facts.append(f"{shots_m.group(1)} shots")
        if drib_m and int(drib_m.group(1)) > 0:
            facts.append(f"{drib_m.group(1)} successful dribbles")

        if facts:
            summary = f"{name} ({nat}, {height}cm) — this season: {', '.join(facts[:4])}."
        else:
            summary = f"{name} is a {pos} at {club} ({league}), aged {age}."

        output.append(
            f"{name} | {age}, {club} ({league}) | {pos} | ★ Rating {rating} | Key: {', '.join(key_stats[:4]) or 'N/A'}\n"
            f"→ {summary}"
        )

    return '\n'.join(output) if output else "No players found matching your criteria."

