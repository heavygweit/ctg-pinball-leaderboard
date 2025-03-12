import requests
import pandas as pd
import time
from flask import Flask, render_template_string, request

app = Flask(__name__)

# Constants
RESULTS_PER_PAGE = 25
CACHE_EXPIRATION = 500

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

def calculate_team_leaderboard():
    global cached_leaderboard

    # If the cached leaderboard is empty or None, return an empty DataFrame
    if not cached_leaderboard or len(cached_leaderboard) == 0:
        return pd.DataFrame(columns=["tribe", "highest_score", "average_score"])

    df = pd.DataFrame(cached_leaderboard)

    # Group by tribe and calculate the highest individual score per team
    team_stats = df.groupby("tribe").agg(
        highest_score=("highScore", "max"),  # Highest individual score
        average_score=("highScore", "mean")  # Average score across tribe
    ).reset_index()

    # Format the scores nicely
    team_stats["highest_score"] = team_stats["highest_score"].apply(lambda x: f"{x:,.0f}" if not pd.isna(x) else "0")
    team_stats["average_score"] = team_stats["average_score"].apply(lambda x: f"{x:,.0f}" if not pd.isna(x) else "0")

    # Sort teams by highest individual score (descending)
    team_stats = team_stats.sort_values(by="highest_score", ascending=False)

    return team_stats




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
        <a href="{base_url}?sort_by=attempts&order=asc" class="btn btn-secondary">Sort by Attempts (Asc)</a>
        <a href="{base_url}?sort_by=attempts&order=desc" class="btn btn-secondary">Sort by Attempts (Desc)</a>
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
            <h1 class="mt-4 mb-4">Live Leaderboard</h1><br>
             <a href="/teams" class="btn btn-info">View Team Leaderboard</a><br>
            {tribe_buttons}
            <h4>Sorted by {sort_by} ({order.upper()})</h4>
            <p><small>Last Updated: {time.strftime('%I:%M %p', time.localtime(last_updated))}</small></p>
            <div>
                <a href="/" class="btn btn-success">Manual Refresh</a>
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
    </head>
    <body>
        <div class="container">
            <h1 class="mt-4 mb-4">{tribe.capitalize()} Tribe Leaderboard</h1>
            {tribe_buttons}
            <h4>Sorted by {sort_by} ({order.upper()})</h4>
            <h5>Percentage of Players with a Score > 0: {percentage_scored}</h5>
            <h5>Average Score (All Players): {average_score}</h5>
            <br>
            {sort_buttons}
            <br><br>
            {table_html}
            <br>
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
