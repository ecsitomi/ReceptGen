import openai
import firebase_admin
import uuid
import os
import requests
from firebase_admin import credentials, firestore, storage, auth
from flask import Flask, request, render_template, jsonify
from dotenv import load_dotenv
from google import genai

# .env betöltése
load_dotenv()

# OpenAI API kulcs
openai.api_key = os.getenv("OPENAI_API_KEY")

#Google API kulcs
google_api_key = os.getenv("GOOGLE_API_KEY")

# Firebase inicializálása
firebase_cert_path = os.getenv("FIREBASE_CERT_PATH")
storage_bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
cred = credentials.Certificate(firebase_cert_path)
firebase_admin.initialize_app(cred, {'storageBucket': storage_bucket_name})

# Firestore adatbázis inicializálása
db = firestore.client()

# Firebase Storage bucket elérése
bucket = storage.bucket()

# Backend inicializálása
app = Flask(__name__)

#Recept generálása
def generate_recept(ingredients, google_api_key):
    client = genai.Client(api_key=google_api_key)
    prompt = f'Írj nekem egy étel recept ötletet, ami felhasználja a következő hozzávalókat: {', '.join(ingredients)}. Kérlek, legyél kreatív és gondolj valami egyedire!'

    response = client.models.generate_content(
        model='gemini-2.0-flash-exp', contents=prompt
    )
    #print(response.text)
    return response.text

#Kép feltöltése
def upload_image_to_storage(image_url, image_id):
    response = requests.get(image_url)
    if response.status_code == 200:
        blob = bucket.blob(f"images/{image_id}.png")
        blob.upload_from_string(response.content, content_type='image/png')
        return blob.public_url
    else:
        raise Exception("Kép feltöltése sikertelen")

# VÉGPONTOK
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/firebase_config") #nem tökéletesen biztonságos megoldás
def get_firebase_config(): #de a frontend így tölti be a firebase configot
    firebase_config = {
        "apiKey": os.getenv("FIREBASE_API_KEY"),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("FIREBASE_APP_ID"),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID") # Opcionális
    }
    return jsonify(firebase_config)

#kép generálása
@app.route("/generate_image", methods=["POST"])
def generate_image():
    data = request.json
    ingredients = data.get("ingredients", [])
    description = f"Írj nekem egy étel recept ötletet, ami felhasználja a következő hozzávalókat: {', '.join(ingredients)}. Kérlek, legyél kreatív és gondolj valami egyedire!"

    response = openai.images.generate(
        model="dall-e-3",
        prompt=description,
        n=1,
        size="1024x1024"
    )
    image_url = response.data[0].url
    openai_img_url = image_url

    #Szöveges recept generálása
    recept=generate_recept(ingredients, google_api_key)

    # Feltöltés a Firebase Storage-ba
    try:
        image_url_storage = upload_image_to_storage(image_url, str(uuid.uuid4()))
    except Exception as e:
        return jsonify({"error": f"Image processing failed: {str(e)}"}), 500

    # Egyedi azonosító generálása
    image_id = str(uuid.uuid4()) 

    # Adatok mentése a Firestore-ba
    doc_ref = db.collection("generated_images_new").document(image_id)
    doc_ref.set({
        "id": image_id,
        "ingredients": ingredients,
        "image_url": image_url_storage,
        "recept": recept
    })

    return jsonify({"image_id": image_id, "image_url": image_url_storage, "openai_img_url": openai_img_url, "recept": recept})

# FUTTATÁS
if __name__ == "__main__":
    app.run(debug=True)

'''
- uuid.uuid4() - itt van egy hiba, mert a storeagebe és a datebasebe nem ugyanazt az id-t menti
- a generált receptet még fel kell "darabolnom" a szebb megjelenítés érdekében
- a Firebase felhasználó, token és lekérdezést még lehet bőven fejleszteni
'''