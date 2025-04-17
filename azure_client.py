import logging
import json
import requests
import threading
import azure.cognitiveservices.speech as speechsdk

logging.basicConfig(level=logging.INFO)

class AzureSpeechClient:
    def __init__(self):
        self.speech_config = speechsdk.SpeechConfig(subscription=st.secrets["AZURE_SPEECH_KEY"], region=st.secrets["AZURE_SPEECH_REGION"])
        self.speech_config.speech_recognition_language = "ru-RU"
        self.speech_config.speech_synthesis_voice_name = "ru-RU-DmitryNeural"

        self.rate_value = 0
        self.pitch_value = 0
        self.volume_value = "medium"
        self.emphasis_value = "moderate"
        self.accent_value = "none"

        self.audio_output_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
        self.synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=self.audio_output_config
        )

        self.audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=self.audio_config
        )

        self.is_listening = False  # Флаг активности микрофона
        self.response_mode = "endpoint"  # "endpoint" или "repeat"
        self.interrupt_enabled = True  # Разрешение перебивания озвучивания
        self.speaking = False  # Флаг, показывающий, идёт ли озвучивание

        self.recognizer.recognized.connect(self._recognized_callback)
        self.recognizer.canceled.connect(self._canceled_callback)

    # ----------------- Методы для распознавания -----------------
    def start_continuous_recognition(self):
        if not self.is_listening:
            self.recognizer.start_continuous_recognition_async()
            self.is_listening = True
            logging.info("Continuous recognition started.")

    def stop_continuous_recognition(self):
        if self.is_listening:
            self.recognizer.stop_continuous_recognition_async().get()
            self.is_listening = False
            logging.info("Continuous recognition stopped.")

    # ----------------- Методы для синтеза речи -----------------
    def speak_text(self, text: str):
        # Если микрофон выключен, синтез речи не выполняется
        if not self.is_listening:
            logging.info("Микрофон выключен, синтез речи отключён.")
            return

        def _speak():
            ssml = self._build_ssml(text)
            self.speaking = True
            result = self.synthesizer.speak_ssml_async(ssml).get()
            self.speaking = False
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logging.info("Озвучивание завершено")
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logging.error(f"Озвучивание отменено: {cancellation_details.reason} - {cancellation_details.error_details}")

        threading.Thread(target=_speak, daemon=True).start()

    def _build_ssml(self, text: str) -> str:
        rate_str = f"{self.rate_value}%"
        if self.rate_value > 0:
            rate_str = f"+{rate_str}"
        pitch_str = f"{self.pitch_value}%"
        if self.pitch_value > 0:
            pitch_str = f"+{pitch_str}"
        volume_str = self.volume_value

        inner_text = text
        if self.accent_value != "none":
            inner_text = f'<emphasis level="{self.accent_value}">{inner_text}</emphasis>'
        if self.emphasis_value != "none":
            inner_text = f'<emphasis level="{self.emphasis_value}">{inner_text}</emphasis>'

        ssml = f"""
                <speak version="1.0" xmlns="https://www.w3.org/2001/10/synthesis"
                       xml:lang="{self.speech_config.speech_recognition_language}">
                  <voice name="{self.speech_config.speech_synthesis_voice_name}">
                    <prosody rate="{rate_str}" pitch="{pitch_str}" volume="{volume_str}">
                      {inner_text}
                    </prosody>
                  </voice>
                </speak>
                """
        return ssml

    def set_synthesis_params(self, rate, pitch, volume, emphasis, accent):
        self.rate_value = rate
        self.pitch_value = pitch
        self.volume_value = volume
        self.emphasis_value = emphasis
        self.accent_value = accent
        logging.info(f"Set synthesis params: rate={rate}, pitch={pitch}, volume={volume}, emphasis={emphasis}, accent={accent}")

    def set_language(self, new_lang: str):
        current_lang = self.speech_config.speech_recognition_language
        if current_lang == new_lang:
            logging.info(f"Language already set to {new_lang}. No change made.")
            return
        was_listening = self.is_listening
        if was_listening:
            self.stop_continuous_recognition()

        self.speech_config.speech_recognition_language = new_lang
        self.synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=self.audio_output_config
        )
        self.recognizer = speechsdk.SpeechRecognizer(
            speech_config=self.speech_config,
            audio_config=self.audio_config
        )
        self.recognizer.recognized.connect(self._recognized_callback)
        self.recognizer.canceled.connect(self._canceled_callback)

        if was_listening:
            self.start_continuous_recognition()

        logging.info(f"Language changed to {new_lang}.")

    def set_voice(self, new_voice: str):
        current_voice = self.speech_config.speech_synthesis_voice_name
        if current_voice == new_voice:
            logging.info(f"Voice already set to {new_voice}. No change made.")
            return
        was_listening = self.is_listening
        if was_listening:
            self.stop_continuous_recognition()

        self.speech_config.speech_synthesis_voice_name = new_voice
        self.synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config,
            audio_config=self.audio_output_config
        )
        if was_listening:
            self.start_continuous_recognition()

        logging.info(f"Voice changed to {new_voice}.")

    # ----------------- Логика работы с API -----------------
    def get_answer_from_api(self, question: str) -> str:
        url = "https://hc-aizhan-4voicebot.francecentral.inference.ml.azure.com/score"
        payload = json.dumps({
            "chat_history": [
                {
                    "inputs": {
                        "question": "привет"
                    },
                    "outputs": {
                        "answer": "Здравствуйте! Чем могу помочь? Если у вас есть вопросы по продуктам и услугам Home Credit Bank, задавайте."
                    }
                }
            ],
            "question": question,
            "source": None,
            "mode": None
        })
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer 3DNAJGclhEf1WwK4J1z7292iwv7bsVOkSXwJw8tlnWRm7WIL81gTJQQJ99BCAAAAAAAAAAAAINFRAZMLjGNL'
        }
        try:
            response = requests.post(url, headers=headers, data=payload)
            if response.status_code == 200:
                response_data = response.json()
                answer = response_data.get("answer")
                return answer
            else:
                logging.error(f"Ошибка запроса: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logging.error(f"Ошибка при запросе к API: {e}")
            return None

    # ----------------- Метод прерывания озвучивания -----------------
    def interrupt_speech(self):
        try:
            self.synthesizer.stop_speaking_async().get()
            self.speaking = False
            # Переинициализируем синтезатор для сброса состояния
            self.synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config,
                audio_config=self.audio_output_config
            )
            logging.info("Озвучивание прервано и синтезатор перезапущен")
        except Exception as e:
            logging.error("Ошибка прерывания озвучивания: " + str(e))

    # ----------------- Колбэк распознавания -----------------
    def _recognized_callback(self, evt: speechsdk.SpeechRecognitionEventArgs):
        # Если микрофон выключен, игнорируем событие распознавания
        if not self.is_listening:
            logging.info("Получен callback распознавания, но микрофон выключен. Игнорирование события.")
            return

        result = evt.result
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            recognized_text = result.text.strip()
            # Если результат пустой, пропускаем его
            if not recognized_text:
                logging.info("Пустой результат распознавания, игнорирование.")
                return

            logging.info(f"Распознано: {recognized_text}")
            if self.interrupt_enabled and self.speaking:
                self.interrupt_speech()
            if self.response_mode == "endpoint":
                answer = self.get_answer_from_api(recognized_text)
                if answer:
                    logging.info(f"Получен ответ: {answer}")
                    self.speak_text(answer)
                else:
                    logging.error("Ответ не получен от API.")
            elif self.response_mode == "repeat":
                self.speak_text(recognized_text)
        elif result.reason == speechsdk.ResultReason.NoMatch:
            logging.error("Речь не распознана (NoMatch). Попробуйте говорить яснее или проверьте настройки микрофона.")

    def _canceled_callback(self, evt: speechsdk.SpeechRecognitionCanceledEventArgs):
        cancellation_details = evt.result.cancellation_details
        logging.error(f"Распознавание отменено: {cancellation_details.reason}. Ошибка: {cancellation_details.error_details}")
