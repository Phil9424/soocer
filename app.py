from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'football_manager_secret_key_2024'

# Функция для определения позиции игрока
def get_player_position(team_name, player_index):
    """Определяет позицию игрока по его месту в составе"""
    if team_name in SQUADS_2007_08:
        squad_size = len(SQUADS_2007_08[team_name])
        # Вратарь (обычно 0-1)
        if player_index < 2:
            return 'GK'
        # Защитники (обычно 2-8)
        elif player_index < 9:
            return 'DEF'
        # Полузащитники (обычно 9-14)
        elif player_index < 15:
            return 'MID'
        # Нападающие (остальные)
        else:
            return 'FWD'
    return 'MID'  # По умолчанию

# Функция для выбора бомбардира из состава пользователя
def select_goal_scorer(game_data, lineup):
    """Выбирает бомбардира с учетом позиций (вратари редко забивают)"""
    import random

    # Создаем список игроков с весами
    scorers_with_weights = []

    for i, player in enumerate(lineup):
        position = get_player_position(game_data['team_name'], i)
        name = player['name']

        # Веса по позициям (чем выше, тем чаще забивает)
        if position == 'GK':
            weight = 1  # Вратари забивают очень редко (1 на 1000 матчей)
        elif position == 'DEF':
            weight = 3  # Защитники забивают реже
        elif position == 'MID':
            weight = 5  # Полузащитники забивают чаще
        elif position == 'FWD':
            weight = 7  # Нападающие забивают чаще всего
        else:
            weight = 4  # По умолчанию

        scorers_with_weights.extend([name] * weight)

    if scorers_with_weights:
        return random.choice(scorers_with_weights)
    else:
        return random.choice([p['name'] for p in lineup])

# Функция для выбора бомбардира соперника
def select_opponent_goal_scorer(team_name, lineup):
    """Выбирает бомбардира соперника с учетом позиций"""
    import random

    # Создаем список игроков с весами
    scorers_with_weights = []

    for i, player in enumerate(lineup):
        position = get_player_position(team_name, i)
        name = player['name']

        # Веса по позициям (чем выше, тем чаще забивает)
        if position == 'GK':
            weight = 1  # Вратари забивают очень редко
        elif position == 'DEF':
            weight = 3  # Защитники забивают реже
        elif position == 'MID':
            weight = 5  # Полузащитники забивают чаще
        elif position == 'FWD':
            weight = 7  # Нападающие забивают чаще всего
        else:
            weight = 4  # По умолчанию

        scorers_with_weights.extend([name] * weight)

    if scorers_with_weights:
        return random.choice(scorers_with_weights)
    else:
        return random.choice([p['name'] for p in lineup])

# Функция для получения среднего рейтинга команды
def get_team_average_rating(team_name):
    """Вычисляет средний рейтинг команды"""
    if team_name in SQUADS_2007_08:
        squad = SQUADS_2007_08[team_name]
        ratings = []
        for player_data in squad[:18]:  # Берем первых 18 игроков (основной состав + запас)
            if isinstance(player_data, tuple):
                rating = player_data[1]
            else:
                rating = 70  # По умолчанию
            ratings.append(rating)
        return sum(ratings) / len(ratings) if ratings else 70
    return 70  # По умолчанию для неизвестных команд

# Функция для обновления турнирной таблицы
def update_league_table(round_results):
    """Обновляет турнирную таблицу на основе результатов матчей тура"""
    if 'game_data' not in session:
        return

    game_data = session['game_data']
    table = game_data['table']

    # Создаем словарь для быстрого доступа к командам
    teams_dict = {team['team']: team for team in table}

    # Обрабатываем каждый результат матча
    for result in round_results:
        home_team = result['home_team']
        away_team = result['away_team']
        home_score = result['home_score']
        away_score = result['away_score']

        # Обновляем статистику домашней команды
        if home_team in teams_dict:
            team = teams_dict[home_team]
            team['played'] += 1
            team['won'] += 1 if home_score > away_score else 0
            team['drawn'] += 1 if home_score == away_score else 0
            team['lost'] += 1 if home_score < away_score else 0
            team['points'] = team['won'] * 3 + team['drawn']

        # Обновляем статистику гостевой команды
        if away_team in teams_dict:
            team = teams_dict[away_team]
            team['played'] += 1
            team['won'] += 1 if away_score > home_score else 0
            team['drawn'] += 1 if away_score == home_score else 0
            team['lost'] += 1 if away_score < home_score else 0
            team['points'] = team['won'] * 3 + team['drawn']

    # Сортируем таблицу по очкам
    table.sort(key=lambda x: (x['points'], x['won'], x['played']), reverse=True)

    # Обновляем позиции
    for i, team in enumerate(table, 1):
        team['position'] = i

    # Сохраняем обновленную таблицу
    game_data['table'] = table
    session['game_data'] = game_data

# Список команд
TEAMS = [
    "Arsenal", "Aston Villa", "Birmingham City", "Blackburn Rovers",
    "Bolton Wanderers", "Chelsea", "Derby County", "Everton", "Fulham",
    "Liverpool", "Manchester City", "Manchester United", "Middlesbrough",
    "Newcastle United", "Portsmouth", "Reading", "Sunderland",
    "Tottenham Hotspur", "West Ham United", "Wigan Athletic"
]

# Генерация полного календаря АПЛ (38 туров, каждый играет с каждым 2 раза)
def generate_full_schedule():
    """Генерирует полный календарь чемпионата где каждая команда играет с каждой 2 раза"""
    schedule = []

    # Для 20 команд: 19 туров в круге, 2 круга (дома и в гостях) = 38 туров
    # В каждом туре 10 матчей (20 команд / 2)

    teams = TEAMS.copy()

    # Первый круг
    # Фиксируем первую команду, остальные будут циклически сдвигаться
    fixed_team = teams[0]
    rotating_teams = teams[1:]

    for round_num in range(19):  # 19 туров в первом круге
        round_matches = []

        # Создаем пары для этого тура
        # Матчи: rotating_teams[i] vs rotating_teams[18-i] (домашние матчи)
        for i in range(9):  # 9 матчей в туре (18 команд / 2)
            home = rotating_teams[i]
            away = rotating_teams[17 - i]  # Симметричная позиция
            round_matches.append((home, away))

        # Последний матч: фиксированная команда vs последняя rotating команда
        round_matches.append((fixed_team, rotating_teams[-1]))

        schedule.append(round_matches)

        # Циклический сдвиг rotating команд (последняя становится первой)
        rotating_teams = [rotating_teams[-1]] + rotating_teams[:-1]

    # Второй круг - те же матчи, но поменяны домашние/гостевые
    first_round_schedule = schedule.copy()
    for round_matches in first_round_schedule:
        reversed_round = [(away, home) for home, away in round_matches]
        schedule.append(reversed_round)

    return schedule

# Инициализируем календарь при запуске
MATCH_SCHEDULE = generate_full_schedule()

# Составы команд сезона 2007-08 с рейтингами FIFA 08
SQUADS_2007_08 = {
    "Arsenal": [
        ("Manuel Almunia", 75), ("Jens Lehmann", 82), ("Gael Clichy", 78), ("Kolo Toure", 81), ("William Gallas", 84),
        ("Philippe Senderos", 76), ("Bacary Sagna", 79), ("Emmanuel Eboue", 75), ("Cesc Fabregas", 85), ("Mathieu Flamini", 78),
        ("Gilberto Silva", 80), ("Tomas Rosicky", 82), ("Alexander Hleb", 81), ("Theo Walcott", 72), ("Robin van Persie", 82),
        ("Emmanuel Adebayor", 80), ("Nicklas Bendtner", 70), ("Eduardo", 78), ("Abou Diaby", 73), ("Denilson", 71),
        ("Alexandre Song", 70), ("Justin Hoyte", 68), ("Armand Traore", 65), ("Lukasz Fabianski", 72)
    ],
    "Aston Villa": [
        ("Scott Carson", 75), ("Stuart Taylor", 68), ("Olof Mellberg", 78), ("Martin Laursen", 79), ("Zat Knight", 73),
        ("Curtis Davies", 74), ("Wilfred Bouma", 76), ("Nicky Shorey", 75), ("Gareth Barry", 81), ("Nigel Reo-Coker", 76),
        ("Stiliyan Petrov", 78), ("Ashley Young", 77), ("Shaun Maloney", 74), ("Gabriel Agbonlahor", 75), ("John Carew", 78),
        ("Marlon Harewood", 72), ("Luke Moore", 70), ("Craig Gardner", 68), ("Isaiah Osbourne", 65), ("Patrik Berger", 76),
        ("Moustapha Salifou", 64), ("Wayne Routledge", 72), ("Nathan Delfouneso", 62)
    ],
    "Birmingham City": [
        ("Maik Taylor", 72), ("Colin Doyle", 65), ("Stephen Kelly", 71), ("Liam Ridgewell", 72), ("Radhi Jaidi", 73),
        ("Martin Taylor", 70), ("Franck Queudrue", 74), ("Stuart Parnaby", 69), ("Sebastian Larsson", 73), ("Fabrice Muamba", 72),
        ("Damien Johnson", 73), ("Mehdi Nafti", 71), ("Gary McSheffrey", 72), ("Cameron Jerome", 71), ("Mikael Forssell", 74),
        ("James McFadden", 75), ("Garry O'Connor", 72), ("Daniel de Ridder", 70), ("Olivier Kapo", 75), ("Rafael Schmitz", 71),
        ("Marcus Bent", 72), ("David Murphy", 70), ("Johan Djourou", 71)
    ],
    "Blackburn Rovers": [
        ("Brad Friedel", 82), ("Jason Brown", 68), ("Ryan Nelsen", 78), ("Christopher Samba", 75), ("Andre Ooijer", 76),
        ("Zurab Khizanishvili", 73), ("Stephen Warnock", 74), ("Brett Emerton", 77), ("David Bentley", 78), ("Morten Gamst Pedersen", 77),
        ("Tugay Kerimoglu", 76), ("Robbie Savage", 75), ("Steven Reid", 74), ("Benedict McCarthy", 76), ("Roque Santa Cruz", 80),
        ("Jason Roberts", 73), ("Matt Derbyshire", 70), ("Aaron Mokoena", 72), ("David Dunn", 76), ("Maceo Rigters", 68),
        ("Keith Treacy", 65), ("Martin Olsson", 66), ("Tony Kane", 63)
    ],
    "Bolton Wanderers": [
        ("Jussi Jaaskelainen", 80), ("Ali Al Habsi", 72), ("Abdoulaye Meite", 74), ("Andy O'Brien", 73), ("Gretar Steinsson", 72),
        ("Gavin McCann", 74), ("Kevin Nolan", 77), ("Ivan Campo", 76), ("Nicky Hunt", 71), ("Jlloyd Samuel", 73),
        ("Ricardo Gardner", 75), ("Stelios Giannakopoulos", 74), ("El-Hadji Diouf", 76), ("Kevin Davies", 75), ("Nicolas Anelka", 82),
        ("Heidar Helguson", 72), ("Daniel Braaten", 73), ("Tamir Cohen", 68), ("Danny Guthrie", 70), ("Joey O'Brien", 69),
        ("Blazej Augustyn", 66), ("Lubomir Michalik", 68), ("James Sinclair", 64)
    ],
    "Chelsea": [
        ("Petr Cech", 88), ("Carlo Cudicini", 80), ("John Terry", 88), ("Ricardo Carvalho", 85), ("Ashley Cole", 85),
        ("Paulo Ferreira", 79), ("Wayne Bridge", 78), ("Michael Essien", 86), ("Frank Lampard", 87), ("Claude Makelele", 84),
        ("Michael Ballack", 86), ("Joe Cole", 83), ("Shaun Wright-Phillips", 78), ("Florent Malouda", 82), ("Didier Drogba", 88),
        ("Nicolas Anelka", 82), ("Salomon Kalou", 78), ("Andriy Shevchenko", 82), ("John Obi Mikel", 78), ("Alex", 80),
        ("Juliano Belletti", 78), ("Branislav Ivanovic", 77), ("Scott Sinclair", 68), ("Steve Sidwell", 75)
    ],
    "Derby County": [
        ("Stephen Bywater", 70), ("Roy Carroll", 72), ("Darren Moore", 71), ("Claude Davis", 70), ("Dean Leacock", 69),
        ("Andy Todd", 70), ("Marc Edworthy", 69), ("Tyrone Mears", 70), ("Matt Oakley", 72), ("Gary Teale", 71),
        ("Eddie Lewis", 71), ("David Jones", 72), ("Stephen Pearson", 71), ("Giles Barnes", 70), ("Kenny Miller", 74),
        ("Rob Earnshaw", 72), ("Steve Howard", 72), ("Emanuel Villa", 71), ("Hossam Ghaly", 72), ("Benny Feilhaber", 71),
        ("Lewin Nyatanga", 68), ("Jay McEveley", 69), ("Mile Sterjovski", 70)
    ],
    "Everton": [
        ("Tim Howard", 81), ("Stefan Wessels", 70), ("Joseph Yobo", 78), ("Joleon Lescott", 79), ("Phil Jagielka", 77),
        ("Leighton Baines", 78), ("Tony Hibbert", 73), ("Phil Neville", 77), ("Mikel Arteta", 82), ("Leon Osman", 76),
        ("Tim Cahill", 81), ("Steven Pienaar", 77), ("Andy Johnson", 77), ("Yakubu", 80), ("James Vaughan", 72),
        ("Victor Anichebe", 71), ("James McFadden", 75), ("Lee Carsley", 75), ("Thomas Gravesen", 74), ("Manuel Fernandes", 75),
        ("Nuno Valente", 74), ("Alan Stubbs", 73), ("Lukas Jutkiewicz", 68)
    ],
    "Fulham": [
        ("Antti Niemi", 78), ("Kasey Keller", 76), ("Carlos Bocanegra", 76), ("Aaron Hughes", 77), ("Brede Hangeland", 78),
        ("Dejan Stefanovic", 74), ("Paul Konchesky", 75), ("Moritz Volz", 73), ("Simon Davies", 76), ("Clint Dempsey", 77),
        ("Danny Murphy", 78), ("Jimmy Bullard", 77), ("Steven Davis", 74), ("Hameur Bouazza", 73), ("Diomansy Kamara", 75),
        ("David Healy", 75), ("Brian McBride", 77), ("Erik Nevland", 73), ("Seol Ki-Hyeon", 74), ("Alexey Smertin", 73),
        ("Chris Baird", 73), ("Tony Kallio", 71), ("Eddie Johnson", 72)
    ],
    "Liverpool": [
        ("Pepe Reina", 85), ("Charles Itandje", 72), ("Jamie Carragher", 85), ("Daniel Agger", 80), ("Sami Hyypia", 81),
        ("John Arne Riise", 79), ("Steve Finnan", 78), ("Alvaro Arbeloa", 77), ("Fabio Aurelio", 77), ("Steven Gerrard", 88),
        ("Xabi Alonso", 84), ("Javier Mascherano", 83), ("Lucas Leiva", 75), ("Yossi Benayoun", 79), ("Ryan Babel", 78),
        ("Fernando Torres", 87), ("Dirk Kuyt", 81), ("Peter Crouch", 78), ("Andriy Voronin", 76), ("Jermaine Pennant", 76),
        ("Harry Kewell", 79), ("Mohamed Sissoko", 77), ("Martin Skrtel", 78), ("Emiliano Insua", 70)
    ],
    "Manchester City": [
        ("Joe Hart", 73), ("Andreas Isaksson", 77), ("Richard Dunne", 79), ("Micah Richards", 78), ("Nedum Onuoha", 74),
        ("Michael Ball", 72), ("Javier Garrido", 74), ("Vedran Corluka", 77), ("Michael Johnson", 75), ("Stephen Ireland", 78),
        ("Elano", 82), ("Martin Petrov", 80), ("Darius Vassell", 75), ("Rolando Bianchi", 76), ("Emile Mpenza", 74),
        ("Valeri Bojinov", 76), ("Felipe Caicedo", 73), ("Geovanni", 78), ("Dietmar Hamann", 77), ("Gelson Fernandes", 73),
        ("Sun Jihai", 72), ("Danny Mills", 73), ("Kelvin Etuhu", 68)
    ],
    "Manchester United": [
        ("Edwin van der Sar", 86), ("Tomasz Kuszczak", 76), ("Rio Ferdinand", 87), ("Nemanja Vidic", 85), ("Patrice Evra", 84),
        ("Gary Neville", 81), ("Wes Brown", 78), ("John O'Shea", 77), ("Michael Carrick", 83), ("Paul Scholes", 86),
        ("Owen Hargreaves", 82), ("Anderson", 79), ("Ryan Giggs", 84), ("Cristiano Ronaldo", 91), ("Nani", 80),
        ("Wayne Rooney", 88), ("Carlos Tevez", 85), ("Louis Saha", 81), ("Dimitar Berbatov", 85), ("Ji-sung Park", 79),
        ("Darren Fletcher", 78), ("Danny Welbeck", 65), ("Rafael", 70), ("Fabio", 70)
    ],
    "Middlesbrough": [
        ("Mark Schwarzer", 79), ("Ross Turnbull", 68), ("David Wheater", 73), ("Robert Huth", 77), ("Emanuel Pogatetz", 75),
        ("Jonathan Woodgate", 79), ("Luke Young", 77), ("Andrew Taylor", 71), ("Stewart Downing", 78), ("Gary O'Neil", 75),
        ("Fabio Rochemback", 75), ("George Boateng", 77), ("Julio Arca", 75), ("Tuncay Sanli", 77), ("Jeremie Aliadiere", 74),
        ("Mido", 78), ("Dong-Gook Lee", 72), ("Tom Craddock", 66), ("Adam Johnson", 72), ("Lee Cattermole", 71),
        ("Matthew Bates", 70), ("Chris Riggott", 73), ("Seventh Hines", 65)
    ],
    "Newcastle United": [
        ("Steve Harper", 75), ("Shay Given", 82), ("Steven Taylor", 75), ("Habib Beye", 76), ("Jose Enrique", 77),
        ("Charles N'Zogbia", 77), ("Geremi", 76), ("Nicky Butt", 76), ("Joey Barton", 78), ("James Milner", 77),
        ("Damien Duff", 79), ("Obafemi Martins", 80), ("Michael Owen", 82), ("Mark Viduka", 78), ("Alan Smith", 75),
        ("Shola Ameobi", 73), ("Peter Lovenkrands", 74), ("Andy Carroll", 68), ("David Edgar", 69), ("Fabricio Coloccini", 79),
        ("Jonas Gutierrez", 77), ("Danny Guthrie", 72), ("Sebastien Bassong", 73)
    ],
    "Portsmouth": [
        ("David James", 80), ("Jamie Ashdown", 69), ("Sol Campbell", 82), ("Sylvain Distin", 79), ("Glen Johnson", 78),
        ("Hermann Hreidarsson", 75), ("Noe Pamarot", 73), ("Lassana Diarra", 81), ("Sulley Muntari", 79), ("Papa Bouba Diop", 77),
        ("Niko Kranjcar", 80), ("John Utaka", 77), ("Benjani", 76), ("Jermain Defoe", 81), ("Peter Crouch", 78),
        ("Nwankwo Kanu", 76), ("David Nugent", 73), ("Sean Davis", 75), ("Richard Hughes", 74), ("Pedro Mendes", 76),
        ("Glen Little", 72), ("Djimi Traore", 73), ("Lauren", 75)
    ],
    "Reading": [
        ("Marcus Hahnemann", 77), ("Adam Federici", 70), ("Ibrahima Sonko", 74), ("Michael Duberry", 73), ("Nick Shorey", 76),
        ("Graeme Murty", 73), ("Liam Rosenior", 72), ("James Harper", 75), ("Stephen Hunt", 75), ("Bobby Convey", 74),
        ("John Oster", 73), ("Kevin Doyle", 77), ("Dave Kitson", 75), ("Leroy Lita", 74), ("Shane Long", 72),
        ("Nicky Forster", 72), ("Kalifa Cisse", 73), ("Brynjar Gunnarsson", 73), ("Andre Bikey", 74), ("Emerse Fae", 75),
        ("Ulises de la Cruz", 72), ("Glen Little", 72), ("Marek Matejovsky", 74)
    ],
    "Sunderland": [
        ("Craig Gordon", 79), ("Darren Ward", 70), ("Nyron Nosworthy", 72), ("Jonny Evans", 74), ("Danny Collins", 72),
        ("Paul McShane", 72), ("Greg Halford", 70), ("Liam Miller", 73), ("Dean Whitehead", 73), ("Kieran Richardson", 76),
        ("Carlos Edwards", 73), ("Daryl Murphy", 71), ("Kenwyne Jones", 76), ("Michael Chopra", 73), ("Roy O'Donovan", 70),
        ("Anthony Stokes", 71), ("Dwight Yorke", 75), ("Grant Leadbitter", 72), ("Ross Wallace", 72), ("Andy Reid", 75),
        ("David Connolly", 73), ("Marton Fulop", 72), ("Phil Bardsley", 72)
    ],
    "Tottenham Hotspur": [
        ("Paul Robinson", 80), ("Radek Cerny", 72), ("Ledley King", 82), ("Michael Dawson", 78), ("Younes Kaboul", 75),
        ("Gareth Bale", 72), ("Pascal Chimbonda", 78), ("Alan Hutton", 75), ("Jermaine Jenas", 79), ("Tom Huddlestone", 76),
        ("Didier Zokora", 77), ("Aaron Lennon", 80), ("Steed Malbranque", 78), ("Robbie Keane", 82), ("Dimitar Berbatov", 85),
        ("Darren Bent", 79), ("Jermain Defoe", 81), ("Teemu Tainio", 74), ("Jamie O'Hara", 72), ("Adel Taarabt", 70),
        ("Giovani dos Santos", 75), ("Heurelho Gomes", 78)
    ],
    "West Ham United": [
        ("Robert Green", 79), ("Richard Wright", 73), ("Anton Ferdinand", 76), ("Matthew Upson", 78), ("Lucas Neill", 77),
        ("George McCartney", 75), ("Jonathan Spector", 72), ("Mark Noble", 75), ("Scott Parker", 79), ("Hayden Mullins", 73),
        ("Freddie Ljungberg", 79), ("Matthew Etherington", 76), ("Craig Bellamy", 79), ("Dean Ashton", 78), ("Carlton Cole", 75),
        ("Bobby Zamora", 75), ("Henri Camara", 73), ("Nolberto Solano", 77), ("Julien Faubert", 76), ("Kieron Dyer", 77),
        ("Lee Bowyer", 75), ("Nigel Quashie", 73), ("Calum Davenport", 72)
    ],
    "Wigan Athletic": [
        ("Chris Kirkland", 77), ("Mike Pollitt", 69), ("Titus Bramble", 73), ("Paul Scharner", 76), ("Mario Melchiot", 76),
        ("Emmerson Boyce", 72), ("Kevin Kilbane", 75), ("Antonio Valencia", 78), ("Jason Koumas", 77), ("Michael Brown", 74),
        ("Ryan Taylor", 72), ("Emile Heskey", 76), ("Marlon King", 74), ("Marcus Bent", 72), ("Julius Aghahowa", 73),
        ("Amr Zaki", 75), ("Henri Camara", 73), ("Daniel de Ridder", 71), ("Tomasz Cywka", 68), ("Erik Edman", 73),
        ("Andreas Granqvist", 73), ("Lewis Montrose", 65)
    ]
}

# Названия стадионов команд сезона 2007-08
STADIUMS_2007_08 = {
    "Arsenal": "Emirates Stadium",
    "Aston Villa": "Villa Park",
    "Birmingham City": "St. Andrew's",
    "Blackburn Rovers": "Ewood Park",
    "Bolton Wanderers": "Reebok Stadium",
    "Chelsea": "Stamford Bridge",
    "Derby County": "Pride Park Stadium",
    "Everton": "Goodison Park",
    "Fulham": "Craven Cottage",
    "Liverpool": "Anfield",
    "Manchester City": "City of Manchester Stadium",
    "Manchester United": "Old Trafford",
    "Middlesbrough": "Riverside Stadium",
    "Newcastle United": "St. James' Park",
    "Portsmouth": "Fratton Park",
    "Reading": "Madejski Stadium",
    "Sunderland": "Stadium of Light",
    "Tottenham Hotspur": "White Hart Lane",
    "West Ham United": "Upton Park",
    "Wigan Athletic": "JJB Stadium"
}

# Вместимость стадионов (примерные данные сезона 2007-08)
STADIUM_CAPACITIES_2007_08 = {
    "Arsenal": 60432,
    "Aston Villa": 42640,
    "Birmingham City": 30016,
    "Blackburn Rovers": 31367,
    "Bolton Wanderers": 28723,
    "Chelsea": 42449,
    "Derby County": 33597,
    "Everton": 40157,
    "Fulham": 19359,
    "Liverpool": 45362,
    "Manchester City": 47726,
    "Manchester United": 76212,
    "Middlesbrough": 35049,
    "Newcastle United": 52387,
    "Portsmouth": 20599,
    "Reading": 24161,
    "Sunderland": 48707,
    "Tottenham Hotspur": 36240,
    "West Ham United": 35447,
    "Wigan Athletic": 25138
}

# Логотипы команд АПЛ 2007-08 (множественные источники)
TEAM_LOGOS = {
    "Arsenal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/200px-Arsenal_FC.svg.png",
    "Aston Villa": "https://a.espncdn.com/i/teamlogos/soccer/500/362.png",
    "Birmingham City": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer/500/392.png",
    "Blackburn Rovers": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer/500/365.png",
    "Bolton Wanderers": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer/500/358.png",
    "Chelsea": "https://upload.wikimedia.org/wikipedia/en/thumb/c/cc/Chelsea_FC.svg/200px-Chelsea_FC.svg.png",
    "Derby County": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer/500/374.png",
    "Everton": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7c/Everton_FC_logo.svg/200px-Everton_FC_logo.svg.png",
    "Fulham": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Fulham_FC_%28shield%29.svg/200px-Fulham_FC_%28shield%29.svg.png",
    "Liverpool": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0c/Liverpool_FC.svg/200px-Liverpool_FC.svg.png",
    "Manchester City": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/200px-Manchester_City_FC_badge.svg.png",
    "Manchester United": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7a/Manchester_United_FC_crest.svg/200px-Manchester_United_FC_crest.svg.png",
    "Middlesbrough": "https://upload.wikimedia.org/wikipedia/en/thumb/2/2c/Middlesbrough_FC_crest.svg/200px-Middlesbrough_FC_crest.svg.png",
    "Newcastle United": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Newcastle_United_Logo.svg/200px-Newcastle_United_Logo.svg.png",
    "Portsmouth": "https://a.espncdn.com/combiner/i?img=/i/teamlogos/soccer/500/385.png",
    "Reading": "https://upload.wikimedia.org/wikipedia/en/thumb/1/11/Reading_FC.svg/200px-Reading_FC.svg.png",
    "Sunderland": "https://a.espncdn.com/i/teamlogos/soccer/500/366.png",
    "Tottenham Hotspur": "https://upload.wikimedia.org/wikipedia/en/thumb/b/b4/Tottenham_Hotspur.svg/200px-Tottenham_Hotspur.svg.png",
    "West Ham United": "https://a.espncdn.com/i/teamlogos/soccer/500/371.png",
    "Wigan Athletic": "https://upload.wikimedia.org/wikipedia/en/thumb/4/43/Wigan_Athletic.svg/200px-Wigan_Athletic.svg.png"
}

# Запасные логотипы (PNG вместо SVG для лучшей совместимости)
TEAM_LOGOS_FALLBACK = {
    "Arsenal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/120px-Arsenal_FC.svg.png",
    "Aston Villa": "https://upload.wikimedia.org/wikipedia/en/thumb/f/f9/Aston_Villa_FC_crest.svg/120px-Aston_Villa_FC_crest.svg.png",
    "Birmingham City": "https://upload.wikimedia.org/wikipedia/en/thumb/6/6c/Birmingham_City_FC_logo.svg/120px-Birmingham_City_FC_logo.svg.png",
    "Blackburn Rovers": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0f/Blackburn_Rovers_FC_logo.svg/120px-Blackburn_Rovers_FC_logo.svg.png",
    "Bolton Wanderers": "https://upload.wikimedia.org/wikipedia/en/thumb/3/37/Bolton_Wanderers_FC_logo.svg/120px-Bolton_Wanderers_FC_logo.svg.png",
    "Chelsea": "https://upload.wikimedia.org/wikipedia/en/thumb/c/cc/Chelsea_FC.svg/120px-Chelsea_FC.svg.png",
    "Derby County": "https://upload.wikimedia.org/wikipedia/en/thumb/4/4c/Derby_County_crest.svg/120px-Derby_County_crest.svg.png",
    "Everton": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7c/Everton_FC_logo.svg/120px-Everton_FC_logo.svg.png",
    "Fulham": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Fulham_FC_%28shield%29.svg/120px-Fulham_FC_%28shield%29.svg.png",
    "Liverpool": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0c/Liverpool_FC.svg/120px-Liverpool_FC.svg.png",
    "Manchester City": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/120px-Manchester_City_FC_badge.svg.png",
    "Manchester United": "https://upload.wikimedia.org/wikipedia/en/thumb/7/7a/Manchester_United_FC_crest.svg/120px-Manchester_United_FC_crest.svg.png",
    "Middlesbrough": "https://upload.wikimedia.org/wikipedia/en/thumb/2/2c/Middlesbrough_FC_crest.svg/120px-Middlesbrough_FC_crest.svg.png",
    "Newcastle United": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Newcastle_United_Logo.svg/120px-Newcastle_United_Logo.svg.png",
    "Portsmouth": "https://upload.wikimedia.org/wikipedia/en/thumb/4/40/Portsmouth_FC_crest.svg/120px-Portsmouth_FC_crest.svg.png",
    "Reading": "https://upload.wikimedia.org/wikipedia/en/thumb/1/11/Reading_FC.svg/120px-Reading_FC.svg.png",
    "Sunderland": "https://upload.wikimedia.org/wikipedia/en/thumb/2/2b/Sunderland_AFC_crest.svg/120px-Sunderland_AFC_crest.svg.png",
    "Tottenham Hotspur": "https://upload.wikimedia.org/wikipedia/en/thumb/b/b4/Tottenham_Hotspur.svg/120px-Tottenham_Hotspur.svg.png",
    "West Ham United": "https://upload.wikimedia.org/wikipedia/en/thumb/c/c2/West_Ham_United_FC_badge.svg/120px-West_Ham_United_FC_badge.svg.png",
    "Wigan Athletic": "https://upload.wikimedia.org/wikipedia/en/thumb/4/43/Wigan_Athletic.svg/120px-Wigan_Athletic.svg.png"
}

# Генерация случайных данных для игры
def generate_game_data(team_name):
    import random
    
    # Используем реальный состав команды из сезона 2007-08 с рейтингами FIFA 08
    squad = []
    if team_name in SQUADS_2007_08:
        for player_data in SQUADS_2007_08[team_name]:
            if isinstance(player_data, tuple):
                player_name, rating = player_data
            else:
                # Fallback для старых данных
                player_name = player_data
                rating = 70
            squad.append({
                "name": player_name,
                "rating": rating
            })
    else:
        # Fallback на случайные имена, если команда не найдена
        first_names = ["John", "James", "Michael", "David", "Robert"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        for i in range(25):
            squad.append({
                "name": f"{random.choice(first_names)} {random.choice(last_names)}",
                "rating": random.randint(65, 85)
            })
    
    # Генерируем турнирную таблицу - все команды начинают с 0 очков
    table = []
    for team in TEAMS:
        table.append({
            "team": team,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "points": 0
        })
    
    # Сортируем по очкам
    table.sort(key=lambda x: x["points"], reverse=True)
    
    # Находим позицию команды
    position = next(i for i, t in enumerate(table, 1) if t["team"] == team_name)
    
    # Определяем текущий тур и следующего соперника по календарю
    current_round = session.get('current_round', 1)
    next_opponent = None
    is_home_match = True  # По умолчанию дома

    # Определяем какой календарь использовать
    active_schedule = session.get('custom_schedule', MATCH_SCHEDULE)

    # Ищем матч с участием нашей команды в текущем туре
    if current_round <= len(active_schedule):
        round_matches = active_schedule[current_round - 1]
        for home, away in round_matches:
            if home == team_name:
                next_opponent = away
                is_home_match = True
                break
            elif away == team_name:
                next_opponent = home
                is_home_match = False
                break

    # Если команда не играет в этом туре (все 38 туров сыграны), начинаем новый сезон
    if not next_opponent and current_round > len(active_schedule):
        # Сбрасываем сезон - генерируем новый календарь
        new_schedule = generate_full_schedule()
        # Сохраняем новый календарь в сессии для этого пользователя
        session['custom_schedule'] = new_schedule
        session['current_round'] = 1
        current_round = 1
        game_data['current_round'] = 1

        # Сбрасываем таблицу
        table = []
        for team in TEAMS:
            table.append({
                "team": team,
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "points": 0
            })

        # Ищем матч в первом туре нового сезона
        round_matches = new_schedule[0]
        for home, away in round_matches:
            if home == team_name:
                next_opponent = away
                is_home_match = True
                break
            elif away == team_name:
                next_opponent = home
                is_home_match = False
                break

    # Если все еще не нашли (редкий случай), выбираем случайного соперника
    if not next_opponent:
        next_opponent = random.choice([t for t in TEAMS if t != team_name])
    
    # Получаем название стадиона
    stadium_name = STADIUMS_2007_08.get(team_name, f"{team_name} Stadium")
    
    # Получаем вместимость стадиона
    total_capacity = STADIUM_CAPACITIES_2007_08.get(team_name, 30000)
    
    # Распределяем вместимость по трибунам (примерно поровну с небольшими вариациями)
    base_capacity = total_capacity // 4
    variation = int(total_capacity * 0.1)  # 10% вариация
    stadium_capacity = {
        "north": base_capacity + random.randint(-variation, variation),
        "south": base_capacity + random.randint(-variation, variation),
        "west": base_capacity + random.randint(-variation, variation),
        "east": base_capacity + random.randint(-variation, variation)
    }
    # Корректируем, чтобы сумма была близка к общей вместимости
    current_sum = sum(stadium_capacity.values())
    if current_sum != total_capacity:
        diff = total_capacity - current_sum
        stadium_capacity["north"] += diff // 4
        stadium_capacity["south"] += diff // 4
        stadium_capacity["west"] += diff // 4
        stadium_capacity["east"] += diff - (diff // 4) * 3
    
    ticket_price = random.randint(20, 50)
    
    # Генерируем финансовые данные
    match_revenue = random.randint(50000, 200000)
    tv_revenue = random.randint(100000, 500000)
    sponsor_revenue = random.randint(200000, 800000)
    player_wages = random.randint(300000, 800000)
    coach_wage = random.randint(50000, 150000)
    debts = random.randint(0, 500000)
    
    total_income = match_revenue + tv_revenue + sponsor_revenue
    total_expenses = player_wages + coach_wage + debts
    bank_balance = total_income - total_expenses + random.randint(1000000, 5000000)
    
    # Инициализируем выбранный состав (пустой список)
    selected_players = []

    # Получаем очки выбранной команды (всегда 0 при старте)
    points = 0

    return {
        "team_name": team_name,
        "division": "Premier League",
        "position": position,
        "points": points,
        "stadium": stadium_name,
        "finances": bank_balance,
        "next_opponent": next_opponent,
        "is_home_match": is_home_match,
        "squad": squad,
        "selected_players": selected_players,
        "table": table,
        "current_round": current_round,
        "stadium_data": {
            "north": stadium_capacity["north"],
            "south": stadium_capacity["south"],
            "west": stadium_capacity["west"],
            "east": stadium_capacity["east"],
            "total": total_capacity,
            "ticket_price": ticket_price
        },
        "finances_data": {
            "match_revenue": match_revenue,
            "tv_revenue": tv_revenue,
            "sponsor_revenue": sponsor_revenue,
            "player_wages": player_wages,
            "coach_wage": coach_wage,
            "debts": debts,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "bank_balance": bank_balance
        }
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/new_game')
def new_game():
    # Создаем список команд с логотипами
    teams_with_logos = []
    for team in TEAMS:
        # Используем основной логотип, если не работает - запасной
        logo_url = TEAM_LOGOS.get(team, '')
        if not logo_url:
            logo_url = TEAM_LOGOS_FALLBACK.get(team, '')

        teams_with_logos.append({
            'name': team,
            'logo': logo_url
        })

    print(f"Всего команд в TEAMS: {len(TEAMS)}")
    print(f"Передаю {len(teams_with_logos)} команд в шаблон")
    print(f"Команды: {[t['name'] for t in teams_with_logos[:5]]}...")  # Первые 5 для проверки
    return render_template('select_team.html', teams=teams_with_logos)

@app.route('/start_game', methods=['POST'])
def start_game():
    team_name = request.form.get('team')
    if team_name not in TEAMS:
        return redirect(url_for('new_game'))

    # Очищаем старые данные тура для новой игры
    session.pop('current_round', None)
    session.pop('custom_schedule', None)

    game_data = generate_game_data(team_name)
    session['game_data'] = game_data
    session['current_round'] = game_data['current_round']

    return redirect(url_for('game_page', page=1))

@app.route('/game/<int:page>')
def game_page(page):
    if 'game_data' not in session:
        return redirect(url_for('index'))
    
    game_data = session['game_data']
    
    # Убеждаемся, что selected_players всегда определен
    if 'selected_players' not in game_data:
        game_data['selected_players'] = []
        session['game_data'] = game_data
    
    # Для страницы состава: если нет выбранных игроков, берем первых 11
    if page == 3:
        if not game_data.get('selected_players'):
            game_data['selected_players'] = [p['name'] for p in game_data['squad'][:11]]
            session['game_data'] = game_data
    
    if page == 1:
        return render_template('game_page1.html', data=game_data)
    elif page == 2:
        return render_template('game_page2.html', data=game_data)
    elif page == 3:
        return render_template('game_page3.html', data=game_data)
    elif page == 4:
        return render_template('game_page4.html', data=game_data)
    elif page == 5:
        return render_template('game_page5.html', data=game_data)
    else:
        return redirect(url_for('game_page', page=1))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/save_game', methods=['POST'])
def save_game():
    if 'game_data' not in session:
        return jsonify({"success": False, "message": "Нет данных для сохранения"})
    
    save_dir = 'saves'
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{save_dir}/save_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(session['game_data'], f, ensure_ascii=False, indent=2)
    
    return jsonify({"success": True, "message": "Игра сохранена!"})

@app.route('/load_game')
def load_game():
    save_dir = 'saves'
    if not os.path.exists(save_dir):
        return render_template('load_game.html', saves=[])
    
    saves = []
    for filename in os.listdir(save_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(save_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
                saves.append({
                    "filename": filename,
                    "team": save_data.get('team_name', 'Unknown'),
                    "timestamp": filename.replace('save_', '').replace('.json', '')
                })
    
    saves.sort(key=lambda x: x['timestamp'], reverse=True)
    return render_template('load_game.html', saves=saves)

@app.route('/load_game_file/<filename>')
def load_game_file(filename):
    save_dir = 'saves'
    filepath = os.path.join(save_dir, filename)
    
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            game_data = json.load(f)
        # Инициализируем selected_players, если его нет в сохранении
        if 'selected_players' not in game_data:
            game_data['selected_players'] = []
        session['game_data'] = game_data
        session['current_round'] = game_data.get('current_round', 1)
        return redirect(url_for('game_page', page=1))
    else:
        return redirect(url_for('load_game'))

@app.route('/update_lineup', methods=['POST'])
def update_lineup():
    if 'game_data' not in session:
        return jsonify({"success": False, "message": "Нет данных игры"})
    
    data = request.json
    player_order = data.get('player_order', [])  # Список имен игроков в порядке
    
    game_data = session['game_data']
    
    # Обновляем порядок игроков (первые 11 - основной состав)
    game_data['selected_players'] = player_order[:11]
    
    session['game_data'] = game_data
    return jsonify({
        "success": True,
        "selected_count": len(game_data['selected_players']),
        "selected_players": game_data['selected_players']
    })

@app.route('/pre_match')
def pre_match():
    if 'game_data' not in session:
        return redirect(url_for('index'))
    
    import random
    from datetime import datetime, timedelta
    game_data = session['game_data']
    
    # Получаем состав своей команды
    my_team = game_data['team_name']
    my_squad = game_data['squad']
    selected_players = game_data.get('selected_players', [])
    
    # Если выбрано меньше 11 игроков, добавляем случайных
    if len(selected_players) < 11:
        available_players = [p['name'] for p in my_squad if p['name'] not in selected_players]
        needed = 11 - len(selected_players)
        selected_players.extend(random.sample(available_players, min(needed, len(available_players))))
    
    # Получаем информацию о выбранных игроках в том порядке, в котором они были расставлены
    my_lineup = []
    for i, player_name in enumerate(selected_players[:11]):
        player_info = next((p for p in my_squad if p['name'] == player_name), None)
        if player_info:
            # Определяем позицию на основе места в списке: 1=В, 2-5=З, 6-9=П, 10-11=Н
            if i == 0:
                position = 'В'  # Вратарь
            elif i >= 1 and i <= 4:
                position = 'З'  # Защитники
            elif i >= 5 and i <= 8:
                position = 'П'  # Полузащитники
            elif i >= 9 and i <= 10:
                position = 'Н'  # Нападение
            else:
                position = '-'
            
            my_lineup.append({**player_info, 'position': position})
    
    # Функция для определения позиции игрока на основе его места в реальном составе
    def get_player_position(team_name, player_index, total_players):
        """Определяет позицию игрока на основе его места в составе команды"""
        # Анализируя реальные составы команд:
        # - Индексы 0-1: вратари (обычно 2 вратаря)
        # - Индексы 2-8: защитники (обычно 7 защитников)
        # - Индексы 9-14: полузащитники (обычно 6 полузащитников)
        # - Индексы 15+: нападающие (остальные)
        if player_index < 2:
            return 'В'  # Вратари
        elif player_index < 9:
            return 'З'  # Защитники
        elif player_index < 15:
            return 'П'  # Полузащитники
        else:
            return 'Н'  # Нападающие
    
    # Генерируем состав соперника с позициями на основе реального порядка
    opponent_team = game_data['next_opponent']
    opponent_squad_with_positions = []
    if opponent_team in SQUADS_2007_08:
        for idx, player_data in enumerate(SQUADS_2007_08[opponent_team]):
            if isinstance(player_data, tuple):
                player_name, rating = player_data
            else:
                player_name = player_data
                rating = 70
            position = get_player_position(opponent_team, idx, len(SQUADS_2007_08[opponent_team]))
            opponent_squad_with_positions.append({
                "name": player_name,
                "rating": rating,
                "position": position,
                "original_index": idx
            })
    
    # Формируем базовый состав: 1 вратарь, 4 защитника, 4 полузащитника, 2 нападающих
    goalkeepers = [p for p in opponent_squad_with_positions if p['position'] == 'В']
    defenders = [p for p in opponent_squad_with_positions if p['position'] == 'З']
    midfielders = [p for p in opponent_squad_with_positions if p['position'] == 'П']
    forwards = [p for p in opponent_squad_with_positions if p['position'] == 'Н']
    
    # Сортируем по рейтингу для выбора лучших
    goalkeepers_sorted = sorted(goalkeepers, key=lambda x: x['rating'], reverse=True)
    defenders_sorted = sorted(defenders, key=lambda x: x['rating'], reverse=True)
    midfielders_sorted = sorted(midfielders, key=lambda x: x['rating'], reverse=True)
    forwards_sorted = sorted(forwards, key=lambda x: x['rating'], reverse=True)
    
    # Выбираем основной состав
    selected_gk = goalkeepers_sorted[0] if goalkeepers_sorted else None
    selected_defenders = defenders_sorted[:4] if len(defenders_sorted) >= 4 else defenders_sorted
    selected_midfielders = midfielders_sorted[:4] if len(midfielders_sorted) >= 4 else midfielders_sorted
    selected_forwards = forwards_sorted[:2] if len(forwards_sorted) >= 2 else forwards_sorted
    
    # Делаем случайные замены (1-2 игрока) - заменяем на игроков из запасных
    num_substitutions = random.randint(1, 2)
    substitutions_made = 0
    
    # Функция для получения следующего доступного игрока из списка
    def get_next_available_player(player_list, current_selection):
        selected_names = {p['name'] for p in current_selection}
        for player in player_list:
            if player['name'] not in selected_names:
                return player
        return None
    
    # Замены защитников
    if len(defenders_sorted) > 4 and substitutions_made < num_substitutions:
        if random.random() < 0.5:  # 50% шанс заменить защитника
            if selected_defenders:
                removed = random.choice(selected_defenders)
                selected_defenders.remove(removed)
                substitute = get_next_available_player(defenders_sorted, selected_defenders)
                if substitute:
                    selected_defenders.append(substitute)
                    substitutions_made += 1
                else:
                    selected_defenders.append(removed)  # Возвращаем обратно, если нет замены
    
    # Замены полузащитников
    if len(midfielders_sorted) > 4 and substitutions_made < num_substitutions:
        if random.random() < 0.5:  # 50% шанс заменить полузащитника
            if selected_midfielders:
                removed = random.choice(selected_midfielders)
                selected_midfielders.remove(removed)
                substitute = get_next_available_player(midfielders_sorted, selected_midfielders)
                if substitute:
                    selected_midfielders.append(substitute)
                    substitutions_made += 1
                else:
                    selected_midfielders.append(removed)  # Возвращаем обратно, если нет замены
    
    # Замены нападающих
    if len(forwards_sorted) > 2 and substitutions_made < num_substitutions:
        if random.random() < 0.5:  # 50% шанс заменить нападающего
            if selected_forwards:
                removed = random.choice(selected_forwards)
                selected_forwards.remove(removed)
                substitute = get_next_available_player(forwards_sorted, selected_forwards)
                if substitute:
                    selected_forwards.append(substitute)
                    substitutions_made += 1
                else:
                    selected_forwards.append(removed)  # Возвращаем обратно, если нет замены
    
    # Формируем финальный состав в правильном порядке: В, З, З, З, З, П, П, П, П, Н, Н
    opponent_lineup = []
    if selected_gk:
        opponent_lineup.append({**selected_gk, 'position': 'В'})
    
    # Защитники (4)
    for i in range(min(4, len(selected_defenders))):
        opponent_lineup.append({**selected_defenders[i], 'position': 'З'})
    
    # Полузащитники (4)
    for i in range(min(4, len(selected_midfielders))):
        opponent_lineup.append({**selected_midfielders[i], 'position': 'П'})
    
    # Нападающие (2)
    for i in range(min(2, len(selected_forwards))):
        opponent_lineup.append({**selected_forwards[i], 'position': 'Н'})
    
    # Проверяем на дубликаты и убираем их
    seen_names = set()
    opponent_lineup_unique = []
    for player in opponent_lineup:
        if player['name'] not in seen_names:
            opponent_lineup_unique.append(player)
            seen_names.add(player['name'])
    opponent_lineup = opponent_lineup_unique
    
    # Если не хватает игроков до 11, дополняем из запасных той же позиции
    while len(opponent_lineup) < 11:
        lineup_names = {p['name'] for p in opponent_lineup}
        added = False
        
        if not selected_gk and goalkeepers_sorted:
            for gk in goalkeepers_sorted:
                if gk['name'] not in lineup_names:
                    opponent_lineup.insert(0, {**gk, 'position': 'В'})
                    added = True
                    break
        
        if not added and len(opponent_lineup) <= 4:
            for defender in defenders_sorted:
                if defender['name'] not in lineup_names:
                    opponent_lineup.append({**defender, 'position': 'З'})
                    added = True
                    break
        
        if not added and len(opponent_lineup) <= 8:
            for midfielder in midfielders_sorted:
                if midfielder['name'] not in lineup_names:
                    opponent_lineup.append({**midfielder, 'position': 'П'})
                    added = True
                    break
        
        if not added and len(opponent_lineup) <= 10:
            for forward in forwards_sorted:
                if forward['name'] not in lineup_names:
                    opponent_lineup.append({**forward, 'position': 'Н'})
                    added = True
                    break
        
        if not added:
            break
    
    # Генерируем информацию о матче
    stadium_name = game_data.get('stadium', f"{my_team} Stadium")
    stadium_capacity = game_data.get('stadium_data', {}).get('total', 50000)
    
    # Время начала матча (случайное между 15:00 и 20:00)
    match_hour = random.randint(15, 20)
    match_time = f"{match_hour}:00"
    
    # Посещаемость (70-95% от вместимости)
    attendance_percent = random.randint(70, 95)
    attendance = int(stadium_capacity * attendance_percent / 100)
    
    return render_template('pre_match.html',
                         my_team=my_team,
                         opponent_team=opponent_team,
                         my_lineup=my_lineup,
                         opponent_lineup=opponent_lineup,
                         stadium_name=stadium_name,
                         match_time=match_time,
                         attendance=attendance,
                         stadium_capacity=stadium_capacity,
                         TEAM_LOGOS=TEAM_LOGOS,
                         TEAM_LOGOS_FALLBACK=TEAM_LOGOS_FALLBACK)

@app.route('/match')
def match():
    if 'game_data' not in session:
        return redirect(url_for('index'))
    
    import random
    game_data = session['game_data']
    
    my_team = game_data['team_name']
    opponent_team = game_data['next_opponent']
    
    # Получаем составы
    my_squad = game_data['squad']
    selected_players = game_data.get('selected_players', [])
    
    # Если выбрано меньше 11 игроков, добавляем случайных
    if len(selected_players) < 11:
        available_players = [p['name'] for p in my_squad if p['name'] not in selected_players]
        needed = 11 - len(selected_players)
        selected_players.extend(random.sample(available_players, min(needed, len(available_players))))
    
    my_lineup = []
    for player_name in selected_players[:11]:
        player_info = next((p for p in my_squad if p['name'] == player_name), None)
        if player_info:
            my_lineup.append(player_info)
    
    # Генерируем состав соперника
    opponent_squad = []
    if opponent_team in SQUADS_2007_08:
        for player_data in SQUADS_2007_08[opponent_team]:
            if isinstance(player_data, tuple):
                player_name, rating = player_data
            else:
                player_name = player_data
                rating = 70
            opponent_squad.append({
                "name": player_name,
                "rating": rating
            })
    
    opponent_squad_sorted = sorted(opponent_squad, key=lambda x: x['rating'], reverse=True)
    opponent_lineup = opponent_squad_sorted[:11]
    
    # Всегда создаем новые данные матча при заходе на страницу матча
    # Это гарантирует, что матч начинается с нуля
    session['match_data'] = {
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
    
    match_data = session['match_data']
    
    # Вычисляем проценты для статистики
    total_shots = max(match_data['shots_my'] + match_data['shots_opponent'], 1)
    shots_my_percent = (match_data['shots_my'] / total_shots) * 100
    shots_opponent_percent = (match_data['shots_opponent'] / total_shots) * 100
    
    total_shots_on_target = max(match_data['shots_on_target_my'] + match_data['shots_on_target_opponent'], 1)
    shots_on_target_my_percent = (match_data['shots_on_target_my'] / total_shots_on_target) * 100
    shots_on_target_opponent_percent = (match_data['shots_on_target_opponent'] / total_shots_on_target) * 100
    
    total_xg = max(match_data['xg_my'] + match_data['xg_opponent'], 0.1)
    xg_my_percent = (match_data['xg_my'] / total_xg) * 100
    xg_opponent_percent = (match_data['xg_opponent'] / total_xg) * 100
    
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

@app.route('/match_action', methods=['POST'])
def match_action():
    # Расширяем try блок на всю функцию для перехвата всех исключений
    try:
        # Проверяем наличие необходимых данных в сессии
        if 'game_data' not in session or 'match_data' not in session:
            return jsonify({"success": False, "error": "Session not initialized"})

        import random

        # Безопасно получаем JSON данные
        try:
            data = request.get_json()
        except Exception as e:
            return jsonify({"success": False, "error": f"Invalid JSON: {str(e)}"})

        if not data:
            return jsonify({"success": False, "error": "No data provided"})

        action = data.get('action')
        if not action:
            return jsonify({"success": False, "error": "No action provided"})

        match_data = session['match_data']
        game_data = session['game_data']

        if action == 'tick':
            # Получаем составы команд (нужно для определения бомбардиров)
            my_team = game_data['team_name']
            opponent_team = game_data['next_opponent']

            # Получаем состав пользователя
            my_squad = game_data['squad']
            selected_players = game_data.get('selected_players', [])

            # Если выбрано меньше 11 игроков, добавляем случайных
            if len(selected_players) < 11:
                available_players = [p['name'] for p in my_squad if p['name'] not in selected_players]
                needed = 11 - len(selected_players)
                selected_players.extend(random.sample(available_players, min(needed, len(available_players))))

            my_lineup = []
            for player_name in selected_players[:11]:
                player_info = next((p for p in my_squad if p['name'] == player_name), None)
                if player_info:
                    my_lineup.append(player_info)

            # Генерируем состав соперника
            opponent_squad = []
            if opponent_team in SQUADS_2007_08:
                for player_data in SQUADS_2007_08[opponent_team]:
                    if isinstance(player_data, tuple):
                        player_name, rating = player_data
                    else:
                        player_name = player_data
                        rating = 70
                    opponent_squad.append({
                        "name": player_name,
                        "rating": rating
                    })

            opponent_squad_sorted = sorted(opponent_squad, key=lambda x: x['rating'], reverse=True)
            opponent_lineup = opponent_squad_sorted[:11]
            # Обновление таймера
            minute = data.get('minute', 0)
            half = data.get('half', 1)

            match_data['minute'] = minute
            match_data['half'] = half

            # Генерируем события (голы, статистика) - каждую секунду
            # Владение - медленно меняется
            if minute % 5 == 0:
                match_data['possession_my'] = max(30, min(70, match_data['possession_my'] + random.randint(-2, 2)))
                match_data['possession_opponent'] = 100 - match_data['possession_my']

            # Удары - случайно (увеличена вероятность)
            if random.random() < 0.12:  # 12% вероятность каждую секунду
                if random.random() < 0.5:
                    match_data['shots_my'] += 1
                    if random.random() < 0.5:  # 50% попаданий в створ
                        match_data['shots_on_target_my'] += 1
                        match_data['xg_my'] += round(random.uniform(0.08, 0.25), 2)
                else:
                    match_data['shots_opponent'] += 1
                    if random.random() < 0.5:  # 50% попаданий в створ
                        match_data['shots_on_target_opponent'] += 1
                        match_data['xg_opponent'] += round(random.uniform(0.08, 0.25), 2)

            # Голы (вероятность зависит от xG и накопленного xG) - увеличена вероятность
            goal_prob_my = min(0.08, match_data['xg_my'] * 0.4)  # Максимум 8% в секунду
            if random.random() < goal_prob_my and match_data['xg_my'] > 0.15:  # Минимальный порог снижен до 0.15
                match_data['my_score'] += 1
                scorer = select_goal_scorer(game_data, my_lineup)
                if not scorer or scorer == "":
                    scorer = "Неизвестный игрок"  # Fallback
                match_data['goals'].append({
                    'team': match_data['my_team'],
                    'scorer': scorer,
                    'minute': minute
                })
                match_data['xg_my'] = 0.0  # Сбрасываем после гола

            goal_prob_opp = min(0.08, match_data['xg_opponent'] * 0.4)  # Максимум 8% в секунду
            if random.random() < goal_prob_opp and match_data['xg_opponent'] > 0.15:  # Минимальный порог снижен до 0.15
                match_data['opponent_score'] += 1
                scorer = select_opponent_goal_scorer(match_data['opponent_team'], opponent_lineup)
                if not scorer or scorer == "":
                    scorer = "Неизвестный игрок"  # Fallback
                match_data['goals'].append({
                    'team': match_data['opponent_team'],
                    'scorer': scorer,
                    'minute': minute
                })
                match_data['xg_opponent'] = 0.0

            # Сохраняем обновленные данные матча в сессии
            session['match_data'] = match_data
            return jsonify({"success": True, "match_data": match_data})

        elif action == 'start_second_half':
            match_data['half'] = 2
            match_data['minute'] = 46
            session['match_data'] = match_data
            return jsonify({"success": True, "match_data": match_data})

        elif action == 'end_match':
            # Сохраняем результаты всего тура
            if 'match_results' not in session:
                session['match_results'] = []

            current_round = game_data.get('current_round', 1)
            round_results = []

            # Добавляем результат нашего матча
            my_result = {
                'home_team': match_data['my_team'],
                'away_team': match_data['opponent_team'],
                'home_score': match_data['my_score'],
                'away_score': match_data['opponent_score'],
                'goals': match_data['goals'],
                'is_user_match': True
            }
            round_results.append(my_result)

            # Генерируем результаты остальных матчей тура
            active_schedule = session.get('custom_schedule', MATCH_SCHEDULE)
            if current_round <= len(active_schedule):
                round_matches = active_schedule[current_round - 1]
                for home, away in round_matches:
                    # Пропускаем наш матч, он уже добавлен
                    if (home == match_data['my_team'] and away == match_data['opponent_team']) or \
                       (away == match_data['my_team'] and home == match_data['opponent_team']):
                        continue

                    # Генерируем более реалистичный результат на основе рейтингов команд
                    home_rating = get_team_average_rating(home)
                    away_rating = get_team_average_rating(away)

                    # Вероятность победы зависит от разницы рейтингов
                    rating_diff = home_rating - away_rating
                    home_win_prob = 0.5 + (rating_diff / 20)  # Максимум ±0.25 от 0.5
                    home_win_prob = max(0.2, min(0.8, home_win_prob))

                    if random.random() < home_win_prob:
                        # Выигрывает хозяин
                        home_score = random.randint(1, 3)
                        away_score = random.randint(0, home_score - 1)
                    else:
                        # Выигрывает гость или ничья
                        if random.random() < 0.6:  # 60% шанс на победу гостя
                            away_score = random.randint(1, 3)
                            home_score = random.randint(0, away_score - 1)
                        else:  # Ничья
                            home_score = random.randint(0, 2)
                            away_score = random.randint(max(0, home_score - 1), home_score + 1)

                    # Генерируем бомбардиров для матча
                    goals = []
                    home_goals_left = home_score
                    away_goals_left = away_score

                    # Получаем составы команд для генерации бомбардиров
                    home_squad = []
                    away_squad = []
                    if home in SQUADS_2007_08:
                        for player_data in SQUADS_2007_08[home]:
                            if isinstance(player_data, tuple):
                                home_squad.append({"name": player_data[0], "rating": player_data[1]})
                            else:
                                home_squad.append({"name": player_data, "rating": 70})
                    if away in SQUADS_2007_08:
                        for player_data in SQUADS_2007_08[away]:
                            if isinstance(player_data, tuple):
                                away_squad.append({"name": player_data[0], "rating": player_data[1]})
                            else:
                                away_squad.append({"name": player_data, "rating": 70})

                    # Генерируем голы для домашней команды
                    for _ in range(home_goals_left):
                        if home_squad:
                            scorer = select_goal_scorer({"team_name": home}, home_squad)
                            goals.append({
                                'team': home,
                                'scorer': scorer,
                                'minute': random.randint(1, 90)
                            })

                    # Генерируем голы для гостевой команды
                    for _ in range(away_goals_left):
                        if away_squad:
                            scorer = select_opponent_goal_scorer(away, away_squad)
                            goals.append({
                                'team': away,
                                'scorer': scorer,
                                'minute': random.randint(1, 90)
                            })

                    round_results.append({
                        'home_team': home,
                        'away_team': away,
                        'home_score': home_score,
                        'away_score': away_score,
                        'goals': goals,
                        'is_user_match': False
                    })

            session['match_results'] = round_results

            # Обновляем турнирную таблицу
            update_league_table(round_results)

            # Увеличиваем тур для следующего матча
            new_round = current_round + 1
            session['current_round'] = new_round
            game_data['current_round'] = new_round

            # Определяем следующего соперника для нового тура
            active_schedule = session.get('custom_schedule', MATCH_SCHEDULE)
            next_opponent = None
            next_is_home_match = True
            if new_round <= len(active_schedule):
                round_matches = active_schedule[new_round - 1]
                my_team = game_data['team_name']
                for home, away in round_matches:
                    if home == my_team:
                        next_opponent = away
                        next_is_home_match = True
                        break
                    elif away == my_team:
                        next_opponent = home
                        next_is_home_match = False
                        break

            # Если матчи закончились, следующий соперник будет определен при сбросе сезона
            if next_opponent:
                game_data['next_opponent'] = next_opponent
                game_data['is_home_match'] = next_is_home_match

            # Проверяем, был ли это последний тур чемпионата
            is_season_end = (new_round > 38)

            # Очищаем данные матча
            session.pop('match_data', None)

            # Если это был последний тур, получаем итоговую позицию команды
            if is_season_end:
                final_position = None
                for team in game_data['table']:
                    if team['team'] == game_data['team_name']:
                        final_position = team['position']
                        break
                session['season_end_data'] = {
                    'final_position': final_position,
                    'team_name': game_data['team_name']
                }

            session['match_data'] = match_data
            response_data = {"success": True, "match_data": match_data}
            if is_season_end:
                response_data["season_end"] = True
                response_data["season_end_data"] = session['season_end_data']
            return jsonify(response_data)

        else:
            # Неизвестное действие
            return jsonify({"success": False, "error": f"Unknown action: {action}"})

    except Exception as e:
        print(f"Error in match_action: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

@app.route('/match_results')
def match_results():
    if 'match_results' not in session:
        return redirect(url_for('game_page', page=1))

    results = session['match_results']
    return render_template('match_results.html', results=results)

@app.route('/top_scorers')
def top_scorers():
    if 'game_data' not in session:
        return redirect(url_for('index'))

    game_data = session['game_data']

    # Собираем статистику бомбардиров из всех результатов матчей
    scorers_stats = {}

    # Проверяем сохраненные результаты матчей
    if 'match_results' in session:
        for result in session['match_results']:
            if 'goals' in result:
                for goal in result['goals']:
                    scorer_name = goal['scorer']
                    team_name = goal['team']

                    if scorer_name not in scorers_stats:
                        scorers_stats[scorer_name] = {
                            'name': scorer_name,
                            'team': team_name,
                            'goals': 0
                        }
                    scorers_stats[scorer_name]['goals'] += 1

    # Преобразуем в список и сортируем по количеству голов
    scorers_list = list(scorers_stats.values())
    scorers_list.sort(key=lambda x: x['goals'], reverse=True)

    # Берем топ-20 бомбардиров
    top_scorers_list = scorers_list[:20]

    return render_template('top_scorers.html', scorers=top_scorers_list)

@app.route('/favicon.ico')
def favicon():
    return '', 204  # No Content

# Глобальный обработчик ошибок для match_action маршрута
@app.errorhandler(500)
def handle_500(error):
    # Проверяем, является ли запрос к match_action
    if request.path == '/match_action':
        print(f"Global 500 error handler for match_action: {error}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": "Internal server error"})
    # Для других маршрутов возвращаем стандартную ошибку
    return error

if __name__ == '__main__':
    app.run(debug=True)

