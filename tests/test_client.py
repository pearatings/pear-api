"""Offline tests: no network, the HTTP session is replaced by a fake that records requests."""
import json

import pandas as pd
import pytest

from pearatings import AuthenticationError, NotFoundError, Pear, RateLimitError, TierError


class FakeResponse:
    def __init__(self, status=200, body=None, content=b""):
        self.status_code, self._body, self.content, self.headers = status, body, content, {}
        self.text, self.reason = json.dumps(body), "reason"

    def json(self):
        if self._body is None:
            raise ValueError
        return self._body


class FakeSession:
    def __init__(self, response):
        self.response, self.calls, self.headers = response, [], {}

    def request(self, method, url, params=None, json=None, timeout=None):
        self.calls.append({"method": method, "url": url, "params": params, "json": json})
        return self.response


def client(response):
    pear = Pear(api_key="k", base_url="http://api.test/")
    pear.session = FakeSession(response)
    return pear


def test_key_required(monkeypatch):
    monkeypatch.delenv("PEAR_API_KEY", raising=False)
    with pytest.raises(AuthenticationError):
        Pear()
    monkeypatch.setenv("PEAR_API_KEY", "from-env")
    assert Pear().session.headers["X-API-Key"] == "from-env"


def test_base_url_from_env(monkeypatch):
    monkeypatch.setenv("PEAR_API_URL", "http://127.0.0.1:8001/")
    assert Pear(api_key="k").base_url == "http://127.0.0.1:8001"


def test_table_endpoint_returns_dataframe_with_attrs():
    pear = client(FakeResponse(body={"teams": [{"Team": "LSU", "power_rating": 6.1}], "date": "May 1", "count": 1}))
    df = pear.ratings(sport="softball", division="d2")
    assert isinstance(df, pd.DataFrame) and df.loc[0, "Team"] == "LSU"
    assert df.attrs == {"date": "May 1", "count": 1}
    assert pear.session.calls[0]["url"] == "http://api.test/v1/softball/d2/ratings"


def test_none_params_are_dropped_and_names_are_escaped():
    pear = client(FakeResponse(body={"team": {}, "upcoming_games": [], "recent_games": []}))
    pear.team("Texas A&M")
    call = pear.session.calls[0]
    assert call["url"].endswith("/v1/baseball/d1/team/Texas%20A%26M")
    pear.games(date=None, team="LSU")
    assert pear.session.calls[1]["params"] == {"team": "LSU"}
    pear.games(__import__("datetime").date(2026, 4, 18))
    assert pear.session.calls[2]["params"] == {"date": "2026-04-18", "season": 2026}


def test_nested_records_become_flat_frames():
    body = {"schedule": [{"Opponent": "UNO", "record": {"wins": 3}}], "metrics": {"pcr": 4}}
    out = client(FakeResponse(body=body)).team_schedule("LSU")
    assert list(out["schedule"].columns) == ["Opponent", "record.wins"] and out["metrics"] == {"pcr": 4}


def test_players_pages_until_total():
    pages = [{"total": 3, "players": [{"n": 1}, {"n": 2}]}, {"total": 3, "players": [{"n": 3}]}]

    class Paging(FakeSession):
        def request(self, *a, **k):
            super().request(*a, **k)
            return FakeResponse(body=dict(pages[len(self.calls) - 1]))

    pear = Pear(api_key="k", base_url="http://api.test")
    pear.session = Paging(None)
    df = pear.players(season=2026, conferences=["SEC", "ACC"])
    assert df["n"].tolist() == [1, 2, 3]
    assert pear.session.calls[0]["params"]["conferences"] == "SEC,ACC"
    assert pear.session.calls[1]["params"]["offset"] == 2


def test_records_one_row_per_team():
    body = {"records": {"LSU": {"wins": 5, "losses": 1}, "UNO": {"wins": 2, "losses": 4}}}
    df = client(FakeResponse(body=body)).records()
    assert df.columns[0] == "Team" and df.set_index("Team").loc["UNO", "losses"] == 4


@pytest.mark.parametrize("status,error", [(401, AuthenticationError), (403, AuthenticationError), (404, NotFoundError),
                                          (429, RateLimitError)])
def test_http_errors(status, error):
    with pytest.raises(error) as e:
        client(FakeResponse(status=status, body={"detail": "nope"})).ratings()
    assert e.value.status_code == status and "nope" in str(e.value)


def test_bad_division_fails_before_any_request():
    pear = client(FakeResponse(body={}))
    with pytest.raises(ValueError):
        pear.ratings(sport="softball", division="naia")
    with pytest.raises(ValueError):
        pear.tournament_team("X", division="d2")
    assert pear.session.calls == []


def test_logo_returns_bytes():
    assert client(FakeResponse(content=b"\x89PNG")).logo("LSU") == b"\x89PNG"


def test_rate_limit_carries_retry_after():
    resp = FakeResponse(status=429, body={"detail": "Rate limit: 60 requests per minute"})
    resp.headers = {"Retry-After": "17"}
    with pytest.raises(RateLimitError) as e:
        client(resp).ratings()
    assert e.value.retry_after == 17


def test_account_and_portal():
    pear = client(FakeResponse(body={"url": "https://billing.stripe.com/p/session/x"}))
    assert pear.billing_portal(open_browser=False) == "https://billing.stripe.com/p/session/x"
    assert pear.session.calls[0]["method"] == "POST" and pear.session.calls[0]["url"].endswith("/v1/account/portal")


def test_ratings_on_a_date():
    import datetime as dt
    pear = client(FakeResponse(body={"teams": [{"Team": "LSU"}], "date": "April 18, 2027", "count": 1}))
    pear.ratings("2027-04-18")
    pear.ratings(dt.date(2027, 4, 18), sport="softball")
    assert [c["url"] for c in pear.session.calls] == ["http://api.test/v1/baseball/d1/ratings/2027-04-18",
                                                      "http://api.test/v1/softball/d1/ratings/2027-04-18"]


GAME = {"game_id": "S2-2026-00001", "date": "2026-03-01", "home": {"team": "A", "score": 3}, "away": {"team": "B"},
        "teams": {"away": {"side": "away", "R": 1}, "home": {"side": "home", "R": 3}},
        "batting": {"away": [{"side": "away", "player": "x"}], "home": [{"side": "home", "player": "y"}]},
        "pitching": {"away": [{"side": "away"}], "home": []}, "plays": [{"seq": 1}, {"seq": 2}]}


def test_box_score_division_comes_from_the_game_id():
    pear = client(FakeResponse(body=GAME))
    box = pear.box_score("S2-2026-00001")
    assert pear.session.calls[0]["url"] == "http://api.test/v1/softball/d2/box-score/S2-2026-00001"
    assert box["game"]["home.team"] == "A" and len(box["batting"]) == 2 and len(box["teams"]) == 2
    assert set(box["batting"]["game_id"]) == {"S2-2026-00001"} and len(box["plays"]) == 2
    with pytest.raises(ValueError):
        pear.box_score("2026-00001")


def test_play_by_play_and_team_season():
    pear = client(FakeResponse(body={k: v for k, v in GAME.items() if k not in ("batting", "pitching", "teams")}))
    plays = pear.play_by_play("B1-2026-00001")
    assert list(plays["seq"]) == [1, 2] and plays.attrs["home"]["team"] == "A"
    pear = client(FakeResponse(body={"team": "LSU", "season": 2026, "count": 2,
                                     "games": [GAME, dict(GAME, game_id="S2-2026-00002")]}))
    season = pear.team_games("LSU", 2026, sport="softball", division="d2")
    assert pear.session.calls[0]["url"] == "http://api.test/v1/softball/d2/team/LSU/games/2026"
    assert len(season["games"]) == 2 and len(season["plays"]) == 4 and season["games"].attrs["season"] == 2026
    plays = pear.team_play_by_play("LSU")
    assert pear.session.calls[-1]["url"] == "http://api.test/v1/baseball/d1/team/LSU/play-by-play"
    assert set(plays["game_id"]) == {"S2-2026-00001", "S2-2026-00002"} and len(plays.attrs["games"]) == 2


def test_tier_error_names_the_tier():
    resp = FakeResponse(status=403, body={"detail": "This endpoint needs the Pro tier or higher; this key is on Free."})
    resp.headers = {"X-Pear-Required-Tier": "pro"}
    with pytest.raises(TierError) as e:
        client(resp).lookup(2026)
    assert e.value.required_tier == "pro" and e.value.status_code == 403 and "Pro tier" in str(e.value)
    with pytest.raises(AuthenticationError):   # a lapsed or revoked key: no tier header
        client(FakeResponse(status=403, body={"detail": "not active"})).ratings()


def test_parks_coaches_and_daily_ratings_urls():
    import datetime as dt
    pear = client(FakeResponse(body={"teams": [{"Team": "LSU"}], "parks": [], "coaches": [], "head_coaches": [],
                                     "staffs": [], "days": [], "date": "2024-04-15", "season": 2024}))
    pear.park_factors(2025, sport="softball", division="d2")
    pear.twitter(division="naia")
    pear.cities()
    pear.schedule(2026, division="d3")
    pear.team_stats(2025, sport="softball")
    pear.coaches()
    pear.head_coaches(2026, team="LSU")
    pear.staffs(team="Texas A&M")
    df = pear.daily_ratings(dt.date(2024, 4, 15))
    pear.team_daily_ratings("Texas A&M", 2024)
    calls = [(c["url"].removeprefix("http://api.test/v1/"), c["params"]) for c in pear.session.calls]
    assert calls == [("softball/d2/park-factors", {"season": 2025}), ("baseball/naia/twitter", {}),
                     ("baseball/d1/cities", {}), ("baseball/d3/schedule", {"season": 2026}),
                     ("softball/d1/team-stats", {"season": 2025}), ("baseball/d1/coaches", {}),
                     ("baseball/d1/head-coaches", {"season": 2026, "team": "LSU"}),
                     ("baseball/d1/staffs", {"team": "Texas A&M"}), ("baseball/d1/daily-ratings/2024-04-15", {}),
                     ("baseball/d1/team/Texas%20A%26M/daily-ratings", {"season": 2024})]
    assert df.loc[0, "Team"] == "LSU" and df.attrs["date"] == "2024-04-15"
    with pytest.raises(ValueError):
        pear.twitter(division="d4")


def test_more_endpoints_urls():
    pear = client(FakeResponse(body={"teams": [], "conferences": [], "games": [], "tenures": [], "players": [],
                                     "matrix": []}))
    pear.team_info(sport="softball", division="d3")
    pear.conference_ratings(2025)
    pear.coach_tenures("C000001")
    pear.player_search("dawson park", sport="softball")
    pear.returning()
    pear.portal(team="LSU")
    pear.team_game_log("LSU", 2026)
    pear.run_expectancy(2026, division="d2")
    calls = [(c["url"].removeprefix("http://api.test/v1/"), c["params"]) for c in pear.session.calls]
    assert calls == [("softball/d3/team-info", {}), ("baseball/d1/conference-ratings", {"season": 2025}),
                     ("baseball/d1/coach-tenures", {"coach_id": "C000001"}),
                     ("softball/players/search", {"q": "dawson park"}), ("baseball/d1/returning", {}),
                     ("baseball/d1/portal", {"team": "LSU"}), ("baseball/d1/team/LSU/game-log", {"season": 2026}),
                     ("baseball/d2/run-expectancy", {"season": 2026})]
