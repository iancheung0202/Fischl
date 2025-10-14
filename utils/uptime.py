from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def status():
    return jsonify(status="ok")
