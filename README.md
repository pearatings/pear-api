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

| Tier | Price | API calls per month | Per minute | Adds |
|---|---|---|---|---|
| Free | $0 | 1,000 | 10 | Current ratings, preseason ratings and PEAR team numbers for every season (TSR, PCR, RQI, SOS, AdjO / AdjD, ...); teams, conferences, standings, records, PCR ranks; games and PEAR's lines for any date, a whole season's games in one call, matchups, team schedules; team stats from NCAA.com (2008 on); conference projections and conference strength; team and tournament history, the D1 historical table; team info (conference, colors, city, X account, logos) |
| Plus | $4.99/month | 10,000 | 60 | Everything in Free, plus ratings on any day of the current season; player leaderboards, rosters, player pages; tournament outlook, regionals, tournament team detail; player search; D1 baseball coaches with records and tenures; D1 returning production and transfers; park factors |
| Pro | $9.99/month | 25,000 | 120 | Everything in Plus, plus box scores and play-by-play (single games or a team's whole season, with in-game win probability and postgame win expectancy); starter, reliever, weekend and midweek staff values; team game logs (xR, win expectancy, Excitement); run expectancy tables; Lookup; simulations (rest-of-season wins, season projection, brackets, conference tournaments) |
| Max | $19.99/month | 75,000 | 120 | Everything in Pro, plus D1 baseball ratings day by day for every finished season since 2016 (TSR, RQI, SOS, RemSOS, PCR) |

Each method's `help()` names its tier when it needs more than Free. Calling one on a lower tier raises `TierError`.

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
pear.stats(2025)                                       # PEAR team numbers, end of season 2025
pear.team_stats(2025)                                  # NCAA.com team stats (AB, H, ERA, ...), end of season 2025

pear.games("2026-04-18")                               # that day's games with PEAR's line and win probability
pear.schedule(2026)                                    # every game of the season in one call
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
pear.daily_ratings("2024-04-15")                       # D1 TSR, RQI, SOS, RemSOS, PCR that day (Max)
pear.team_daily_ratings("LSU", 2024)                   # one team's 2024 day by day (Max)
pear.park_factors(2026)                                # each home park's run effect (Plus)
pear.head_coaches(2026, team="LSU")                    # D1 baseball coaches with records (Plus)
pear.player_search("dawson park")                      # player ids across every season (Plus)
pear.team_game_log("LSU", 2026)                        # per game xR, win expectancy, Excitement (Pro)
pear.team_info()                                       # conference, colors, city, X account, logo
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
| Teams and ratings | `ratings`, `preseason`, `stats`, `team_stats`, `teams`, `team`, `team_info`, `team_conferences`, `conferences`, `conference_standings`, `conference_ratings`, `records`, `pcr_ranks`, `combined_ratings`, `logo`, `conference_logo`, `twitter`, `cities`, `park_factors` |
| Coaches (D1 baseball) | `coaches`, `head_coaches`, `coach_tenures`, `staffs` |
| Projections | `games`, `schedule`, `matchup`, `team_schedule`, `simulate_wins`, `season_projection`, `conference_projections` |
| Players | `players`, `roster`, `player`, `player_search`, `returning`, `portal` |
| Box scores and play-by-play | `box_score`, `play_by_play`, `game`, `team_box_scores`, `team_play_by_play`, `team_games`, `team_game_log`, `run_expectancy` |
| History | `history`, `tournament_history`, `historical_table`, `daily_ratings`, `team_daily_ratings` |
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
seconds to wait), `TierError` (the method needs a higher tier; `.required_tier` names it: `"plus"`, `"pro"` or
`"max"`), `APIError` (anything else, e.g. data not available out of season).
