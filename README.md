# pearatings

Python client for the [PEARatings](https://pearatings.com) data API: college baseball (D1, D2, D3, NAIA)
and softball (D1, D2, D3) ratings, projections, player stats, history, Lookup and tournament simulations.
Tables come back as pandas DataFrames.

## Install

```bash
pip install pearatings
```

## Get a key

Pick a tier at **https://api.pearatings.com/billing**. Your key is shown once: copy it.

| Tier | Price | API calls per month | Per minute |
|---|---|---|---|
| Free | $0 | 1,000 | 10 |
| Plus | $4.99/month | 10,000 | 60 |
| Pro | $9.99/month | 25,000 | 120 |
| Max | $19.99/month | 75,000 | 120 |

Every request is one call; `players()` fetches a full leaderboard 200 rows per call, and a team's whole season of
box scores or play-by-play is one call. Calls reset on the 1st
(UTC). `pear.account()` shows your tier and calls used this month; `pear.billing_portal()` changes tier or cancels.

## Set your key

```bash
export PEAR_API_KEY='your-key'        # single quotes if the key has a ! in it
```
or pass it: `Pear(api_key="your-key")`.

## Quick start

```python
from pearatings import Pear

pear = Pear()

ratings = pear.ratings()                               # D1 baseball, current
ratings.attrs["date"]                                  # when the ratings were updated
pear.ratings("2027-04-18")                             # as they stood that day (current season)
pear.ratings(sport="softball", division="d2")

pear.preseason(2027)                                   # preseason ratings
pear.stats(2025)                                       # team stats + end-of-season ratings for 2025

pear.games("2026-04-18")                               # that day's games with PEAR's line and win probability
pear.matchup("LSU", "Florida", neutral=True)           # any two teams
pear.team_schedule("LSU", 2026)["schedule"]            # every game of a team's season

pear.players(2026)                                     # full hitting leaderboard (every page)
pear.players(2026, side="pitching", conferences=["SEC"], limit=50)
roster = pear.roster("LSU", 2026)
pear.player(roster["player_id"].iloc[0])["games"]      # one player's game-by-game lines

game_id = pear.games("2026-04-18")["game_id"].iloc[0]  # every game has a PEAR game id
pear.box_score(game_id)["batting"]                     # one game's box score (game, batting, pitching, teams)
pear.play_by_play(game_id)                             # one game's plays, with base-out state and win probability
pear.game(game_id)                                     # both
season = pear.team_box_scores("LSU", 2026)             # a team's whole season: games, batting, pitching, teams
pear.team_play_by_play("LSU", 2026)                    # every play of a team's season

pear.history("LSU")                                    # end-of-season numbers, every season
pear.tournament_outlook()                              # projected NCAA field
pear.simulate_bracket(seed=7)                          # one simulated tournament

open("lsu.png", "wb").write(pear.logo("LSU"))
```

Every method takes keyword-only `sport` (`"baseball"` default, or `"softball"`) and `division` (`"d1"`
default, `"d2"`, `"d3"`, `"naia"`) unless it exists for one division only, or takes a game id (its sport and division
come from the id). Use `help(pear.games)` for any
method's details.

## What comes back

- **One table** → a `DataFrame`; the rest of the response (data date, season, totals) is in `df.attrs`.
- **Anything else** → a `dict`, where every list of records is a `DataFrame`.
- Nested fields are flattened to dotted columns: `record.wins`, `stats.PA`.
- `pear.get("baseball/d1/ratings")` / `pear.post(path, body)` return the raw JSON of any endpoint.

## Methods

| Area | Methods |
|---|---|
| Your account | `account`, `billing_portal` |
| Teams and ratings | `ratings`, `preseason`, `stats`, `teams`, `team`, `team_conferences`, `conferences`, `conference_standings`, `records`, `pcr_ranks`, `combined_ratings`, `logo`, `conference_logo` |
| Projections | `games`, `matchup`, `team_schedule`, `simulate_wins`, `season_projection`, `conference_projections` |
| Players | `players`, `roster`, `player` |
| Box scores and play-by-play | `box_score`, `play_by_play`, `game`, `team_box_scores`, `team_play_by_play`, `team_games` |
| History | `history`, `tournament_history`, `historical_table` |
| Lookup | `lookup_fields`, `lookup_options`, `lookup` |
| Tournaments | `tournament_outlook`, `tournament_regionals`, `tournament_team`, `simulate_bracket`, `conference_tournament_probs`, `d2_simulate_cary`, `naia_simulate_regional`, `naia_simulate_ws`, `naia_ws_odds` |

## Lookup

Find games or player games that meet conditions. Field keys come from `pear.lookup_fields()`.

```python
pear.lookup_fields()                                   # kind, key, label, group, unit

# games where a team scored 25+ in 2026
pear.lookup(2026, conditions=[{"kind": "team", "field": "R", "op": ">=", "value": 25, "scope": "either"}])

# 3-homer games, 2021-2026
pear.lookup(2021, 2026, mode="players", role="bat",
            conditions=[{"kind": "player", "field": "HR", "op": ">=", "value": 3}], limit=200)
```
Up to 200 rows per call; `df.attrs["total"]` is the full count, page with `offset=`.

## Errors

All errors subclass `pearatings.PearError` and carry `.status_code`:
`AuthenticationError` (bad or missing key, or a lapsed subscription), `NotFoundError` (unknown team / season),
`InvalidRequestError` (bad parameters), `RateLimitError` (over your tier's limit; `.retry_after` says how many
seconds to wait), `APIError` (anything else, e.g. data not available out of season).

## Development

```bash
pip install -e '.[test]'
pytest                                                    # offline tests
PEAR_API_KEY='...' PEAR_API_URL=http://127.0.0.1:8001 pytest -m live   # every method against a running API
```
`PEAR_API_URL` (or `Pear(base_url=...)`) points the client at another server; the default is
`https://api.pearatings.com`.
