import os
import time
import uuid
import logging
import requests
from flask import Flask, request, session, Response
from twilio.twiml.voice_response import VoiceResponse

# Configuration and Setup
app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Replace with a secure secret key

# Logging Setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuration Values
TWILIO_PHONE_NUMBER = "your_twilio_phone_number"
ELEVEN_LABS_API_KEY = "your_eleven_labs_api_key"

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
        url = f"https://api.elevenlabs.io/v1/text-to-speech/cgSgspJ2msm6clMCkdW9"
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
        if response.status_code == 200:
            return response.content
        logger.error("Error in text_to_speech: %s %s", response.status_code, response.text)
    except Exception as e:
        logger.error(f"Exception in text_to_speech: {str(e)}", exc_info=True)
    return None

@app.route("/", methods=['GET'])
def index():
    return "Welcome to the Albany Hindu Temple Call Handling System"

@app.route("/voice", methods=['POST'])
def voice():
    try:
        session.clear()
        response = VoiceResponse()
        session['conversation_history'] = conversation_history_template.copy()
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id

        initial_message = session['conversation_history'][-1]['content']
        audio_content = text_to_speech(initial_message)
        if audio_content:
            audio_filename = f"./audio/{session_id}_initial_message.mp3"
            os.makedirs('./audio', exist_ok=True)
            with open(audio_filename, "wb") as f:
                f.write(audio_content)
            response.play(f"/stream_audio/{session_id}_initial_message.mp3")
        response.redirect('/gather')
        return str(response)
    except Exception as e:
        logger.error(f"Error in /voice: {str(e)}")
        response = VoiceResponse()
        response.say("An application error occurred. Please try again later.")
        return str(response)

@app.route("/gather", methods=['POST'])
def gather():
    try:
        response = VoiceResponse()
        response.gather(input="speech", action="/process_speech", speechTimeout="auto")
        return str(response)
    except Exception as e:
        logger.error(f"Error in /gather: {str(e)}")
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
            # Simple echo response for speech transcription
            reply = f"You said: {speech_result}. How can I assist further?"
            session['conversation_history'].append({"role": "user", "content": speech_result})
            session['conversation_history'].append({"role": "assistant", "content": reply})

            audio_content = text_to_speech(reply)
            if audio_content:
                audio_filename = f"./audio/{session_id}_response.mp3"
                with open(audio_filename, "wb") as f:
                    f.write(audio_content)
                response.play(f"/stream_audio/{session_id}_response.mp3")
            response.redirect('/gather')
        else:
            response.say("I didn't catch that. Could you repeat?")
            response.redirect('/gather')
        return str(response)
    except Exception as e:
        logger.error(f"Error in /process_speech: {str(e)}")
        response = VoiceResponse()
        response.say("An application error occurred. Please try again later.")
        return str(response)

@app.route("/stream_audio/<filename>", methods=['GET'])
def stream_audio(filename):
    try:
        with open(f"./audio/{filename}", "rb") as audio_file:
            return Response(audio_file.read(), mimetype="audio/mpeg")
    except Exception as e:
        logger.error(f"Error in /stream_audio: {str(e)}")
        return Response("Audio not found", status=404)

if __name__ == "__main__":
    app.run(debug=True)
