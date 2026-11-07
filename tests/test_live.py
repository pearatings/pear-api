"""Calls every client method against a running API. Skipped unless PEAR_API_KEY and PEAR_API_URL are set:
    PEAR_API_KEY='...' PEAR_API_URL=http://127.0.0.1:8001 pytest -m live
Uses 2026 data, so some calls need that season on the server."""
import os

import pandas as pd
import pytest

from pearatings import APIError, NotFoundError, Pear

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(not (os.environ.get("PEAR_API_KEY") and os.environ.get("PEAR_API_URL")),
                                 reason="needs PEAR_API_KEY and PEAR_API_URL")]


@pytest.fixture(scope="module")
def pear():
    return Pear()


def frame(df, min_rows=1):
    assert isinstance(df, pd.DataFrame) and len(df) >= min_rows, df
    return df


def test_teams_and_ratings(pear):
    frame(pear.ratings(), 250)
    frame(pear.ratings(sport="softball", division="d3"), 100)
    assert frame(pear.preseason(2027)).iloc[0]["Team"]
    frame(pear.preseason(2005))
    with pytest.raises(NotFoundError):
        pear.preseason(1990)
    frame(pear.stats(2026), 250)
    frame(pear.stats(2026, sport="baseball", division="naia"))
    teams = pear.teams()
    assert "LSU" in teams
    assert isinstance(pear.team("LSU")["team"], dict)
    assert pear.team_conferences()["LSU"] == "SEC"
    assert "SEC" in pear.conferences()
    frame(pear.conference_standings("SEC"))
    assert isinstance(pear.pcr_ranks()["LSU"], int)
    frame(pear.combined_ratings(), 1000)
    assert pear.logo("LSU").startswith(b"\x89PNG")
    assert pear.logo("Oklahoma", sport="softball", variant="dark").startswith(b"\x89PNG")
    assert pear.conference_logo("SEC").startswith(b"\x89PNG")


def test_projections(pear):
    games = frame(pear.games("2026-04-18"), 50)
    assert {"home_team", "away_team", "home_win_prob"} <= set(games.columns)
    frame(pear.games(conference="SEC"), 0)
    m = pear.matchup("LSU", "Florida")
    assert 0 < m["home_win_prob"] < 100   # percent here; games() uses 0-1
    s = pear.team_schedule("LSU", 2026)
    frame(s["schedule"], 50)
    w = pear.simulate_wins("LSU", rating=7.0)
    frame(w["distribution"])
    frame(pear.season_projection(division="d2")["projected_pcr"]["teams"], 100)
    assert {"team", "conference"} <= set(frame(pear.conference_projections(), 250).columns)


def test_players(pear):
    hitters = frame(pear.players(2026, limit=250), 250)
    assert len(hitters) == 250 and hitters.attrs["total"] > 250
    frame(pear.players(2026, side="pitching", conferences=["SEC"], sport="softball"))
    roster = frame(pear.roster("LSU", 2026), 20)
    p = pear.player(roster["player_id"].dropna().iloc[0])
    frame(p["games"])


def test_history_and_lookup(pear):
    frame(pear.history("LSU"), 20)
    frame(pear.tournament_history())
    frame(pear.historical_table(), 5000)
    assert {"kind", "key"} <= set(frame(pear.lookup_fields()).columns)
    assert 2026 in pear.lookup_options()["seasons"]
    rows = frame(pear.lookup(2026, conditions=[{"kind": "team", "field": "R", "op": ">=", "value": 25,
                                                "scope": "either"}]))
    assert rows.attrs["total"] >= len(rows)
    frame(pear.lookup(2026, mode="players", team="LSU", limit=10))


def test_tournaments(pear):
    outlook = pear.tournament_outlook()
    frame(outlook["regionals"], 16)
    assert pear.simulate_bracket(outlook, seed=1)["regional_winners"]
    assert pear.simulate_bracket(sport="softball", seed=1)["regional_winners"]
    assert pear.simulate_bracket(division="d3", seed=1)["regional_winners"]
    assert pear.simulate_bracket(division="d2", seed=1)["regions"]
    frame(pear.tournament_outlook(division="d2")["regions"], 8)
    assert pear.tournament_team("LSU")["team"] == "LSU"
    frame(pear.tournament_regionals(2026)["games"], 100)
    frame(pear.conference_tournament_probs("SEC")["teams"])
    frame(pear.tournament_history(sport="softball"))
    with pytest.raises(APIError):   # 503 until NAIA's bracket exists
        pear.tournament_outlook(division="naia")
