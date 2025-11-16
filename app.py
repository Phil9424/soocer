from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__,
            static_folder='static',
            static_url_path='/static')
app.secret_key = 'football_manager_secret_key_2024'

# Простые данные для тестирования
TEAMS_DATA = [
    {'name': 'Arsenal', 'logo': '/static/logos/arsenal.png'},
    {'name': 'Chelsea', 'logo': '/static/logos/chelsea.png'},
    {'name': 'Manchester United', 'logo': '/static/logos/manchester_united.png'},
    {'name': 'Liverpool', 'logo': '/static/logos/liverpool.png'},
    {'name': 'Manchester City', 'logo': '/static/logos/manchester_city.png'}
]
TEAMS = [team['name'] for team in TEAMS_DATA]
TEAM_LOGOS = {}
TEAM_LOGOS_FALLBACK = {}

def get_player_position(team_name, player_index):
    """Определяет позицию игрока по индексу"""
    if player_index < 2:
        return 'GK'
    elif player_index < 8:
        return 'DEF'
    elif player_index < 14:
        return 'MID'
    else:
        return 'FWD'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/new_game')
def new_game():
    return render_template('select_team.html', teams=TEAMS_DATA, preselected_team='')

@app.route('/load_game')
def load_game():
    return render_template('load_game.html', saves=[], is_vercel=True)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    team_name = request.form.get('team')
    if not team_name or team_name not in TEAMS:
        return redirect(url_for('new_game'))

    # Создаем игровую сессию
    session['game_data'] = {
        'team_name': team_name,
        'squad': [{'name': f'Player {i}', 'rating': 70} for i in range(20)],
        'selected_players': [f'Player {i}' for i in range(11)],
        'next_opponent': 'Chelsea' if team_name != 'Chelsea' else 'Arsenal',
        'current_round': 1
    }

    return redirect(url_for('match'))

@app.route('/match')
def match():
    try:
        # Создаем тестовые данные сессии
        if 'game_data' not in session:
            session['game_data'] = {
                'team_name': 'Arsenal',
                'squad': [{'name': f'Player {i}', 'rating': 70} for i in range(20)],
                'selected_players': [f'Player {i}' for i in range(11)],
                'next_opponent': 'Chelsea'
            }
        
        game_data = session['game_data']
        my_team = game_data['team_name']
        opponent_team = game_data['next_opponent']
        
        my_lineup = [{'name': f'Player {i}', 'rating': 70} for i in range(11)]
        opponent_lineup = [{'name': f'Opp Player {i}', 'rating': 70} for i in range(11)]
        
        match_data = {
            'my_team': my_team,
            'opponent_team': opponent_team,
            'my_score': 0,
            'opponent_score': 0,
            'goals': [],
            'half': 1,
            'minute': 0,
            'possession_my': 50,
            'possession_opponent': 50,
            'shots_my': 0,
            'shots_opponent': 0,
            'shots_on_target_my': 0,
            'shots_on_target_opponent': 0,
            'xg_my': 0.0,
            'xg_opponent': 0.0
        }
        
        session['match_data'] = match_data
        
        # Простые проценты
        shots_my_percent = 50
        shots_opponent_percent = 50
        shots_on_target_my_percent = 50
        shots_on_target_opponent_percent = 50
        xg_my_percent = 50
        xg_opponent_percent = 50
        
        return render_template('match.html',
                             my_team=my_team,
                             opponent_team=opponent_team,
                             match_data=match_data,
                             my_lineup=my_lineup,
                             opponent_lineup=opponent_lineup,
                             shots_my_percent=shots_my_percent,
                             shots_opponent_percent=shots_opponent_percent,
                             shots_on_target_my_percent=shots_on_target_my_percent,
                             shots_on_target_opponent_percent=shots_on_target_opponent_percent,
                             xg_my_percent=xg_my_percent,
                             xg_opponent_percent=xg_opponent_percent,
                             TEAM_LOGOS=TEAM_LOGOS,
                             TEAM_LOGOS_FALLBACK=TEAM_LOGOS_FALLBACK)
    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route('/match_action', methods=['POST'])
def match_action():
    try:
        if 'game_data' not in session or 'match_data' not in session:
            return jsonify({"success": False, "error": "Session not initialized"})

        import random
        data = request.get_json()
        action = data.get('action', '')

        match_data = session['match_data']
        game_data = session['game_data']

        if action == 'tick':
            # Обновляем таймер
            minute = data.get('minute', 0)
            half = data.get('half', 1)

            # Увеличиваем минуту
            minute += 1
            if minute > 45 and half == 1:
                # Переход ко второму тайму
                minute = 46
                half = 2
            elif minute > 90 and half == 2:
                minute = 90  # Матч окончен

            match_data['minute'] = minute
            match_data['half'] = half

            # Инициализируем статистику если не существует
            if 'shots_my' not in match_data:
                match_data['shots_my'] = 0
            if 'shots_opponent' not in match_data:
                match_data['shots_opponent'] = 0
            if 'shots_on_target_my' not in match_data:
                match_data['shots_on_target_my'] = 0
            if 'shots_on_target_opponent' not in match_data:
                match_data['shots_on_target_opponent'] = 0
            if 'possession_my' not in match_data:
                match_data['possession_my'] = 50
            if 'possession_opponent' not in match_data:
                match_data['possession_opponent'] = 50
            if 'xg_my' not in match_data:
                match_data['xg_my'] = 0.0
            if 'xg_opponent' not in match_data:
                match_data['xg_opponent'] = 0.0

            events = []

            # Генерируем события каждые несколько секунд
            if random.random() < 0.08:  # 8% шанс события каждую секунду
                if random.random() < 0.6:  # Моя команда атакует
                    match_data['shots_my'] += 1
                    if random.random() < 0.4:  # Попадание в створ
                        match_data['shots_on_target_my'] += 1
                        match_data['xg_my'] += random.uniform(0.05, 0.15)
                        if random.random() < 0.2:  # ГОЛ!
                            match_data['my_score'] = match_data.get('my_score', 0) + 1
                            events.append("⚽ ГОЛ! " + game_data['team_name'] + " забивает!")
                    else:
                        events.append("❌ Удар " + game_data['team_name'] + " мимо ворот")
                else:  # Соперник атакует
                    match_data['shots_opponent'] += 1
                    if random.random() < 0.4:  # Попадание в створ
                        match_data['shots_on_target_opponent'] += 1
                        match_data['xg_opponent'] += random.uniform(0.05, 0.15)
                        if random.random() < 0.2:  # ГОЛ!
                            match_data['opponent_score'] = match_data.get('opponent_score', 0) + 1
                            events.append("⚽ ГОЛ! " + game_data['next_opponent'] + " забивает!")
                    else:
                        events.append("❌ Удар " + game_data['next_opponent'] + " мимо ворот")

            # Обновляем владение
            if random.random() < 0.3:
                change = random.randint(-3, 3)
                match_data['possession_my'] = max(30, min(70, match_data['possession_my'] + change))
                match_data['possession_opponent'] = 100 - match_data['possession_my']

            session['match_data'] = match_data

            return jsonify({
                "success": True,
                "match_data": {
                    "minute": minute,
                    "half": half,
                    "my_score": match_data.get('my_score', 0),
                    "opponent_score": match_data.get('opponent_score', 0),
                    "finished": minute >= 90,
                    "events": events,
                    "goals": [],  # Для совместимости
                    "shots_my": match_data['shots_my'],
                    "shots_on_target_my": match_data['shots_on_target_my'],
                    "possession_my": match_data['possession_my'],
                    "xg_my": round(match_data['xg_my'], 2)
                }
            })

        elif action == 'start_second_half':
            # Начинаем второй тайм
            match_data['half'] = 2
            match_data['minute'] = 46
            session['match_data'] = match_data

            return jsonify({
                "success": True,
                "match_data": {
                    "minute": 46,
                    "half": 2,
                    "my_score": match_data.get('my_score', 0),
                    "opponent_score": match_data.get('opponent_score', 0),
                    "finished": False
                }
            })

        elif action == 'end_match':
            # Завершаем матч и генерируем результаты параллельных матчей
            current_round = game_data.get('current_round', 1)

            # Сохраняем результат текущего матча
            my_result = {
                'home_team': game_data['team_name'] if game_data.get('is_home_match', True) else game_data['next_opponent'],
                'away_team': game_data['next_opponent'] if game_data.get('is_home_match', True) else game_data['team_name'],
                'home_score': match_data.get('my_score', 0) if game_data.get('is_home_match', True) else match_data.get('opponent_score', 0),
                'away_score': match_data.get('opponent_score', 0) if game_data.get('is_home_match', True) else match_data.get('my_score', 0),
                'goals': []
            }

            # Добавляем текущий результат в историю матчей
            if 'match_results' not in session:
                session['match_results'] = []
            session['match_results'].append(my_result)

            # Генерируем результаты параллельных матчей
            round_results = [my_result]

            # Получаем расписание матчей
            active_schedule = session.get('custom_schedule', MATCH_SCHEDULE)
            if current_round <= len(active_schedule):
                round_matches = active_schedule[current_round - 1]
                for home, away in round_matches:
                    # Пропускаем наш матч
                    if (home == game_data['team_name'] and away == game_data['next_opponent']) or                        (away == game_data['team_name'] and home == game_data['next_opponent']):
                        continue

                    # Генерируем результат для параллельного матча
                    home_squad = []
                    away_squad = []

                    if home in SQUADS_2007_08:
                        for player_data in SQUADS_2007_08[home]:
                            if isinstance(player_data, tuple):
                                player_name, rating = player_data
                            else:
                                player_name = player_data
                                rating = 70
                            home_squad.append({"name": player_name, "rating": rating})

                    if away in SQUADS_2007_08:
                        for player_data in SQUADS_2007_08[away]:
                            if isinstance(player_data, tuple):
                                player_name, rating = player_data
                            else:
                                player_name = player_data
                                rating = 70
                            away_squad.append({"name": player_name, "rating": rating})

                    home_lineup = create_optimal_lineup(home_squad, home)
                    away_lineup = create_optimal_lineup(away_squad, away)

                    home_strength = calculate_lineup_strength(home_lineup)
                    away_strength = calculate_lineup_strength(away_lineup)

                    home_advantage = 1.05
                    home_effective = home_strength * home_advantage
                    away_effective = away_strength

                    home_form = random.uniform(0.9, 1.1)
                    away_form = random.uniform(0.9, 1.1)

                    home_final = home_effective * home_form
                    away_final = away_effective * away_form

                    strength_diff = home_final - away_final
                    home_win_prob = 0.5 + (strength_diff / 15)
                    home_win_prob = max(0.15, min(0.85, home_win_prob))

                    strength_diff_abs = abs(home_final - away_final)
                    score_variability = min(3, strength_diff_abs / 8)

                    home_score = 0
                    away_score = 0

                    if random.random() < home_win_prob:
                        if strength_diff_abs > 15:
                            home_score = random.randint(2, 5 + int(score_variability))
                            away_score = random.randint(0, min(3, home_score - 1))
                        elif strength_diff_abs > 8:
                            home_score = random.randint(1, 4 + int(score_variability))
                            away_score = random.randint(0, home_score)
                        else:
                            home_score = random.randint(1, 4)
                            away_score = random.randint(0, home_score)
                    else:
                        if random.random() < 0.55:
                            if strength_diff_abs > 15:
                                away_score = random.randint(2, 5 + int(score_variability))
                                home_score = random.randint(0, min(3, away_score - 1))
                            elif strength_diff_abs > 8:
                                away_score = random.randint(1, 4 + int(score_variability))
                                home_score = random.randint(0, away_score)
                            else:
                                away_score = random.randint(1, 4)
                                home_score = random.randint(0, away_score)
                        else:
                            if strength_diff_abs > 15:
                                home_score = random.randint(0, 3)
                                away_score = random.randint(0, 3)
                            else:
                                home_score = random.randint(0, 4)
                                away_score = random.randint(0, 4)

                    parallel_result = {
                        'home_team': home,
                        'away_team': away,
                        'home_score': home_score,
                        'away_score': away_score,
                        'goals': []
                    }
                    round_results.append(parallel_result)

            # Сохраняем результаты раунда
            session['last_round_results'] = round_results

            # Обновляем турнирную таблицу
            update_league_table(round_results)

            # Переходим к следующему раунду
            new_round = current_round + 1
            game_data['current_round'] = new_round
            session['game_data'] = game_data

            # Определяем следующего соперника
            if new_round <= len(active_schedule):
                next_matches = active_schedule[new_round - 1]
                for home, away in next_matches:
                    if home == game_data['team_name'] or away == game_data['team_name']:
                        game_data['next_opponent'] = away if home == game_data['team_name'] else home
                        game_data['is_home_match'] = home == game_data['team_name']
                        break

            is_season_end = new_round > len(active_schedule)

            return jsonify({
                "success": True,
                "season_end": is_season_end,
                "next_opponent": game_data.get('next_opponent', ''),
                "is_home_match": game_data.get('is_home_match', True),
                "final_score": str(my_result['home_score']) + "-" + str(my_result['away_score'])
            })

        return jsonify({"success": False, "error": "Unknown action"})

    except Exception as e:
        import traceback
        print("Error in match_action: " + str(e))
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})
if __name__ == '__main__':
    app.run(debug=True)
