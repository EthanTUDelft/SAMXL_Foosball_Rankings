"""Analysis of every foosball game played at SAMXL.

Reads all Results/*.csv files (named DDMMYY), replays them in chronological
order and writes the analysed data to Analysis_by_claude/output/:

    games.csv        every valid game, in order, with pre-game Elo and expectations
    players.csv      per-player summary stats
    partners.csv     per-pair stats (as teammates)
    sessions.csv     per-session stats
    rejected.csv     rows that could not be used (same player listed twice, ...)
    analysis.json    everything above, consumed by the dashboard
    dashboard.html   the plots (built from dashboard_template.html)

Run from the repo root:  python3 Analysis_by_claude/analyze.py
"""
import csv
import json
import math
import os
from collections import defaultdict
from datetime import date
from itertools import combinations

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS_DIR = os.path.join(REPO, 'Results')
OUT_DIR = os.path.join(HERE, 'output')

# Same Elo system as the repo's main.py, replayed from scratch for everyone.
START_ELO = 1000
K = 32
SCALE = 500


def session_date(filename):
    """'231026.csv' -> date(2026, 10, 23)."""
    stem = os.path.splitext(filename)[0]
    return date(2000 + int(stem[4:6]), int(stem[2:4]), int(stem[0:2]))


def load_games():
    games, rejected = [], []
    files = sorted((f for f in os.listdir(RESULTS_DIR) if f.endswith('.csv')), key=session_date)
    for filename in files:
        day = session_date(filename).isoformat()
        with open(os.path.join(RESULTS_DIR, filename), newline='', encoding='utf-8') as fh:
            for row_no, row in enumerate(csv.reader(fh), start=1):
                row = [c.strip() for c in row]
                if not row or not row[0] or row[0] == 'Player 1-1':
                    continue
                p = row[:4]
                try:
                    s1, s2 = int(row[4]), int(row[5])
                except (IndexError, ValueError):
                    rejected.append({'date': day, 'file': filename, 'row': row_no, 'raw': ','.join(row), 'reason': 'bad score'})
                    continue
                if len(set(p)) != 4:
                    rejected.append({'date': day, 'file': filename, 'row': row_no, 'raw': ','.join(row), 'reason': 'player listed twice'})
                    continue
                if s1 == s2:
                    rejected.append({'date': day, 'file': filename, 'row': row_no, 'raw': ','.join(row), 'reason': 'draw'})
                    continue
                games.append({'date': day, 'team1': p[:2], 'team2': p[2:], 's1': s1, 's2': s2})
    for i, g in enumerate(games):
        g['id'] = i + 1
    return games, rejected


def replay_elo(games):
    """Apply main.py's update rule game by game; record history per player."""
    elo = defaultdict(lambda: START_ELO)
    history = defaultdict(list)  # player -> [[game_id, rating], ...]
    for g in games:
        for pl in g['team1'] + g['team2']:
            if pl not in history:
                history[pl].append([g['id'] - 1, START_ELO])
        r1 = sum(elo[pl] for pl in g['team1']) / 2
        r2 = sum(elo[pl] for pl in g['team2']) / 2
        e1 = 1 / (1 + 10 ** ((r2 - r1) / SCALE))
        margin = 1 + 0.25 * math.log(abs(g['s1'] - g['s2']))
        d1 = K * ((1 if g['s1'] > g['s2'] else 0) - e1) * margin
        g.update(r1=round(r1, 1), r2=round(r2, 1), e1=round(e1, 4), delta1=round(d1, 2))
        # An upset = the team the model rated as underdog won (even games don't count).
        g['upset'] = e1 != 0.5 and (e1 < 0.5) == (g['s1'] > g['s2'])
        for pl in g['team1']:
            elo[pl] += d1
            history[pl].append([g['id'], round(elo[pl], 1)])
        for pl in g['team2']:
            elo[pl] -= d1
            history[pl].append([g['id'], round(elo[pl], 1)])
    return dict(elo), dict(history)


def player_stats(games, elo, history):
    st = defaultdict(lambda: defaultdict(int))
    for g in games:
        sides = [(g['team1'], g['s1'], g['s2']), (g['team2'], g['s2'], g['s1'])]
        for team, gf, ga in sides:
            for pl in team:
                s = st[pl]
                s['games'] += 1
                s['wins'] += gf > ga
                s['goals_for'] += gf
                s['goals_against'] += ga
                s['shutouts_for'] += ga == 0
                s['close_games'] += abs(gf - ga) == 1
                s['close_wins'] += gf - ga == 1
                s.setdefault('sessions', set()).add(g['date'])
    rows = []
    for pl, s in st.items():
        ratings = [r for _, r in history[pl]]
        rows.append({
            'player': pl,
            'games': s['games'],
            'wins': s['wins'],
            'losses': s['games'] - s['wins'],
            'win_pct': round(100 * s['wins'] / s['games'], 1),
            'goals_for': s['goals_for'],
            'goals_against': s['goals_against'],
            'goal_diff_per_game': round((s['goals_for'] - s['goals_against']) / s['games'], 2),
            'shutouts_for': s['shutouts_for'],
            'close_games': s['close_games'],
            'close_wins': s['close_wins'],
            'sessions': len(s['sessions']),
            'elo': round(elo[pl]),
            'peak_elo': round(max(ratings)),
            'low_elo': round(min(ratings)),
        })
    rows.sort(key=lambda r: -r['elo'])
    return rows


def partner_stats(games):
    st = defaultdict(lambda: [0, 0, 0])  # games, wins, goal diff
    for g in games:
        for team, won, gd in ((g['team1'], g['s1'] > g['s2'], g['s1'] - g['s2']),
                              (g['team2'], g['s2'] > g['s1'], g['s2'] - g['s1'])):
            key = tuple(sorted(team))
            st[key][0] += 1
            st[key][1] += won
            st[key][2] += gd
    rows = [{'a': a, 'b': b, 'games': n, 'wins': w, 'win_pct': round(100 * w / n, 1),
             'goal_diff_per_game': round(d / n, 2)} for (a, b), (n, w, d) in st.items()]
    rows.sort(key=lambda r: (-r['games'], -r['win_pct']))
    return rows


def session_stats(games):
    by_day = defaultdict(list)
    for g in games:
        by_day[g['date']].append(g)
    rows = []
    for day in sorted(by_day):
        gs = by_day[day]
        players = {pl for g in gs for pl in g['team1'] + g['team2']}
        rows.append({
            'date': day,
            'games': len(gs),
            'players': len(players),
            'avg_margin': round(sum(abs(g['s1'] - g['s2']) for g in gs) / len(gs), 2),
            'upsets': sum(g['upset'] for g in gs),
        })
    return rows


def write_csv(name, rows, fields=None):
    if not rows:
        return
    fields = fields or list(rows[0].keys())
    with open(os.path.join(OUT_DIR, name), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    games, rejected = load_games()
    elo, history = replay_elo(games)
    players = player_stats(games, elo, history)
    partners = partner_stats(games)
    sessions = session_stats(games)

    # Losing team's score: how close games usually are (winner always reaches 10).
    loser_scores = [0] * 10
    for g in games:
        loser_scores[min(g['s1'], g['s2'])] += 1

    # Calibration: does the Elo favourite win as often as the model predicts?
    bins = defaultdict(lambda: [0, 0, 0.0])  # games, favourite wins, summed prob
    for g in games:
        fav_p = max(g['e1'], 1 - g['e1'])
        if fav_p == 0.5:
            continue
        b = min(int((fav_p - 0.5) * 20), 4)  # 50-55, 55-60, ..., 70+
        bins[b][0] += 1
        bins[b][1] += not g['upset']
        bins[b][2] += fav_p
    calibration = [{
        'bin': f"{50 + 5 * b}–{55 + 5 * b}%" if b < 4 else '70%+',
        'games': n, 'predicted': round(100 * p / n, 1), 'actual': round(100 * w / n, 1),
    } for b, (n, w, p) in sorted(bins.items())]

    flat_games = [{
        'id': g['id'], 'date': g['date'],
        'team1_p1': g['team1'][0], 'team1_p2': g['team1'][1],
        'team2_p1': g['team2'][0], 'team2_p2': g['team2'][1],
        'score1': g['s1'], 'score2': g['s2'],
        'team1_elo': g['r1'], 'team2_elo': g['r2'],
        'team1_win_prob': g['e1'], 'team1_elo_change': g['delta1'], 'upset': g['upset'],
    } for g in games]

    write_csv('games.csv', flat_games)
    write_csv('players.csv', players)
    write_csv('partners.csv', partners)
    write_csv('sessions.csv', sessions)
    write_csv('rejected.csv', rejected, ['date', 'file', 'row', 'raw', 'reason'])

    data = {
        'summary': {
            'games': len(games),
            'sessions': len(sessions),
            'players': len(players),
            'rejected': len(rejected),
            'upsets': sum(g['upset'] for g in games),
            'first': sessions[0]['date'],
            'last': sessions[-1]['date'],
            'elo': {'start': START_ELO, 'k': K, 'scale': SCALE},
        },
        'players': players,
        'partners': partners,
        'sessions': sessions,
        'loser_scores': loser_scores,
        'calibration': calibration,
        'history': history,
        'game_dates': [g['date'] for g in games],
        'rejected': rejected,
    }
    with open(os.path.join(OUT_DIR, 'analysis.json'), 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)

    with open(os.path.join(HERE, 'dashboard_template.html'), encoding='utf-8') as fh:
        template = fh.read()
    payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    with open(os.path.join(OUT_DIR, 'dashboard.html'), 'w', encoding='utf-8') as fh:
        fh.write(template.replace('/*__DATA__*/null', payload))

    print(f"{len(games)} games over {len(sessions)} sessions, {len(players)} players, "
          f"{len(rejected)} rows rejected")
    print(f"{'player':<12} {'games':>5} {'win%':>6} {'GD/g':>6} {'elo':>5}")
    for p in players:
        print(f"{p['player']:<12} {p['games']:>5} {p['win_pct']:>6} {p['goal_diff_per_game']:>6} {p['elo']:>5}")


if __name__ == '__main__':
    main()
