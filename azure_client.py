import logging
import json
import requests
import threading
import streamlit as st
import azure.cognitiveservices.speech as speechsdk

logging.basicConfig(level=logging.INFO)

class AzureSpeechClient:
    def __init__(self):
        key = st.secrets["AZURE_SPEECH_KEY"]
        region = st.secrets["AZURE_SPEECH_REGION"]
        self.speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        self.speech_config.speech_recognition_language = "ru-RU"
        self.speech_config.speech_synthesis_voice_name = "ru-RU-DmitryNeural"
        self.rate_value = 0
        self.pitch_value = 0
        self.volume_value = "medium"
        self.emphasis_value = "moderate"
        self.accent_value = "none"
        self.synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)
        orig = self.synthesizer.speak_ssml_async
        class Future:
            def __init__(self, res): self._res = res
            def get(self): return self._res
        def patched(ssml):
            f = orig(ssml)
            res = f.get()
            if res.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                st.audio(res.audio_data, format="audio/wav")
            else:
                d = res.cancellation_details
                logging.error(f"TTS canceled: {d.reason} {d.error_details}")
            return Future(res)
        self.synthesizer.speak_ssml_async = patched
        mic_cfg = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.recognizer = speechsdk.SpeechRecognizer(self.speech_config, audio_config=mic_cfg)
        self.recognizer.recognized.connect(self._recognized_callback)
        self.recognizer.canceled.connect(self._canceled_callback)
        self.is_listening = False
        self.response_mode = "endpoint"
        self.interrupt_enabled = True
        self.speaking = False

    def start_continuous_recognition(self):
        if not self.is_listening:
            self.recognizer.start_continuous_recognition_async()
            self.is_listening = True

    def stop_continuous_recognition(self):
        if self.is_listening:
            self.recognizer.stop_continuous_recognition_async().get()
            self.is_listening = False

    def _build_ssml(self, text: str) -> str:
        rate = f"{'+' if self.rate_value>0 else ''}{self.rate_value}%"
        pitch = f"{'+' if self.pitch_value>0 else ''}{self.pitch_value}%"
        vol = self.volume_value
        inner = text
        if self.accent_value != "none":
            inner = f'<emphasis level="{self.accent_value}">{inner}</emphasis>'
        if self.emphasis_value != "none":
            inner = f'<emphasis level="{self.emphasis_value}">{inner}</emphasis>'
        return f'<speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis" xml:lang="{self.speech_config.speech_recognition_language}"><voice name="{self.speech_config.speech_synthesis_voice_name}"><prosody rate="{rate}" pitch="{pitch}" volume="{vol}">{inner}</prosody></voice></speak>'

    def speak_text(self, text: str):
        def _worker():
            self.speaking = True
            self.synthesizer.speak_ssml_async(self._build_ssml(text)).get()
            self.speaking = False
        threading.Thread(target=_worker, daemon=True).start()

    def set_synthesis_params(self, rate, pitch, volume, emphasis, accent):
        self.rate_value = rate
        self.pitch_value = pitch
        self.volume_value = volume
        self.emphasis_value = emphasis
        self.accent_value = accent
        logging.info(f"Params set: rate={rate} pitch={pitch} volume={volume} emphasis={emphasis} accent={accent}")

    def set_language(self, new_lang: str):
        was = self.is_listening
        if was:
            self.stop_continuous_recognition()
        self.speech_config.speech_recognition_language = new_lang
        if was:
            self.start_continuous_recognition()
        logging.info(f"Language set to {new_lang}")

    def set_voice(self, new_voice: str):
        self.speech_config.speech_synthesis_voice_name = new_voice
        logging.info(f"Voice set to {new_voice}")

    def get_answer_from_api(self, question: str) -> str:
        url = "https://hc-aizhan-4voicebot.francecentral.inference.ml.azure.com/score"
        payload = json.dumps({"chat_history":[{"inputs":{"question":"привет"},"outputs":{"answer":"Здравствуйте! Чем могу помочь?"}}],"question":question,"source":None,"mode":None})
        headers = {'Content-Type':'application/json','Authorization':'Bearer 3DNAJGclhEf1WwK4J1z7292iwv7bsVOkSXwJw8tlnWRm7WIL81gTJQQJ99BCAAAAAAAAAAAAINFRAZMLjGNL'}
        try:
            r = requests.post(url, headers=headers, data=payload)
            if r.status_code == 200:
                return r.json().get("answer")
        except Exception as e:
            logging.error(f"API error: {e}")
        return None

    def interrupt_speech(self):
        try:
            self.synthesizer.stop_speaking_async().get()
            self.speaking = False
        except:
            pass

    def _recognized_callback(self, evt):
        if not self.is_listening:
            return
        txt = evt.result.text.strip()
        if not txt:
            return
        if self.interrupt_enabled and self.speaking:
            self.interrupt_speech()
        if self.response_mode == "endpoint":
            ans = self.get_answer_from_api(txt)
            if ans:
                self.speak_text(ans)
        else:
            self.speak_text(txt)

    def _canceled_callback(self, evt):
        logging.error(f"Recognition canceled: {evt.result.cancellation_details.reason}")
