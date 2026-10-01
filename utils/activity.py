from firebase_admin import db
from flask import Flask, jsonify
from flask_cors import CORS

CORS_ORIGINS = [
    "https://iancheung.dev",
    "https://www.iancheung.dev",
    "https://github.com",
    "https://www.github.com",
]
app = Flask(__name__)
CORS(app, origins=CORS_ORIGINS)


@app.route("/")
def status():
    ref = db.reference("/Ian Activity")
    activity = ref.get()
    return jsonify(activity=activity)


@app.route("/github/<type>")
def github_shields(type):
    ref = db.reference("/Ian Activity")
    raw_data = ref.get()

    # Extract the activity list from your specific JSON structure
    if isinstance(raw_data, list):
        activities = raw_data
    elif isinstance(raw_data, dict):
        activities = raw_data.get("activity", [])
    else:
        activities = []

    # 1. Currently | online/offline
    if type == "currently":
        # If the activity list has anything (Spotify, Custom Status, etc.), you are online
        is_online = len(activities) > 0
        return jsonify(
            {
                "schemaVersion": 1,
                "label": "currently",
                "message": "online" if is_online else "offline",
                "color": "brightgreen" if is_online else "lightgrey",
            }
        )

    # 2. Playing | nothing rn/game name
    elif type == "playing":
        game = next(
            (
                a
                for a in activities
                if a.get("name")
                not in ["Visual Studio Code", "Spotify", "Custom Status"]
            ),
            None,
        )
        return jsonify(
            {
                "schemaVersion": 1,
                "label": "playing",
                "message": game.get("name") if game else "nothing rn",
                "color": "7289DA",  # Always Blue/Blurple
            }
        )

    # 3. Coding | nothing rn/file name
    elif type == "coding":
        vscode = next(
            (a for a in activities if a.get("name") == "Visual Studio Code"), None
        )
        return jsonify(
            {
                "schemaVersion": 1,
                "label": "coding",
                "message": vscode.get("details", "coding") if vscode else "nothing rn",
                "color": "informational",  # Always Blue
            }
        )

    # 4. Listening to | nothing rn/song name
    elif type == "listening":
        spotify = next((a for a in activities if a.get("name") == "Spotify"), None)
        msg = "nothing rn"
        if spotify:
            track = spotify.get("details", "song")
            msg = (track[:26] + "...") if len(track) > 30 else track

        return jsonify(
            {
                "schemaVersion": 1,
                "label": "listening to",
                "message": msg,
                "color": "1DB954",  # Always Spotify Green
            }
        )

    return jsonify({"error": "invalid type"}), 400
