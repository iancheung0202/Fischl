import openai, os
import firebase_admin
from firebase_admin import db

def request(query, guild_id):
  openai.api_key = os.environ['OPENAI_KEY']

  ref = db.reference("/FAQ")
  faqs = ref.get()

  data = ""
  try:
    for key, val in faqs.items():
      if val['Server ID'] == guild_id:
        data = f"{data}{val['Question']}\n{val['Answer']}\n\n"
  except Exception:
    pass

  query = f"{data}{query}"
  
  response = openai.Completion.create(
    model="text-davinci-003",
    prompt=query,
    temperature=0.99,
    max_tokens=1000,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
  )
  return response['choices'][0]['text'].replace(query, "").replace("@everyone","").replace("@here","")

def simple_get(query):
  openai.api_key = os.environ['OPENAI_KEY']
  
  response = openai.Completion.create(
    model="text-davinci-003",
    prompt=query,
    temperature=0.99,
    max_tokens=1000,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
  )
  return response['choices'][0]['text'].replace(query, "").replace("@everyone","").replace("@here","")