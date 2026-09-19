import json
import re
from google import genai

print("[rewriter] === REWRITER ЗАГРУЖЕН ===")

PROMPT_NEWS = """Ты — автор телеграм-канала "Капитал на автопилоте" о финансах и инвестициях.
Перепиши новость ниже своими словами, сохранив ВСЕ факты, числа, проценты, названия.

Стиль: экспертно, но понятно обычному человеку. Без сленга и сложных терминов.
Структура: цепляющий заголовок, вводный абзац, 2-4 абзаца, вывод «Что это значит для обычного человека?».
Добавь 1-2 эмодзи.
НЕ выдумывай цифры. Если чего-то нет — опусти.
В конце — короткий вопрос читателю.
Длина: 1200–2000 символов.
Внутри строк НЕ используй двойные кавычки.

Верни ТОЛЬКО валидный JSON. Первый символ {{, последний }}.
Формат: {{"title": "заголовок", "text": "текст", "teaser": "1-2 предложения"}}

Заголовок: {title}
Текст: {body}
"""

PROMPT_LIFEHACK = """Ты — автор телеграм-канала "Капитал на автопилоте" о финансах.
Перепиши материал ниже как ПОЛЕЗНЫЙ ФИНАНСОВЫЙ ЛАЙФХАК.

Стиль: экспертно, практично.
Структура: броский заголовок, короткое вступление, 3-5 пунктов-советов, резюме.
Сохрани все числа и факты.
НЕ выдумывай цифры.
В конце — вопрос «А вы так делаете?».
Длина: 1200–2000 символов.
Внутри строк НЕ используй двойные кавычки.

Верни ТОЛЬКО валидный JSON. Первый символ {{, последний }}.
Формат: {{"title": "заголовок", "text": "текст", "teaser": "1-2 предложения"}}

Заголовок: {title}
Текст: {body}
"""

PROMPT_STORY = """Ты — автор телеграм-канала "Капитал на автопилоте" о финансах.
Перепиши материал ниже как ИСТОРИЮ из мира финансов.

Стиль: экспертно, но с элементом рассказа.
Структура: интригующий заголовок, завязка, факты, вывод.
Сохрани все числа и факты.
НЕ выдумывай.
В конце — открытый вопрос.
Длина: 1200–2000 символов.
Внутри строк НЕ используй двойные кавычки.

Верни ТОЛЬКО валидный JSON. Первый символ {{, последний }}.
Формат: {{"title": "заголовок", "text": "текст", "teaser": "1-2 предложения"}}

Заголовок: {title}
Текст: {body}
"""

RUBRICS = [
    {"name": "Банки и карты",
     "keywords": ["банк", "карт", "кэшбэк", "вклад", "счёт", "дебетов", "кредитн", "ипотек"],
     "hashtags": "#КапиталНаАвтопилоте #банки #карты #кэшбэк"},
    {"name": "Инвестиции",
     "keywords": ["инвестиц", "акци", "облигац", "дивиденд", "брокер", "биржа", "фонд", "портфель"],
     "hashtags": "#КапиталНаАвтопилоте #инвестиции #акции #дивиденды"},
    {"name": "Экономика",
     "keywords": ["рубл", "доллар", "евро", "курс", "ставк", "ЦБ", "инфляц", "ВВП", "экономик"],
     "hashtags": "#КапиталНаАвтопилоте #экономика #курс #ЦБ"},
    {"name": "Личные финансы",
     "keywords": ["бюджет", "накоплен", "сбережен", "расход", "доход", "зарплат", "налог"],
     "hashtags": "#КапиталНаАвтопилоте #личныефинансы #бюджет"},
    {"name": "Криптовалюты",
     "keywords": ["криптов", "биткоин", "блокчейн", "токен", "ethereum", "NFT"],
     "hashtags": "#КапиталНаАвтопилоте #крипта #биткоин #блокчейн"},
    {"name": "Налоги",
     "keywords": ["налог", "НДФЛ", "вычет", "декларац", "ФНС", "сбор"],
     "hashtags": "#КапиталНаАвтопилоте #налоги #НДФЛ #вычет"},
    {"name": "Страхование",
     "keywords": ["страхов", "полис", "ОСАГО", "КАСКО", "ДМС"],
     "hashtags": "#КапиталНаАвтопилоте #страхование #полис"},
]

FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]


def detect_rubric(title, summary, full_text):
    haystack = (title + " " + summary + " " + full_text[:1500]).lower()
    scores = [(sum(1 for kw in r["keywords"] if kw in haystack), r) for r in RUBRICS]
    scores.sort(key=lambda x: x[0], reverse=True)
    if scores and scores[0][0] > 0:
        return scores[0][1]
    return RUBRICS[2]


def detect_style(title, summary, full_text):
    haystack = (title + " " + summary).lower()
    if any(m in haystack for m in ["совет", "как ", "лайфхак", "способ", "инструкц", "ошибк"]):
        return "lifehack", PROMPT_LIFEHACK
    if any(m in haystack for m in ["описал", "рассказал", "поделил", "истори", "опыт"]):
        return "story", PROMPT_STORY
    return "news", PROMPT_NEWS


def safe_json_parse(raw):
    if not raw:
        return None
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            fixed = re.sub(r",\s*}", "}", candidate)
            fixed = re.sub(r",\s*]", "]", fixed)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
    return None


def try_model(client, model_name, prompt):
    try:
        print("[rewriter] Пробую: " + model_name)
        response = client.models.generate_content(model=model_name, contents=prompt)
        raw = response.text if hasattr(response, "text") else str(response)
        print("[rewriter] RAW (600):\n" + raw[:600] + "\n---END---")
        parsed = safe_json_parse(raw)
        if parsed:
            print("[rewriter] OK: " + str(list(parsed.keys())))
        return parsed
    except Exception as e:
        print("[rewriter] " + model_name + ": " + type(e).__name__ + ": " + str(e))
        return None


def rewrite_article(title, body, api_key, model_name="gemini-3.6-flash", summary=""):
    if not api_key:
        print("[rewriter] Нет GEMINI_API_KEY")
        return None

    style, prompt_template = detect_style(title, summary, body)
    rubric = detect_rubric(title, summary, body)
    print("[rewriter] Стиль: " + style + " | Рубрика: " + rubric["name"])

    prompt = prompt_template.format(title=title, body=body[:8000])

    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print("[rewriter] Клиент: " + str(e))
        return None

    for m in [model_name] + [x for x in FALLBACK_MODELS if x != model_name]:
        result = try_model(client, m, prompt)
        if result:
            result["style"] = style
            result["rubric_name"] = rubric["name"]
            result["hashtags"] = rubric["hashtags"]
            return result
    return None
