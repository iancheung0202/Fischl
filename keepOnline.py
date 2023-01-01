from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    # return '''<iframe src="https://fm-genshin-cafe.github.io/fischl/" width="100%" height="100%"></iframe>'''
  return 'Fischl is a Genshin-based Discord bot with lots of functions for Genshin Impact servers, namely a convenient ticket system and a random Genshin conversation starter. The bot also comes with a lot of utility-based features such as implementing sticky messages, generating welcome cards, or even creating customized Genshin-font texts.'

def run():
    app.run(host='0.0.0.0', port=8080)

def keepOnline():
    t = Thread(target=run)
    t.start()