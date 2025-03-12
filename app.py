import requests
import pandas as pd
import time
from flask import Flask, render_template_string, request

app = Flask(__name__)

# Constants
RESULTS_PER_PAGE = 25
CACHE_EXPIRATION = 500
LOW_SCORE_THRESHOLD = 100000  # New constant for vote-off calculation

# Cache variables
cached_leaderboard = None
last_updated = 0

# Fetch leaderboard (with caching)
def fetch_leaderboard():
    global cached_leaderboard, last_updated

    # Only fetch new data if cache is expired
    if time.time() - last_updated > CACHE_EXPIRATION:
        print("Fetching new leaderboard data...")  # Debugging
        url = "https://www.cryptothegame.com/api/trpc/event.getProgress?batch=1&input=%7B%220%22%3A%7B%22json%22%3A%7B%22eventId%22%3A%22points%3Afd0206c5-3eb3-4ffb-a399-9f6212441495%22%7D%7D%7D"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            try:
                cached_leaderboard = data[0]["result"]["data"]["json"]["leaderboard"]
                last_updated = time.time()  # Update cache time
            except KeyError:
                print("Error: JSON structure changed")
                cached_leaderboard = []
        else:
            print(f"Failed to fetch data: {response.status_code}")
            cached_leaderboard = []

    return cached_leaderboard

# Process leaderboard (sorting, filtering, pagination)
from datetime import datetime

def process_leaderboard(leaderboard, sort_by="highScore", ascending=False, tribe=None, page=1):
    if not leaderboard:
        return None, 0

    df = pd.DataFrame(leaderboard)

    # Handle playerAddress for compatibility with existing code
    if 'playerAddress' in df.columns and 'address' not in df.columns:
        # Rename the column instead of creating a duplicate
        df = df.rename(columns={'playerAddress': 'address'})

    # Convert highScoreAchievedAt to time-only format (HH:MM AM/PM)
    if 'highScoreAchievedAt' in df.columns:
        df['highScoreAchievedAt'] = df['highScoreAchievedAt'].apply(
            lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%I:%M %p") if isinstance(x, str) else "N/A"
        )

    # Filter by tribe if specified
    if tribe:
        df = df[df["tribe"] == tribe]

    # Sort data
    df_sorted = df.sort_values(by=sort_by, ascending=ascending)

    # Pagination logic
    total_results = len(df_sorted)
    start_idx = (page - 1) * RESULTS_PER_PAGE
    end_idx = start_idx + RESULTS_PER_PAGE
    df_paginated = df_sorted.iloc[start_idx:end_idx]

    return df_paginated, total_results

def calculate_tribe_stats(tribe):
    # Get the full dataset
    full_data = fetch_leaderboard()
    if not full_data or len(full_data) == 0:
        return "0% (0/0)", "0"

    # Convert to DataFrame
    df = pd.DataFrame(full_data)

    # Check if "tribe" column exists
    if "tribe" not in df.columns:
        return "0% (0/0)", "0"

    # Filter by tribe
    df = df[df["tribe"] == tribe]

    # If no players in this tribe, return safe values
    if df.empty:
        return "0% (0/0)", "0"

    # Count players
    total_players = len(df)
    players_with_score = df[df["highScore"] > 0].shape[0]

    # Calculate percentage of players with a score
    percentage_scored = (players_with_score / total_players) * 100 if total_players > 0 else 0
    percentage_text = f"{percentage_scored:.1f}% ({players_with_score}/{total_players})"

    # Calculate average score (even if some players have 0)
    average_score = df["highScore"].mean()
    average_score_text = f"{average_score:,.0f}" if not pd.isna(average_score) else "0"

    return percentage_text, average_score_text

# Define hardcoded tribe colors (10% opacity for rows, 100% for buttons)
tribe_colors = {
    "red": {"row": "rgba(255, 0, 0, 0.2)", "button": "rgb(255, 0, 0)"},
    "orange": {"row": "rgba(255, 165, 0, 0.2)", "button": "rgb(255, 165, 0)"},
    "yellow": {"row": "rgba(255, 255, 0, 0.2)", "button": "rgb(255, 255, 0)"},
    "green": {"row": "rgba(0, 128, 0, 0.2)", "button": "rgb(0, 128, 0)"},
    "blue": {"row": "rgba(0, 0, 255, 0.2)", "button": "rgb(0, 0, 255)"},
    "aqua": {"row": "rgba(0, 255, 255, 0.2)", "button": "rgb(0, 255, 255)"},
    "purple": {"row": "rgba(128, 0, 128, 0.2)", "button": "rgb(128, 0, 128)"},
    "gold": {"row": "rgba(255, 215, 0, 0.2)", "button": "rgb(255, 215, 0)"},
    "silver": {"row": "rgba(192, 192, 192, 0.2)", "button": "rgb(192, 192, 192)"},
    "pink": {"row": "rgba(255, 192, 203, 0.2)", "button": "rgb(255, 192, 203)"}
}

def generate_html_table(df):
    table_html = "<table class='table table-striped'><thead><tr>"
    for col in df.columns:
        table_html += f"<th>{col}</th>"
    table_html += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        tribe = row["tribe"]
        row_color = tribe_colors.get(tribe, {"row": "rgba(0,0,0,0.05)"}).get("row")  # Default light grey
        table_html += f"<tr style='background-color:{row_color}'>"

        for col in df.columns:
            table_html += f"<td>{row[col]}</td>"

        table_html += "</tr>"

    table_html += "</tbody></table>"
    return table_html

def generate_tribe_buttons():
    buttons_html = '<div class="mb-3">'
    for tribe, colors in tribe_colors.items():
        buttons_html += f'<a href="/tribe/{tribe}" class="btn" style="background-color: {colors["button"]}; color: white; margin: 5px;">{tribe.capitalize()} Tribe</a>'
    buttons_html += '</div>'
    return buttons_html

def generate_sort_buttons(base_url):
    return f'''
        <a href="{base_url}?sort_by=highScore&order=asc" class="btn btn-secondary">Sort by High Score (Asc)</a>
        <a href="{base_url}?sort_by=highScore&order=desc" class="btn btn-secondary">Sort by High Score (Desc)</a>
    '''

def calculate_team_leaderboard():
    global cached_leaderboard

    # If the cached leaderboard is empty or None, return an empty DataFrame
    if not cached_leaderboard or len(cached_leaderboard) == 0:
        return pd.DataFrame(columns=["tribe", "average_score"])

    df = pd.DataFrame(cached_leaderboard)

    # Group by tribe and calculate the average score per team
    team_stats = df.groupby("tribe").agg(
        average_score=("highScore", "mean")  # Average score across all players in the tribe
    ).reset_index()

    # Format scores nicely
    team_stats["average_score"] = team_stats["average_score"].apply(lambda x: f"{x:,.0f}" if not pd.isna(x) else "0")

    # Sort teams by average score (descending)
    team_stats = team_stats.sort_values(by="average_score", ascending=False)

    return team_stats

def calculate_vote_off_list(tribe):
    full_data = fetch_leaderboard()  # Get the full leaderboard
    if not full_data:
        return []

    df = pd.DataFrame(full_data)

    # Ensure required columns exist
    address_col = "playerAddress" if "playerAddress" in df.columns else "address"
    if "tribe" not in df.columns or address_col not in df.columns:
        return []

    # Filter by tribe
    df = df[df["tribe"] == tribe]

    # Find players with scores below threshold (0 or less than 100,000)
    df = df[df["highScore"] < LOW_SCORE_THRESHOLD]

    # Sort by score (ascending)
    df = df.sort_values(by="highScore", ascending=True)

    # Extract player IDs safely
    df["player_id"] = df[address_col].apply(lambda x: x.split(":")[-1] if ":" in str(x) else "Unknown")

    # Create a list of tuples with player_id and highScore
    return [(player, score) for player, score in zip(df["player_id"].tolist(), df["highScore"].tolist())]

# Main leaderboard route
@app.route('/')
def leaderboard():
    sort_by = request.args.get("sort_by", "highScore")
    order = request.args.get("order", "desc")
    page = int(request.args.get("page", 1))
    ascending = order == "asc"

    data = fetch_leaderboard()
    df_sorted, total_results = process_leaderboard(data, sort_by, ascending, page=page)

    if df_sorted is None:
        return "<h1>No leaderboard data available.</h1>"

    table_html = generate_html_table(df_sorted)
    total_pages = (total_results // RESULTS_PER_PAGE) + (1 if total_results % RESULTS_PER_PAGE > 0 else 0)
    tribe_buttons = generate_tribe_buttons()

    html = f'''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
        <title>Leaderboard - Sorted by {sort_by} ({order.upper()})</title>
    </head>
    <body>
        <div class="container">
        <div class="d-flex flex-wrap align-items-center">
            <h1 class="mt-4 mb-4">Individual Leaderboard</h1><br>
             <a href="/teams" class="btn btn-info ml-4">View Team Leaderboard</a><br>
             </div>
             <h3>Tribe Leaderboards</h3>
            {tribe_buttons}
            <div class="d-flex flex-wrap align-items-center justify-content-end">
            <div class="mr-2"><small>Last Updated: {time.strftime('%I:%M %p', time.localtime(last_updated))}</small></div>
            <div>
                <a href="/" class="btn btn-success">Refresh</a>
            </div>
            </div>
            <br>
            {table_html}
            <br>
            <div>
                Page: {page} of {total_pages} &nbsp;
                {" | ".join(f'<a href="?sort_by={sort_by}&order={order}&page={p}" class="btn btn-sm btn-outline-dark">{p}</a>' for p in range(1, total_pages + 1))}
            </div>
            <hr>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/tribe/<tribe>')
def tribe_leaderboard(tribe):
    sort_by = request.args.get("sort_by", "highScore")
    order = request.args.get("order", "desc")
    page = int(request.args.get("page", 1))
    ascending = order == "asc"

    data = fetch_leaderboard()

    # Get full tribe stats BEFORE pagination
    percentage_scored, average_score = calculate_tribe_stats(tribe)

    # Get the vote-off list
    vote_off_list = calculate_vote_off_list(tribe)

    # Apply sorting and pagination
    df_sorted, total_results = process_leaderboard(data, sort_by, ascending, tribe, page)

    if df_sorted is None or df_sorted.empty:
        return f"<h1>No data for {tribe.capitalize()} Tribe.</h1>"

    table_html = generate_html_table(df_sorted)
    total_pages = (total_results // RESULTS_PER_PAGE) + (1 if total_results % RESULTS_PER_PAGE > 0 else 0)
    tribe_buttons = generate_tribe_buttons()
    sort_buttons = generate_sort_buttons(f"/tribe/{tribe}")

    html = f'''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
        <a href="/" class="btn btn-dark">Back to Main Leaderboard</a>
        <title>{tribe.capitalize()} Tribe Leaderboard</title>
        <!-- Add Bootstrap and jQuery -->
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.bundle.min.js"></script>
    </head>
    <body>
        <div class="container">
            <h1 class="mt-4 mb-4">{tribe.capitalize()} Tribe Leaderboard</h1>
            {tribe_buttons}
            <div class="d-flex flex-wrap align-items-center justify-content-between">
            <div>
            <h4>Sorted by {sort_by} ({order.upper()})</h4>
            <h5>Percentage of Players with a Score > 0: {percentage_scored}</h5>
            <h5>Average Score (All Players): {average_score}</h5>
            </div>
            <button type="button" class="btn btn-danger mt-3" data-toggle="modal" data-target="#voteOffModal">
                Who Should I Vote Off?
            </button>
            </div>
            <br>
            {sort_buttons}
            <br><br>
            {table_html}
            <br>
            <div class="modal fade" id="voteOffModal" tabindex="-1" role="dialog" aria-labelledby="voteOffModalLabel" aria-hidden="true">
                <div class="modal-dialog" role="document">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="voteOffModalLabel">Players with Low Scores (< {LOW_SCORE_THRESHOLD:,})</h5>
                            <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                <span aria-hidden="true">&times;</span>
                            </button>
                        </div>
                        <div class="modal-body">
                            <ul class="list-group">
                                {"".join(f'<li class="list-group-item">Player {player} - Score: {score:,}</li>' for player, score in vote_off_list) if vote_off_list else "<p>No players with low scores.</p>"}
                            </ul>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html)

@app.route('/teams')
def team_leaderboard():
    team_data = calculate_team_leaderboard()

    # If team_data is empty, show a message
    if team_data.empty:
        return "<h1>No team data available.</h1>"

    table_html = "<table class='table table-striped'><thead><tr><th>Tribe</th><th>Average Score</th></tr></thead><tbody>"

    for _, row in team_data.iterrows():
        tribe = row["tribe"]
        avg_score = row["average_score"]
        row_color = tribe_colors.get(tribe, {"row": "rgba(0,0,0,0.05)"}).get("row")  # Default light grey

        table_html += f"<tr style='background-color:{row_color}'><td>{tribe.capitalize()}</td><td>{avg_score}</td></tr>"

    table_html += "</tbody></table>"

    html = f'''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
        <title>Team Leaderboard</title>
    </head>
    <body>
        <div class="container">
            <h1 class="mt-4 mb-4">Team Leaderboard (Sorted by Highest Average Score)</h1>
            <a href="/" class="btn btn-dark">Back to Main Leaderboard</a>
            <br><br>
            {table_html}
        </div>
    </body>
    </html>
    '''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
