import os
import uuid
import logging
import requests
from flask import Flask, request, session, Response
from twilio.twiml.voice_response import VoiceResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration and Setup
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')  # Replace with a secure secret key

# Logging Setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuration Values
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
ELEVEN_LABS_API_KEY = os.getenv('ELEVEN_LABS_API_KEY')
ELEVEN_LABS_VOICE_ID = os.getenv('ELEVEN_LABS_VOICE_ID', 'cgSgspJ2msm6clMCkdW9')  # Default voice ID
AUDIO_DIR = os.path.join(os.getcwd(), 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

# Verify critical environment variables
if not TWILIO_PHONE_NUMBER or not ELEVEN_LABS_API_KEY:
    raise EnvironmentError("Missing critical environment variables!")

# Conversation template
conversation_history_template = [
    {
        "role": "system",
        "content": (
            "You are Neela, a friendly assistant from the Albany Hindu Temple in Albany, NY. "
            "You can assist with temple information and puja bookings in English, Hindi, Telugu, and Tamil. "
            "Guide users step-by-step through bookings, collecting details like puja name, date, time, name, and phone number. "
            "Always provide responses that are concise and helpful."
        )
    },
    {"role": "assistant", "content": "Hello, I'm Neela. How can I assist you today?"}
]

# ElevenLabs text-to-speech function
def text_to_speech(text):
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVEN_LABS_API_KEY,
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # Raise HTTPError for bad responses
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Error in ElevenLabs API: {e}", exc_info=True)
        return None

@app.route("/", methods=['GET'])
def index():
    return "Welcome to the Albany Hindu Temple Call Handling System"

@app.route("/voice", methods=['POST'])
def voice():
    try:
        logger.info("Incoming call to /voice endpoint.")
        session.clear()
        session['conversation_history'] = conversation_history_template.copy()
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id

        initial_message = session['conversation_history'][-1]['content']
        audio_content = text_to_speech(initial_message)
        if audio_content:
            audio_filename = os.path.join(AUDIO_DIR, f"{session_id}_initial_message.mp3")
            with open(audio_filename, "wb") as f:
                f.write(audio_content)
            response = VoiceResponse()
            response.play(f"/stream_audio/{session_id}_initial_message.mp3")
            response.redirect('/gather')
        else:
            response = VoiceResponse()
            response.say("Sorry, I couldn't process your request.")
        return str(response)
    except Exception as e:
        logger.error(f"Error in /voice: {e}", exc_info=True)
        response = VoiceResponse()
        response.say("An error occurred. Please try again later.")
        return str(response)

@app.route("/gather", methods=['POST'])
def gather():
    try:
        logger.info("Processing /gather endpoint.")
        response = VoiceResponse()
        response.gather(input="speech", action="/process_speech", speechTimeout="auto")
        return str(response)
    except Exception as e:
        logger.error(f"Error in /gather: {e}", exc_info=True)
        response = VoiceResponse()
        response.say("An application error occurred. Please try again later.")
        return str(response)

@app.route("/process_speech", methods=['POST'])
def process_speech():
    try:
        speech_result = request.form.get("SpeechResult", "")
        response = VoiceResponse()
        session_id = session.get("session_id", "default_session")

        if speech_result:
            reply = f"You said: {speech_result}. How can I assist further?"
            session['conversation_history'].append({"role": "user", "content": speech_result})
            session['conversation_history'].append({"role": "assistant", "content": reply})

            audio_content = text_to_speech(reply)
            if audio_content:
                audio_filename = os.path.join(AUDIO_DIR, f"{session_id}_response.mp3")
                with open(audio_filename, "wb") as f:
                    f.write(audio_content)
                response.play(f"/stream_audio/{session_id}_response.mp3")
            response.redirect('/gather')
        else:
            response.say("I didn't catch that. Could you repeat?")
            response.redirect('/gather')
        return str(response)
    except Exception as e:
        logger.error(f"Error in /process_speech: {e}", exc_info=True)
        response = VoiceResponse()
        response.say("An application error occurred. Please try again later.")
        return str(response)

@app.route("/stream_audio/<filename>", methods=['GET'])
def stream_audio(filename):
    try:
        audio_path = os.path.join(AUDIO_DIR, filename)
        if os.path.exists(audio_path):
            with open(audio_path, "rb") as audio_file:
                return Response(audio_file.read(), mimetype="audio/mpeg")
        else:
            raise FileNotFoundError(f"File {filename} not found.")
    except Exception as e:
        logger.error(f"Error in /stream_audio: {e}", exc_info=True)
        return Response("Audio not found", status=404)

if __name__ == "__main__":
    app.run(debug=True)
