from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'football_manager_secret_key_2024'

# Простые данные для тестирования
TEAMS = ['Arsenal', 'Chelsea', 'Manchester United', 'Liverpool', 'Manchester City']
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
    return render_template('select_team.html', teams=TEAMS, preselected_team='')

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
        if 'match_data' not in session:
            return jsonify({"success": False, "error": "Session not initialized"})

        data = request.get_json()
        action = data.get('action', '')

        match_data = session['match_data']

        if action == 'tick':
            minute = data.get('minute', 0)
            half = data.get('half', 1)
            
            minute += 1
            if half == 1 and minute > 45:
                minute = 45
            elif half == 2 and minute > 90:
                minute = 90

            match_data['minute'] = minute
            match_data['half'] = half

            events = []
            import random
            if random.random() < 0.08:
                if random.random() < 0.6:
                    match_data['shots_my'] += 1
                    if random.random() < 0.2:
                        match_data['score_my'] += 1
                        events.append("Гол!")
                else:
                    match_data['shots_opponent'] += 1
                    if random.random() < 0.2:
                        match_data['score_opponent'] += 1
                        events.append("Гол соперника!")

            session['match_data'] = match_data

            return jsonify({
                "success": True,
                "match_data": {
                    "minute": minute,
                    "half": half,
                    "my_score": match_data['score_my'],
                    "opponent_score": match_data['score_opponent'],
                    "finished": minute >= 90,
                    "events": events,
                    "stats": {
                        "shots": match_data['shots_my'],
                        "shots_on_target": match_data['shots_on_target_my'],
                        "possession": match_data['possession_my'],
                        "xg": 0.0
                    },
                    "goals": match_data['goals']
                }
            })

        elif action == 'start_second_half':
            match_data['half'] = 2
            match_data['minute'] = 46
            session['match_data'] = match_data

            return jsonify({
                "success": True,
                "match_data": {
                    "minute": 46,
                    "half": 2,
                    "my_score": match_data['score_my'],
                    "opponent_score": match_data['score_opponent'],
                    "finished": False,
                    "events": ["Второй тайм начался!"],
                    "goals": match_data['goals']
                }
            })

        elif action == 'end_match':
            return jsonify({
                "success": True,
                "season_end": False,
                "next_opponent": "Manchester United",
                "is_home_match": True,
                "final_score": str(match_data['score_my']) + "-" + str(match_data['score_opponent'])
            })

        return jsonify({"success": False, "error": "Unknown action"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
