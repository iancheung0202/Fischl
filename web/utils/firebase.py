import firebase_admin

from firebase_admin import credentials, db
from config.settings import FIREBASE_CRED, DATABASE_URL

# Initialize Firebase
cred = credentials.Certificate(FIREBASE_CRED)
default_app = firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})

def save_user_to_firebase(user, token):
    """Save user data to Firebase"""
    db.reference(f"Dashboard Users/{user['id']}").set({
        "username": user["username"],
        "avatar": user.get("avatar", ""),
        "discord_token": token
    })