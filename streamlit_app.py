import streamlit as st

st.set_page_config(layout="wide")

from streamlit_autorefresh import st_autorefresh
import threading
from azure_client import AzureSpeechClient


st_autorefresh(interval=1000, limit=1000, key="refresh")

# ----------------- Стили для страницы -----------------
hide_streamlit_style = """
    <style>
        #root > div:nth-child(1) > div > div > div > div > section > div {padding-top: 0;}
        header {visibility: hidden;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

custom_css = """
    <style>
    .block-container {
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    .main {
        padding: 0;
    }
    </style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ----------------- Заголовок -----------------
st.markdown(
    "<h1 style='text-align: center;'>ДЕМОНСТАРЦИЯ SPEECH2TEXT и TEXT2SPEECH</h1>",
    unsafe_allow_html=True
)

# ----------------- Инициализация session_state -----------------
if "azure_client" not in st.session_state:
    st.session_state.azure_client = AzureSpeechClient()

if "current_lang" not in st.session_state:
    st.session_state.current_lang = "ru-RU"

if "selected_voice" not in st.session_state:
    st.session_state.selected_voice = "ru-RU-DmitryNeural"

if "rate_value" not in st.session_state:
    st.session_state.rate_value = 20
if "pitch_value" not in st.session_state:
    st.session_state.pitch_value = 0
if "volume_value" not in st.session_state:
    st.session_state.volume_value = "medium"
if "emphasis_value" not in st.session_state:
    st.session_state.emphasis_value = "moderate"
if "accent_value" not in st.session_state:
    st.session_state.accent_value = "none"

# Поле для логов в информационной консоли
if "console_output" not in st.session_state:
    default_settings = (
        "Настройки голосовых параметров по умолчанию:\n"
        f"    Язык: Русский\n"
        f"    Голос: Дмитрий\n"
        f"    Скорость речи: 20%\n"
        f"    Высота тона: 0%\n"
        f"    Громкость: Средняя\n"
        f"    Улучшение произношения: Умеренное\n"
        f"    Акцент: Нет\n\n"
    )
    st.session_state.console_output = default_settings

# ----------------- Функции -----------------
def toggle_microphone():
    """Включает/выключает микрофон и пишет в консоль."""
    client = st.session_state.azure_client
    if client.is_listening:
        client.stop_continuous_recognition()
        st.session_state.console_output += "Микрофон выключен.\n"
    else:
        client.start_continuous_recognition()
        st.session_state.console_output += "Микрофон включён. Говорите...\n"

def manual_speak(text: str):
    """
    Функция для озвучивания текста, минуя проверку состояния микрофона.
    Используется для текстового ввода.
    """
    client = st.session_state.azure_client

    def _speak():
        ssml = client._build_ssml(text)
        client.speaking = True
        result = client.synthesizer.speak_ssml_async(ssml).get()
        client.speaking = False
    threading.Thread(target=_speak, daemon=True).start()


def process_input(text: str):
    """
    Общая функция для обработки ввода текста с учётом выбора источника ответа:
    - Если response_mode = "endpoint", то берём ответ из API и озвучиваем его
    - Если response_mode = "repeat", то озвучиваем введённое пользователем
    """
    st.session_state.console_output += f"Полученно на ввод: {text}\n"

    client = st.session_state.azure_client

    # Если включена «возможность перебивать» (interrupt_enabled) и сейчас идёт озвучивание, прерываем:
    if client.interrupt_enabled and client.speaking:
        client.interrupt_speech()

    if client.response_mode == "endpoint":
        answer = client.get_answer_from_api(text)
        if answer:
            st.session_state.console_output += f"Ответ от endpoint: {answer}\n"

            if client.is_listening:
                client.speak_text(answer)
            else:
                manual_speak(answer)
        else:
            st.session_state.console_output += "Ответ не получен от API.\n"
    else:
        # Иначе (режим repeat) озвучиваем исходную фразу
        if client.is_listening:
            client.speak_text(text)
        else:
            manual_speak(text)


# ----------------- Разметка страницы: две колонки -----------------
col_mid, col_right = st.columns([2, 1], gap="large")

# ---------- Левая колонка (Основная) ----------
with col_mid:
    st.markdown("### Информационная консоль")
    st.text_area(
        label="гагага",
        value=st.session_state.console_output,
        height=700,
        key="console_area",
        label_visibility="collapsed"
    )

    st.markdown("---")

    # Поле ввода и кнопки в нижней части основной колонки
    row_col1, row_col2, row_col3 = st.columns([5, 2, 1])
    with row_col1:
        user_input = st.text_input(
            label="гагага",
            placeholder="Введите текст для озвучки...",
            label_visibility="collapsed"
        )
    with row_col2:
        send_clicked = st.button("Отправить", key="send_btn")
    with row_col3:
        mic_clicked = st.button("🎤", key="mic_btn")

    if send_clicked:
        send_text_to_speech(user_input)
    if mic_clicked:
        toggle_microphone()

    if st.session_state.azure_client.is_listening:
        st.success("Сейчас идёт прослушивание.")

# ---------- Правая колонка (Настройки голоса) ----------
with col_right:
    st.markdown(
        """
        <style>
        div.stButton > button {
            width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.write("##### Выберите язык:")
    flag_col1, flag_col2 = st.columns(2)
    if flag_col1.button("Русский", key="lang_ru"):
        st.session_state.console_output += "Смена языка на русский\n"
        st.session_state.azure_client.set_language("ru-RU")
        st.session_state.current_lang = "ru-RU"
    if flag_col2.button("Казахский", key="lang_kz"):
        st.session_state.console_output += "Смена языка на казахский\n"
        st.session_state.azure_client.set_language("kk-KZ")
        st.session_state.current_lang = "kk-KZ"

    st.write("##### Выберите голос:")
    if st.session_state.current_lang == "ru-RU":
        col1, col2, col3 = st.columns(3)
        if col1.button("Дмитрий", key="voice_dmitry"):
            st.session_state.console_output += "Выбран голос: Дмитрий\n"
            st.session_state.selected_voice = "ru-RU-DmitryNeural"
            st.session_state.azure_client.set_voice("ru-RU-DmitryNeural")
        if col2.button("Светлана", key="voice_svetlana"):
            st.session_state.console_output += "Выбран голос: Светлана\n"
            st.session_state.selected_voice = "ru-RU-SvetlanaNeural"
            st.session_state.azure_client.set_voice("ru-RU-SvetlanaNeural")
        if col3.button("Дарья", key="voice_dariya"):
            st.session_state.console_output += "Выбран голос: Дарья\n"
            st.session_state.selected_voice = "ru-RU-DariyaNeural"
            st.session_state.azure_client.set_voice("ru-RU-DariyaNeural")
    elif st.session_state.current_lang == "kk-KZ":
        col1, col2 = st.columns(2)
        if col1.button("Айгуль", key="voice_aigul"):
            st.session_state.console_output += "Выбран голос: Айгуль\n"
            st.session_state.selected_voice = "kk-KZ-AigulNeural"
            st.session_state.azure_client.set_voice("kk-KZ-AigulNeural")
        if col2.button("Даулет", key="voice_daulet"):
            st.session_state.console_output += "Выбран голос: Даулет\n"
            st.session_state.selected_voice = "kk-KZ-DauletNeural"
            st.session_state.azure_client.set_voice("kk-KZ-DauletNeural")

    st.markdown(
        "<h5 style='font-size:20px; margin-bottom:-75px;'>Скорость речи (%):</h5>",
        unsafe_allow_html=True
    )
    st.slider("гагага", -50, 50, key="rate_value", step=10, label_visibility="collapsed")

    st.markdown(
        "<h5 style='font-size:20px; margin-bottom:-75px;'>Высота тона (%):</h5>",
        unsafe_allow_html=True
    )
    st.slider("гагага", -20, 20, key="pitch_value", step=5, label_visibility="collapsed")

    st.write("##### Уровень громкости:")
    col_soft, col_medium, col_loud = st.columns(3)
    if col_soft.button("Тихий", key="vol_soft"):
        st.session_state.console_output += "Установлена громкость: тихий\n"
        st.session_state.volume_value = "soft"
    if col_medium.button("Средний", key="vol_medium"):
        st.session_state.console_output += "Установлена громкость: средний\n"
        st.session_state.volume_value = "medium"
    if col_loud.button("Громкий", key="vol_loud"):
        st.session_state.console_output += "Установлена громкость: громкий\n"
        st.session_state.volume_value = "loud"

    st.write("##### Улучшение произношения:")
    emph_cols = st.columns(4)
    if emph_cols[0].button("Нет", key="emph_none"):
        st.session_state.console_output += "Улучшение произношения: нет\n"
        st.session_state.emphasis_value = "none"
    if emph_cols[1].button("Небольшое", key="emph_reduced"):
        st.session_state.console_output += "Улучшение произношения: небольшое\n"
        st.session_state.emphasis_value = "reduced"
    if emph_cols[2].button("Умеренное", key="emph_moderate"):
        st.session_state.console_output += "Улучшение произношения: умеренное\n"
        st.session_state.emphasis_value = "moderate"
    if emph_cols[3].button("Сильное", key="emph_strong"):
        st.session_state.console_output += "Улучшение произношения: сильное\n"
        st.session_state.emphasis_value = "strong"

    st.markdown("##### Уровни акцента:")
    accent_cols = st.columns(4)
    if accent_cols[0].button("Нет", key="accent_none"):
        st.session_state.console_output += "Акцент: нет\n"
        st.session_state.accent_value = "none"
    if accent_cols[1].button("Небольшое", key="accent_reduced"):
        st.session_state.console_output += "Акцент: небольшое\n"
        st.session_state.accent_value = "reduced"
    if accent_cols[2].button("Умеренное", key="accent_moderate"):
        st.session_state.console_output += "Акцент: умеренное\n"
        st.session_state.accent_value = "moderate"
    if accent_cols[3].button("Сильное", key="accent_strong"):
        st.session_state.console_output += "Акцент: сильное\n"
        st.session_state.accent_value = "strong"

    st.markdown("##### Источник ответа:")
    col_source1, col_source2 = st.columns(2)
    if col_source1.button("Endpoint HCB", key="source_endpoint"):
        st.session_state.console_output += "Источник ответа: Endpoint HCB\n"
        st.session_state.azure_client.response_mode = "endpoint"
    if col_source2.button("Повторение услышанного", key="source_repeat"):
        st.session_state.console_output += "Источник ответа: Повторение услышанного\n"
        st.session_state.azure_client.response_mode = "repeat"

    st.markdown("##### Перебивание бота:")
    col_int1, col_int2 = st.columns(2)
    if col_int1.button("Можно перебивать", key="interrupt_enabled"):
        st.session_state.console_output += "Перебивание: можно\n"
        st.session_state.azure_client.interrupt_enabled = True
    if col_int2.button("Нельзя перебивать", key="interrupt_disabled"):
        st.session_state.console_output += "Перебивание: нельзя\n"
        st.session_state.azure_client.interrupt_enabled = False

    st.session_state.azure_client.set_synthesis_params(
        rate=st.session_state.rate_value,
        pitch=st.session_state.pitch_value,
        volume=st.session_state.volume_value,
        emphasis=st.session_state.emphasis_value,
        accent=st.session_state.accent_value
    )
