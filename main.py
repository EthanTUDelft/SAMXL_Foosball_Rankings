import math as m
import csv
import glob
import sys

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

def add_player(players, name, elo):
    players[name] = elo
    return players


def save_ratings(players, filename):
    with open(filename, 'w') as file:
        for item in players:
            file.write(str(item) + ',' + str(int(players[item])) + '\n')


def load_rankings(filename):
    players = {}
    with open(filename, 'r') as file:
        for line in file:
            line = line.strip('\n')
            ranks = line.split(',')
            players[ranks[0]] = int(ranks[1])
    return players


def load_results(filename):
    results = []
    with open(filename, 'r') as file:
        for line in file:
            line = line.split(',')
            if line[0] != 'Player 1-1':
                results.append(line)
    return results


def calculate_elo_change(players, result):
    k = 32

    p1 = result[0]
    p2 = result[1]
    p3 = result[2]
    p4 = result[3]
    T1_score = int(result[4])
    T2_score = int(result[5])
    T1_R = (players[p1] + players[p2])/2
    T2_R = (players[p3] + players[p4])/2

    T1_E = 1/(1+10**((T2_R - T1_R)/500))
    T2_E = 1 - T1_E
    print(T1_E)

    performance_diff = 1 + 0.25*m.log(abs(T1_score-T2_score))

    if T1_score > T2_score:
        T1_delta = k*(1-T1_E)*performance_diff
        T2_delta = k*(0-T2_E)*performance_diff

    else:
        T1_delta = k*(0-T1_E)*performance_diff
        T2_delta = k*(1-T2_E)*performance_diff

    players[p1] += T1_delta
    players[p2] += T1_delta
    players[p3] += T2_delta
    players[p4] += T2_delta


def update_elo(ratings_file, results_file):
    players = load_rankings(ratings_file)
    results = load_results(results_file)

    for result in results:
        calculate_elo_change(players, result)
        print(players)
    return players


def count_games(results_dir='Results'):
    games = {}
    for filename in glob.glob(results_dir + '/*.csv'):
        with open(filename, 'r') as file:
            for row in list(csv.reader(file))[1:]:
                if len(row) >= 6:
                    for name in row[:4]:
                        games[name] = games.get(name, 0) + 1
    return games


def shrunk_rating(elo, games, prior_games=100, start=1000):
    # Ratings from few games are pulled toward the starting rating,
    # so a high Elo only counts fully once it is backed by enough games.
    return start + (elo - start) * games / (games + prior_games)


def print_leaderboard(ratings_file='ratings.txt', results_dir='Results'):
    players = load_rankings(ratings_file)
    games = count_games(results_dir)
    board = sorted(players, key=lambda p: -shrunk_rating(players[p], games.get(p, 0)))
    for i, p in enumerate(board, 1):
        print(i, p, round(shrunk_rating(players[p], games.get(p, 0))), players[p], games.get(p, 0))


if __name__ == '__main__':
    if '--leaderboard' in sys.argv:
        print_leaderboard()
        sys.exit()
    ratings_file = 'ratings.txt'
    results_file = 'Results/15102026.csv'
    players = update_elo(ratings_file, results_file)
    save_ratings(players, ratings_file)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/

