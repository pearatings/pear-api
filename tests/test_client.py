"""Offline tests: no network, the HTTP session is replaced by a fake that records requests."""
import json

import pandas as pd
import pytest

from pearatings import AuthenticationError, NotFoundError, Pear, RateLimitError


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
