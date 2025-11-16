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
            if half == 1 and minute > 45:
                minute = 45  # Останавливаемся на 45 минуте
            elif half == 2 and minute > 90:
                minute = 90  # Матч окончен

            match_data['minute'] = minute
            match_data['half'] = half

            # Генерируем события
            events = []
            if random.random() < 0.08:  # 8% шанс события
                if random.random() < 0.6:  # Моя команда
                    match_data['shots_my'] = match_data.get('shots_my', 0) + 1
                    if random.random() < 0.4:  # Попадание
                        match_data['shots_on_target_my'] = match_data.get('shots_on_target_my', 0) + 1
                        if random.random() < 0.2:  # ГОЛ!
                            match_data['score_my'] = match_data.get('score_my', 0) + 1
                            events.append("⚽ ГОЛ! " + game_data['team_name'] + " забивает!")
                else:  # Соперник
                    match_data['shots_opponent'] = match_data.get('shots_opponent', 0) + 1
                    if random.random() < 0.4:  # Попадание
                        match_data['shots_on_target_opponent'] = match_data.get('shots_on_target_opponent', 0) + 1
                        if random.random() < 0.2:  # ГОЛ!
                            match_data['score_opponent'] = match_data.get('score_opponent', 0) + 1
                            events.append("⚽ ГОЛ! " + game_data['next_opponent'] + " забивает!")

            session['match_data'] = match_data

            return jsonify({
                "success": True,
                "match_data": {
                    "minute": minute,
                    "half": half,
                    "my_score": match_data.get('score_my', 0),
                    "opponent_score": match_data.get('score_opponent', 0),
                    "finished": minute >= 90,
                    "events": events,
                    "stats": {
                        "shots": match_data.get('shots_my', 0),
                        "shots_on_target": match_data.get('shots_on_target_my', 0),
                        "possession": match_data.get('possession_my', 50),
                        "xg": round(match_data.get('xg_my', 0.0), 2)
                    },
                    "goals": match_data.get('goals', [])
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
                    "my_score": match_data.get('score_my', 0),
                    "opponent_score": match_data.get('score_opponent', 0),
                    "finished": False,
                    "events": ["Второй тайм начался!"],
                    "goals": match_data.get('goals', [])
                }
            })

        elif action == 'end_match':
            # Простая версия завершения матча
            return jsonify({
                "success": True,
                "season_end": False,
                "next_opponent": "Manchester United",
                "is_home_match": True,
                "final_score": str(match_data.get('score_my', 0)) + "-" + str(match_data.get('score_opponent', 0))
            })

        return jsonify({"success": False, "error": "Unknown action"})

    except Exception as e:
        import traceback
        print("Error in match_action: " + str(e))
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})
