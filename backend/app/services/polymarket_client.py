"""
Polymarket CLOB API client.

Uses the Gamma API (public, no auth required) to fetch market data
including prices, volumes, and metadata.
"""

import json
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class PolymarketClient:
    """Client for Polymarket's public Gamma API."""

    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self, timeout: int = 15):
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "prediction-market-debater/1.0",
        })
        self._timeout = timeout
        self._last_request_time: float = 0
        self._min_request_interval: float = 0.25  # 250ms between requests

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_active_markets(
        self,
        category: Optional[str] = None,
        limit: int = 50,
        order: str = "volume24hr",
        offset: int = 0,
    ) -> list[dict]:
        """Fetch active (not closed) markets, optionally filtered by category.

        Args:
            category: Optional category/tag filter (e.g. "crypto", "politics").
            limit: Max number of markets to return (capped at 100 by API).
            order: Sort field, default "volume24hr".

        Returns:
            List of normalized market dicts.
        """
        params: dict = {
            "closed": "false",
            "limit": min(limit, 100),
            "offset": offset,
            "order": order,
            "ascending": "false",
        }
        if category:
            params["tag"] = category.lower()

        try:
            raw_markets = self._request("/markets", params=params)
        except Exception:
            logger.exception("Failed to fetch active markets")
            return []

        if not isinstance(raw_markets, list):
            logger.warning("Unexpected response type for /markets: %s", type(raw_markets))
            return []

        normalized = []
        for raw in raw_markets:
            try:
                market = self._normalize_market(raw)
                normalized.append(market)
            except Exception:
                logger.debug("Skipping malformed market: %s", raw.get("condition_id", "?"))
                continue

        return normalized

    def get_market(self, condition_id: str) -> Optional[dict]:
        """Fetch a single market by condition_id.

        Returns:
            Normalized market dict, or None if not found.
        """
        try:
            raw = self._request(f"/markets/{condition_id}")
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None
            logger.exception("Failed to fetch market %s", condition_id)
            return None
        except Exception:
            logger.exception("Failed to fetch market %s", condition_id)
            return None

        if not isinstance(raw, dict) or "condition_id" not in raw:
            return None

        try:
            return self._normalize_market(raw)
        except Exception:
            logger.exception("Failed to normalize market %s", condition_id)
            return None

    def get_market_by_slug(self, slug: str) -> Optional[dict]:
        """Search for a market by its URL slug.

        Searches both active and closed markets so resolved markets
        can still be found.

        Returns:
            Normalized market dict, or None if not found.
        """
        # Try without closed filter first (returns both active and closed)
        for closed_param in [None, "true", "false"]:
            try:
                params = {"slug": slug, "limit": 1}
                if closed_param is not None:
                    params["closed"] = closed_param
                results = self._request("/markets", params=params)
            except Exception:
                logger.exception("Failed to fetch market by slug: %s", slug)
                return None

            if isinstance(results, list) and len(results) > 0:
                try:
                    return self._normalize_market(results[0])
                except Exception:
                    return None

        return None

    def get_resolved_markets(
        self,
        limit: int = 50,
        offset: int = 0,
        order: str = "volume",
    ) -> list[dict]:
        """Fetch closed/resolved markets with their outcomes.

        Args:
            limit: Max number of markets to return (capped at 100).
            offset: Pagination offset.
            order: Sort field, default "volume".

        Returns:
            List of normalized market dicts with added 'resolved' and
            'resolution' fields (True = YES won, False = NO won, None = ambiguous).
        """
        params: dict = {
            "closed": "true",
            "limit": min(limit, 100),
            "offset": offset,
            "order": order,
            "ascending": "false",
        }

        try:
            raw_markets = self._request("/markets", params=params)
        except Exception:
            logger.exception("Failed to fetch resolved markets")
            return []

        if not isinstance(raw_markets, list):
            return []

        results = []
        for raw in raw_markets:
            try:
                market = self._normalize_market(raw)
                # Determine resolution from outcome prices
                resolution = self._extract_resolution(market)
                if resolution is not None:
                    market["resolved"] = True
                    market["resolution"] = resolution  # True=YES, False=NO
                    results.append(market)
            except Exception:
                continue

        return results

    @staticmethod
    def _extract_resolution(market: dict) -> bool | None:
        """Determine resolution from outcome_prices.

        On a resolved market, the winning outcome has price ~1.0 and losers ~0.0.

        For binary Yes/No markets: True if YES won, False if NO won.
        For two-outcome markets (e.g. team1 vs team2): True if first outcome
        won (index 0), False if second outcome won (index 1). This matches
        the convention that market_price represents the first outcome's
        probability.

        Returns True/False, or None if not yet resolved or ambiguous.
        """
        outcomes = market.get("outcomes", [])
        prices = market.get("outcome_prices", [])

        if len(outcomes) < 2 or len(prices) < 2:
            return None

        # Check if any outcome has price >= 0.95 (resolved)
        # Use 0.95 instead of 0.99 to catch markets near resolution
        for i, (outcome, price) in enumerate(zip(outcomes, prices)):
            if price >= 0.95:
                # For Yes/No markets
                if outcome.lower() == "yes":
                    return True
                elif outcome.lower() == "no":
                    return False
                # For non-yes/no markets (e.g. team names):
                # index 0 = first outcome = "YES" equivalent
                # index 1 = second outcome = "NO" equivalent
                return i == 0

        return None

    def search_markets(self, query: str, limit: int = 20) -> list[dict]:
        """Search markets by keyword in question text.

        The Gamma API does not have a dedicated search endpoint, so this
        fetches a broad set of active markets and filters client-side.

        Args:
            query: Search keywords (case-insensitive substring match).
            limit: Max results to return.

        Returns:
            List of normalized market dicts whose question contains the query.
        """
        # Fetch a larger batch to search through
        all_markets = self.get_active_markets(limit=100)

        query_lower = query.lower()
        matched = []
        for market in all_markets:
            question = market.get("question", "")
            description = market.get("description", "")
            if query_lower in question.lower() or query_lower in description.lower():
                matched.append(market)
                if len(matched) >= limit:
                    break

        return matched

    # ------------------------------------------------------------------
    # Category classification
    # ------------------------------------------------------------------

    # Regex patterns per category — uses word boundaries (\b) to avoid
    # false positives like "sol" matching "resolve" or "eth" matching "whether".
    import re as _re

    _CATEGORY_RULES: list[tuple[str, "_re.Pattern"]] = []

    @classmethod
    def _init_rules(cls):
        """Build compiled regex patterns once."""
        if cls._CATEGORY_RULES:
            return
        import re
        _defs: dict[str, list[str]] = {
            # Sports checked FIRST — has most distinctive patterns
            "Sports": [
                r"\bvs\.?\b", r"\bnba\b", r"\bnfl\b", r"\bmlb\b", r"\bnhl\b",
                r"\bpremier league\b", r"\bchampions league\b", r"\bworld cup\b",
                r"\bolympics\b", r"\bsoccer\b", r"\bfootball\b", r"\bbasketball\b",
                r"\bbaseball\b", r"\btennis\b", r"\bgolf\b", r"\bboxing\b",
                r"\bufc\b", r"\bmma\b", r"\bchampionship\b", r"\bsuper bowl\b",
                r"\bplayoffs\b", r"\bmvp\b", r"\bla liga\b", r"\bserie a\b",
                r"\bbundesliga\b", r"\bformula\b", r"\bf1\b",
                r"\bbarcelona\b", r"\breal madrid\b", r"\bmanchester\b",
                r"\bliverpool\b", r"\bchelsea\b", r"\blakers\b", r"\bceltics\b",
                r"\bwarriors\b", r"\blebron\b", r"\bo/u\b", r"\bspread\b",
                r"\bhawks\b", r"\bmavericks\b", r"\bclippers\b", r"\bnuggets\b",
                r"\bgrizzlies\b", r"\bpacers\b", r"\bbulls\b", r"\braptors\b",
                r"\bthunder\b", r"\bnets\b", r"\bpenguins\b", r"\bhurricanes\b",
                r"\bdevils\b", r"\brangers\b", r"\bstars\b", r"\bavalanch\b",
                r"\bblues\b", r"\bflames\b", r"\bcardinals\b", r"\bmustangs\b",
                r"\bgame \d", r"\bwin on 20\d\d",
                r"\bfifa\b", r"\bbo[35]\b", r"\besports?\b", r"\blol\b",
                r"\bcounter-strike\b",
            ],
            "Crypto": [
                r"\bbitcoin\b", r"\bbtc\b", r"\bethereum\b", r"\bcrypto\b",
                r"\bblockchain\b", r"\bsolana\b", r"\bdogecoin\b", r"\bdoge\b",
                r"\bnft\b", r"\bdefi\b", r"\btoken\b", r"\baltcoin\b",
                r"\bmemecoin\b", r"\bbinance\b", r"\bcoinbase\b", r"\bstablecoin\b",
                r"\bweb3\b", r"\bhalving\b", r"\b\$btc\b", r"\b\$eth\b",
                r"\b\$sol\b", r"\b\$usdt\b",
            ],
            "Politics": [
                r"\bpresident\b", r"\belection\b", r"\btrump\b", r"\bbiden\b",
                r"\bdemocrat\b", r"\brepublican\b", r"\bcongress\b", r"\bsenate\b",
                r"\bgovernor\b", r"\bparliament\b", r"\bprime minister\b",
                r"\bnato\b", r"\bwar\b", r"\bceasefire\b", r"\btariff\b",
                r"\bsanction\b", r"\bimpeach\b", r"\bvote\b", r"\bnominee\b",
                r"\bnomination\b", r"\binaugurat\b", r"\bpolitical\b",
                r"\bnetanyahu\b", r"\bzelensky\b", r"\bputin\b", r"\bmodi\b",
                r"\bukraine\b", r"\bgaza\b", r"\btaiwan\b",
                r"\bnuclear\b", r"\bmissile\b", r"\bmilitary\b", r"\binvasion\b",
            ],
            "Science & Tech": [
                r"\bartificial intelligence\b", r"\bgpt\b", r"\bopenai\b",
                r"\bspacex\b", r"\bnasa\b", r"\bclimate change\b", r"\bvaccine\b",
                r"\bchatgpt\b", r"\bllm\b", r"\banthropic\b", r"\bneuralink\b",
                r"\bjailbreak\b", r"\bdeepseek\b", r"\bmarket cap\b",
                r"\bsemiconductor\b", r"\bnvidia\b", r"\btsmc\b", r"\bstarship\b",
                r"\bcrispr\b", r"\bself-driving\b", r"\btesla\b",
                r"\bmicrosoft\b", r"\bgoogle\b", r"\bmeta\b", r"\bapple\b",
            ],
            "Economics": [
                r"\bfed\b", r"\binterest rate\b", r"\binflation\b", r"\bgdp\b",
                r"\brecession\b", r"\bstock\b", r"\bs&p\b", r"\bnasdaq\b",
                r"\btreasury\b", r"\bunemployment\b", r"\bcpi\b", r"\bfomc\b",
                r"\brate cut\b", r"\brate hike\b", r"\boil price\b",
                r"\bgold price\b", r"\bdebt ceiling\b",
            ],
            "Entertainment": [
                r"\boscar\b", r"\bgrammy\b", r"\bemmy\b", r"\bmovie\b",
                r"\bbox office\b", r"\bnetflix\b", r"\bspotify\b",
                r"\bcelebrity\b", r"\baward\b", r"\btv show\b",
                r"\bstreamer\b", r"\btwitch\b",
            ],
        }
        for cat, patterns in _defs.items():
            combined = "|".join(patterns)
            cls._CATEGORY_RULES.append((cat, re.compile(combined, re.IGNORECASE)))

    @classmethod
    def classify_market(cls, question: str, description: str = "") -> str:
        """Classify a market into a category based on regex keyword matching.

        Only uses the question text for classification to avoid false positives
        from generic description words like 'resolve', 'market', etc.
        """
        cls._init_rules()
        text = question.lower()
        scores: dict[str, int] = {}
        for cat, pattern in cls._CATEGORY_RULES:
            matches = pattern.findall(text)
            if matches:
                scores[cat] = len(matches)
        if scores:
            return max(scores, key=scores.get)
        return "Other"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_market(self, raw: dict) -> dict:
        """Convert raw API market object to normalized format.

        Handles the JSON-string-within-JSON fields (outcomePrices, outcomes).
        """
        # Parse outcomePrices: JSON string like '["0.41","0.59"]'
        outcome_prices_raw = raw.get("outcomePrices", "[]")
        if isinstance(outcome_prices_raw, str):
            try:
                outcome_prices = [float(p) for p in json.loads(outcome_prices_raw)]
            except (json.JSONDecodeError, ValueError, TypeError):
                outcome_prices = []
        elif isinstance(outcome_prices_raw, list):
            outcome_prices = [float(p) for p in outcome_prices_raw]
        else:
            outcome_prices = []

        # Parse outcomes: JSON string like '["Yes","No"]'
        outcomes_raw = raw.get("outcomes", "[]")
        if isinstance(outcomes_raw, str):
            try:
                outcomes = json.loads(outcomes_raw)
            except (json.JSONDecodeError, ValueError):
                outcomes = []
        elif isinstance(outcomes_raw, list):
            outcomes = outcomes_raw
        else:
            outcomes = []

        # YES price is typically the first outcome price
        market_price = outcome_prices[0] if outcome_prices else 0.0

        # Safe float conversion for numeric fields
        def _safe_float(val, default=0.0):
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        # Auto-classify if Polymarket doesn't provide category
        category = raw.get("category", "")
        if not category:
            category = self.classify_market(
                raw.get("question", ""),
                raw.get("description", ""),
            )

        return {
            "condition_id": raw.get("condition_id", ""),
            "slug": raw.get("slug", ""),
            "question": raw.get("question", ""),
            "description": raw.get("description", ""),
            "category": category,
            "market_price": round(market_price, 4),
            "volume_24h": _safe_float(raw.get("volume24hr")),
            "liquidity": _safe_float(raw.get("liquidity")),
            "end_date": raw.get("endDate", ""),
            "image": raw.get("image", ""),
            "outcomes": outcomes,
            "outcome_prices": outcome_prices,
        }

    def _request(self, endpoint: str, params: Optional[dict] = None):
        """Make HTTP request with rate limiting, timeout, and error handling.

        Args:
            endpoint: API path (e.g. "/markets").
            params: Optional query parameters.

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            requests.exceptions.HTTPError: On 4xx/5xx responses.
            requests.exceptions.RequestException: On connection/timeout errors.
        """
        # Rate limiting: ensure minimum interval between requests
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)

        url = f"{self.BASE_URL}{endpoint}"
        logger.debug("GET %s params=%s", url, params)

        response = self._session.get(url, params=params, timeout=self._timeout)
        self._last_request_time = time.monotonic()

        response.raise_for_status()
        return response.json()
