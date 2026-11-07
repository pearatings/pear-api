"""The `Pear` client: one method per PEARatings data API endpoint (baseball and softball).

Return values follow two rules:
- An endpoint that returns one table comes back as a pandas DataFrame. Everything else in the response
  (the data date, season, totals, ...) is in `df.attrs`.
- Anything else comes back as a dict, in which every list of records is a DataFrame. Nested fields are
  flattened to dotted column names (`record.wins`, `stats.PA`).
"""
import datetime as _dt
import os
from typing import Any, Dict, Iterable, List, Optional, Union
from urllib.parse import quote

import pandas as pd
import requests

from . import __version__
from .errors import (APIError, AuthenticationError, InvalidRequestError, NotFoundError, PearError,
                     RateLimitError)

DEFAULT_BASE_URL = "https://api.pearatings.com"
DIVISIONS = {"baseball": ("d1", "d2", "d3", "naia"), "softball": ("d1", "d2", "d3")}
_ERRORS = {400: InvalidRequestError, 401: AuthenticationError, 404: NotFoundError, 422: InvalidRequestError,
           429: RateLimitError}
_PAGE = 200  # the API's largest page for the player leaderboard and Lookup

Date = Union[str, _dt.date]


def _records(rows) -> pd.DataFrame:
    return pd.json_normalize(rows) if rows else pd.DataFrame()


def _frames(obj):
    """Every list of records (dicts) inside a response becomes a DataFrame; dicts are walked recursively."""
    if isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj):
        return _records(obj)
    if isinstance(obj, dict):
        return {k: _frames(v) for k, v in obj.items()}
    return obj


def _table(data: dict, key: str) -> pd.DataFrame:
    """data[key] as a DataFrame, with the rest of the response in .attrs."""
    df = _records(data.get(key))
    df.attrs = {k: v for k, v in data.items() if k != key}
    return df


def _drop_none(d: Optional[dict]) -> Optional[dict]:
    return None if d is None else {k: v for k, v in d.items() if v is not None}


def _csv(values: Union[None, str, Iterable[str]]) -> Optional[str]:
    return values if values is None or isinstance(values, str) else ",".join(values)


def _seg(text: str) -> str:
    """A team / conference / player name as one URL path segment."""
    return quote(str(text), safe="")


class Pear:
    """PEARatings data API client.

        from pearatings import Pear
        pear = Pear()                         # key from the PEAR_API_KEY environment variable
        pear = Pear(api_key="...")            # or pass it

    Every method takes keyword-only `sport` ("baseball" | "softball", default "baseball") and `division`
    ("d1" | "d2" | "d3" | "naia", default "d1") unless it exists for one division only.
    The API address comes from `base_url`, else the PEAR_API_URL environment variable, else
    https://api.pearatings.com.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 60):
        self.api_key = api_key or os.environ.get("PEAR_API_KEY")
        if not self.api_key:
            raise AuthenticationError("No API key: pass Pear(api_key=...) or set the PEAR_API_KEY environment variable")
        self.base_url = (base_url or os.environ.get("PEAR_API_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key, "User-Agent": f"pearatings-python/{__version__}"})

    def __repr__(self):
        return f"Pear(base_url={self.base_url!r})"

    # ------------------------------------------------------------------ plumbing

    def _request(self, method: str, path: str, params: Optional[dict] = None, json: Optional[dict] = None):
        try:
            r = self.session.request(method, f"{self.base_url}/v1/{path}", params=_drop_none(params),
                                     json=_drop_none(json), timeout=self.timeout)
        except requests.RequestException as e:
            raise PearError(f"Could not reach {self.base_url}: {e}") from e
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text or r.reason
            raise _ERRORS.get(r.status_code, APIError)(f"{r.status_code}: {detail}", status_code=r.status_code)
        return r

    def get(self, path: str, **params) -> Any:
        """Raw GET of any /v1 path (without the /v1/ prefix); returns the JSON as is.
        Example: pear.get("baseball/d1/ratings")."""
        return self._request("GET", path, params=params).json()

    def post(self, path: str, body: Optional[dict] = None) -> Any:
        """Raw POST of any /v1 path (without the /v1/ prefix); returns the JSON as is."""
        return self._request("POST", path, json=body or {}).json()

    @staticmethod
    def _div(sport: str, division: str) -> str:
        sport, division = sport.lower(), division.lower()
        if division not in DIVISIONS.get(sport, ()):
            raise ValueError(f"Unknown sport/division {sport}/{division}; choose from {DIVISIONS}")
        return f"{sport}/{division}"

    def _only(self, allowed, sport: str, division: str) -> str:
        path = self._div(sport, division)
        if path not in allowed:
            raise ValueError(f"Only available for {', '.join(allowed)}")
        return path

    # ------------------------------------------------------------------ teams and ratings

    def ratings(self, *, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """Current Team Strength Ratings (TSR) and PCR for every team. attrs: date."""
        return _table(self.get(f"{self._div(sport, division)}/ratings"), "teams")

    def preseason(self, season: int, *, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """A season's preseason ratings: the projection the season started from. D1 baseball has them back to
        2001; other divisions from 2026."""
        return _table(self.get(f"{self._div(sport, division)}/preseason", season=season), "teams")

    def stats(self, season: Optional[int] = None, *, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """Every team's calculated stats and ratings for a season (default: current). For a finished season these
        are the end-of-season ratings. attrs: date, season, columnMetadata."""
        return _table(self.get(f"{self._div(sport, division)}/stats", season=season), "stats")

    def teams(self, season: Optional[int] = None, *, sport: str = "baseball", division: str = "d1") -> List[str]:
        """Team names, in the exact spelling every other method expects."""
        return self.get(f"{self._div(sport, division)}/teams", season=season)["teams"]

    def team(self, team: str, *, sport: str = "baseball", division: str = "d1") -> dict:
        """One team: its ratings row (`team`), `upcoming_games` and `recent_games` with projections, `date`."""
        return _frames(self.get(f"{self._div(sport, division)}/team/{_seg(team)}"))

    def team_conferences(self, season: Optional[int] = None, *, sport: str = "baseball",
                         division: str = "d1") -> Dict[str, str]:
        """{team: conference}."""
        return self.get(f"{self._div(sport, division)}/team-conferences", season=season)["team_conferences"]

    def conferences(self, season: Optional[int] = None, *, sport: str = "baseball", division: str = "d1") -> List[str]:
        """Conference names."""
        return self.get(f"{self._div(sport, division)}/conferences", season=season)["conferences"]

    def conference_standings(self, conference: str, *, division: str = "d1") -> pd.DataFrame:
        """Current standings of one baseball conference. attrs: conference, date."""
        return _table(self.get(f"{self._div('baseball', division)}/conference/{_seg(conference)}"), "teams")

    def records(self, *, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """Current W-L, conference W-L, PCR and PCR score for every team, one row per team (in season only)."""
        records = self.get(f"{self._div(sport, division)}/current-records")["records"]
        return pd.DataFrame.from_dict(records, orient="index").rename_axis("Team").reset_index()

    def pcr_ranks(self, *, sport: str = "baseball", division: str = "d1") -> Dict[str, int]:
        """{team: PCR rank}."""
        return self.get(f"{self._div(sport, division)}/team-pcrs")["team_pcrs"]

    def combined_ratings(self) -> pd.DataFrame:
        """Every baseball team (D1, D2, D3, NAIA) on one rating scale."""
        return _records(self.get("baseball/combined-ratings"))

    def logo(self, team: str, *, sport: str = "baseball", division: str = "d1", variant: Optional[str] = None) -> bytes:
        """A team's logo as PNG bytes. `variant="dark"` gives the version drawn for dark backgrounds where there
        is one. Save it with open("logo.png", "wb").write(pear.logo("LSU"))."""
        return self._request("GET", f"{self._div(sport, division)}/logo/{_seg(team)}",
                             params={"variant": variant}).content

    def conference_logo(self, conference: str) -> bytes:
        """A conference's logo as PNG bytes."""
        return self._request("GET", f"conference-logo/{_seg(conference)}").content

    # ------------------------------------------------------------------ projections

    def games(self, date: Optional[Date] = None, *, team: Optional[str] = None, conference: Optional[str] = None,
              season: Optional[int] = None, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """Games on a date (default: today, or the next day with games) with PEAR's line, win probability and
        game quality (GQI); final scores once played. Filter by `team` or `conference`. `season` defaults to the
        date's year. attrs: date, count, min_date, max_date (the season's first and last game dates)."""
        if isinstance(date, _dt.date):
            date = date.isoformat()
        if date and season is None:
            season = int(date[:4])
        return _table(self.get(f"{self._div(sport, division)}/games", date=date, team=team, conference=conference,
                               season=season), "games")

    def matchup(self, away: str, home: str, *, neutral: bool = False, season: Optional[int] = None,
                sport: str = "baseball", division: str = "d1") -> dict:
        """Projected line and win probabilities for any two teams: spread, formatted_spread, home_win_prob and
        away_win_prob (percent, 0-100; games() gives 0-1), game_quality, home_pr, away_pr."""
        return self.post(f"{self._div(sport, division)}/matchup",
                         {"away_team": away, "home_team": home, "neutral": neutral, "season": season})

    def team_schedule(self, team: str, season: Optional[int] = None, *, sport: str = "baseball",
                      division: str = "d1") -> dict:
        """A team's full season: `schedule` (every game with its projection or result), `metrics` (ranks),
        `resume_path` (D1 baseball), `head_coach`, `data_date`."""
        return _frames(self.post(f"{self._div(sport, division)}/team-schedule", {"team_name": team, "season": season}))

    def simulate_wins(self, team: str, *, rating: Optional[float] = None, num_simulations: Optional[int] = None,
                      conference_only: bool = False, sport: str = "baseball", division: str = "d1") -> dict:
        """Simulate the rest of a team's season: expected_wins, min/max, and the `distribution` of final win
        totals. Pass `rating` to see the effect of a different team rating."""
        return _frames(self.post(f"{self._div(sport, division)}/simulate-wins",
                                 {"team_name": team, "rating": rating, "num_simulations": num_simulations,
                                  "conference_only": conference_only}))

    def season_projection(self, *, sport: str = "baseball", division: str = "d1") -> dict:
        """The whole projected season: `projected_pcr` (final PCR projection), `tournament_outlook` (projected
        field) and `team_simulated_results` ({team: projected games})."""
        return _frames(self.get(f"{self._div(sport, division)}/season-projection"))

    def conference_projections(self, *, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """One row per team: current and projected overall / conference records, PCR, TSR. attrs: date."""
        data = self.get(f"{self._div(sport, division)}/conference-view")
        df = _records([t for conf in data["conferences"] for t in conf["teams"]])
        df.attrs = {"date": data.get("date")}
        return df

    # ------------------------------------------------------------------ players

    def players(self, season: Optional[int] = None, *, side: str = "hitting", sort: Optional[str] = None,
                order: Optional[str] = None, conferences: Union[None, str, Iterable[str]] = None,
                positions: Union[None, str, Iterable[str]] = None, search: Optional[str] = None,
                limit: Optional[int] = None, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """Player leaderboard for a season: `side` "hitting" or "pitching", sorted by `sort` (a stat column;
        default PRV) in `order` ("asc" | "desc"). Filters: `conferences`, `positions` (hitting: C, IF, OF, UT,
        DH), `search` (player or team name). Returns every matching player unless you set `limit`.
        attrs: total, season, side, sort, and the filter values."""
        path = f"{self._div(sport, division)}/players"
        params = {"season": season, "side": side, "sort": sort, "order": order, "conferences": _csv(conferences),
                  "pos": _csv(positions), "q": search}
        pages, offset = [], 0
        while True:
            page = min(_PAGE, limit - offset) if limit else _PAGE
            data = self.get(path, **params, offset=offset, limit=page)
            pages.extend(data["players"])
            offset += len(data["players"])
            if not data["players"] or offset >= data["total"] or (limit and offset >= limit):
                break
        data["players"] = pages
        return _table(data, "players")

    def roster(self, team: str, season: Optional[int] = None, *, sport: str = "baseball",
               division: str = "d1") -> pd.DataFrame:
        """A team's players for a season with their season stats (hitting, pitching `p_*`, fielding `f_*`) and
        roster details. Before a season starts: next season's roster with each player's status.
        attrs: team, season, platform (where the stats came from), returning."""
        return _table(self.get(f"{self._div(sport, division)}/roster", team=team, season=season), "players")

    def player(self, player_id: str, *, sport: str = "baseball") -> dict:
        """One player by id (the `player_id` column of `roster` / `players`): bio, `seasons` (season lines) and
        `games` (game-by-game lines)."""
        if sport not in DIVISIONS:
            raise ValueError(f"Unknown sport {sport}")
        return _frames(self.get(f"{sport}/player/{_seg(player_id)}"))

    # ------------------------------------------------------------------ history

    def history(self, team: str, *, division: str = "d1") -> pd.DataFrame:
        """A baseball team's end-of-season rating, rank, PCR and RPI for every season on record. attrs: team."""
        return _table(self.get(f"{self._div('baseball', division)}/history", team=team), "history")

    def tournament_history(self, *, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """Past national tournament results by year (not NAIA)."""
        return _table(self.get(f"{self._div(sport, division)}/tournament-history"), "years")

    def historical_table(self) -> pd.DataFrame:
        """D1 baseball: every team's end-of-season numbers for every season since 1999."""
        return _table(self.get("baseball/d1/historical-table"), "data")

    # ------------------------------------------------------------------ lookup

    def lookup_options(self, *, sport: str = "baseball", division: str = "d1") -> dict:
        """What Lookup can search: `seasons`, `fields` by kind (game, team, bat, pit) and `scopes`."""
        return _frames(self.get(f"{self._div(sport, division)}/lookup-options"))

    def lookup_fields(self, *, sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """Every Lookup field in one table: kind (game | team | bat | pit), key (what a condition's `field`
        takes), label, group, unit."""
        fields = self.get(f"{self._div(sport, division)}/lookup-options")["fields"]
        return _records([dict(f, kind=kind) for kind, rows in fields.items() for f in rows])

    def lookup(self, season_from: int, season_to: Optional[int] = None, *, mode: str = "games", role: str = "bat",
               conditions: Optional[List[dict]] = None, match: str = "all", team: Optional[str] = None,
               sort: Optional[str] = None, desc: bool = True, limit: int = 50, offset: int = 0,
               sport: str = "baseball", division: str = "d1") -> pd.DataFrame:
        """Search games (`mode="games"`) or player games (`mode="players"`, `role` "bat" | "pit") that meet
        `conditions` (all of them with match="all", any with "any"). Each condition is a dict:
            {"kind": "team", "field": "R", "op": ">=", "value": 20, "scope": "either"}   # a team scored 20+
            {"kind": "game", "field": "innings", "op": ">=", "value": 12}                 # 12+ innings
            {"kind": "player", "field": "HR", "op": ">=", "value": 3}                     # mode="players"
        `op` is ">=", "<=" or "="; `field` is a key from lookup_fields(); team conditions need a `scope`
        (either, both, total, winner, loser, home, away, team, opp). `team` limits the search to teams whose
        name contains it. Up to 200 rows per call; page with `offset`. attrs: total, columns."""
        return _table(self.post(f"{self._div(sport, division)}/lookup", {
            "mode": mode, "role": role, "season_from": season_from, "season_to": season_to or season_from,
            "conditions": conditions or [], "match": match, "team": team, "sort": sort, "desc": desc,
            "limit": limit, "offset": offset}), "rows")

    # ------------------------------------------------------------------ tournaments

    def tournament_outlook(self, *, sport: str = "baseball", division: str = "d1") -> dict:
        """The projected national tournament field (the actual bracket once it is set): regionals (D2:
        regions), bubble lists, automatic qualifiers, multi-bid conferences, team ratings."""
        return _frames(self.get(f"{self._div(sport, division)}/tournament/outlook"))

    def tournament_regionals(self, season: Optional[int] = None) -> dict:
        """D1 baseball, once the tournament starts (default: current season): regionals, every regional / super
        regional / CWS game with its projection or result, regional winners, the CWS bracket."""
        return _frames(self.get("baseball/d1/tournament/regionals", season=season))

    def tournament_team(self, team: str, *, sport: str = "baseball", division: str = "d1") -> dict:
        """One tournament team's numbers: rating and rank, PCR, record, Q1 record, regional win probability
        (D1 baseball, D1 softball, D3 baseball)."""
        path = self._only(("baseball/d1", "softball/d1", "baseball/d3"), sport, division)
        return self.get(f"{path}/tournament/team", team=team)

    def simulate_bracket(self, outlook: Optional[dict] = None, *, seed: Optional[int] = None,
                         sport: str = "baseball", division: str = "d1") -> dict:
        """Simulate the national tournament once: regional winners through the champion. D1 baseball, D1
        softball and D3 baseball use `outlook` (from tournament_outlook(); fetched when omitted); D2 baseball
        needs no outlook. Same `seed` = same result."""
        path = self._only(("baseball/d1", "softball/d1", "baseball/d3", "baseball/d2"), sport, division)
        if path == "baseball/d2":
            body = {"seed": seed}
        else:
            outlook = outlook or self.get(f"{path}/tournament/outlook")
            regionals = outlook["regionals"]
            if isinstance(regionals, pd.DataFrame):
                regionals = regionals.to_dict("records")
            body = {"regionals": regionals, "ratings": outlook["ratings"], "seed": seed}
        return _frames(self.post(f"{path}/tournament/simulate-bracket", body))

    def d2_simulate_cary(self, teams: List[str], *, seed: Optional[int] = None) -> dict:
        """D2 baseball: simulate the 8-team finals in Cary from the 8 regional winners, best PCR first."""
        return _frames(self.post("baseball/d2/tournament/simulate-cary", {"teams": teams, "seed": seed}))

    def naia_simulate_regional(self, seeds: List[str], *, format: str = "5team", seed: Optional[int] = None) -> dict:
        """NAIA: simulate one opening-round regional (`format` "4team" or "5team", seeds in order)."""
        return _frames(self.post("baseball/naia/tournament/simulate-regional",
                                 {"seeds": seeds, "format": format, "seed": seed}))

    def naia_simulate_ws(self, teams: Optional[List[str]] = None, *, regional_picks: Optional[dict] = None,
                         seed: Optional[int] = None, n: Optional[int] = None) -> dict:
        """NAIA: simulate the World Series. With no `teams`, one winner per regional is drawn first."""
        return _frames(self.post("baseball/naia/tournament/simulate-ws",
                                 {"teams": teams or [], "regional_picks": regional_picks or {}, "seed": seed, "n": n}))

    def naia_ws_odds(self, teams: List[str]) -> dict:
        """NAIA: each team's chance to win the World Series from its 10 seeds (exact, not simulated)."""
        return _frames(self.post("baseball/naia/tournament/ws-champion-odds", {"teams": teams}))

    def conference_tournament_probs(self, conference: str, *, locked_matchups: Optional[List[dict]] = None) -> dict:
        """D1 baseball: each team's chance to reach every round of its conference tournament and win it.
        `locked_matchups` fixes results already decided: [{"winner": "LSU", "loser": "Florida"}, ...]."""
        if locked_matchups:
            return _frames(self.post("baseball/d1/conference-tournament/probs-with-picks",
                                     {"conference": conference, "locked_matchups": locked_matchups}))
        return _frames(self.post("baseball/d1/conference-tournament/probs", {"conference": conference}))
