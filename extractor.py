import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

print("[extractor] === EXTRACTOR ЗАГРУЖЕН ===")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0 Safari/537.36"
}

# Селекторы основного текста для каждого источника.
# Если сайта нет в списке — используется fallback (все <p> внутри <article>).
SELECTORS = {
    "rbc.ru": "div.article__text",
    "tass.ru": "div.text-content",
    "vedomosti.ru": "div.article__body",
    "forbes.ru": "div.article__text",
    "banki.ru": "div.article__content",
    "kommersant.ru": "div.article_text",
    "lenta.ru": "div.topic-body__content",
    "ria.ru": "div.article__body",
    "frankmedia.ru": "div.article__body",
    "thebell.io": "div.article__body",
    "rueconomics.ru": "div.article__body",
}


def extract_full_text(url):
    """Скачивает страницу и вытаскивает основной текст статьи."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print("[extractor] Ошибка скачивания " + url + ": " + str(e))
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Убираем мусор
    for tag in soup(["script", "style", "aside", "nav", "footer", "form", "header"]):
        tag.decompose()

    domain = urlparse(url).netloc.replace("www.", "")
    selector = SELECTORS.get(domain)

    container = None
    if selector:
        container = soup.select_one(selector)

    # Fallback: <article> или весь документ
    if not container:
        container = soup.find("article") or soup

    paragraphs = container.find_all("p")
    text = "\n\n".join(
        p.get_text(strip=True)
        for p in paragraphs
        if len(p.get_text(strip=True)) > 40
    )

    if not text:
        print("[extractor] Пустой текст для " + url)
        return None

    return text


def extract_image(url):
    """Вытаскивает главную картинку статьи (og:image или первая крупная в тексте)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        img = og["content"]
        if img.startswith("//"):
            img = "https:" + img
        elif img.startswith("/"):
            img = urljoin(url, img)
        return img

    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content"):
        img = tw["content"]
        if img.startswith("//"):
            img = "https:" + img
        elif img.startswith("/"):
            img = urljoin(url, img)
        return img

    for img_tag in soup.find_all("img"):
        src = img_tag.get("src") or img_tag.get("data-src")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = urljoin(url, src)
        if any(x in src.lower() for x in ["icon", "logo", "sprite", "avatar", "1x1", "pixel"]):
            continue
        return src
    return None
