"""Builds the Nuvio premium collection set: static art + import JSON.

Usage: build_set.py <project_dir> [base_url]
"""
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps, ImageStat

sys.stdout.reconfigure(encoding="utf-8")

ROOT = sys.argv[1]
BASE = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "__BASE_URL__"
SRC = os.path.join(ROOT, "nuvio-collections-profile-1-2026-10-30.json")
OUT = os.path.join(ROOT, "premium-set")
CACHE = os.path.join(OUT, ".cache")
W, H = 1280, 720
HERO_W, HERO_H = 1600, 900
TILE_QUALITY, HERO_QUALITY = 80, 70  # jsDelivr refuses tagged packages over 50 MB
TARGET_MEAN = .34
LOGO_AREA = 34000
COLOR_SATURATION = .9
VARIANTS = ("mono", "color")
TEXT_INSTEAD_OF_LOGO = {"cartoon-network", "ghibli"}  # source art has no usable transparency
FONT = "C:/Windows/Fonts/seguisb.ttf"

# collection id -> (title, {folder slug: (title, imdb id, type)}). A slug left out removes that folder.
COLLECTIONS = {
    "collections-discover": ("Para Você", {
        "recommended": ("Recomendados", "tt15239678", "movie"),
        "popular": ("Populares", "tt15398776", "movie"),
        "trending": ("Em Alta", "tt1745960", "movie"),
        "top-rated": ("Mais Bem Avaliados", "tt0068646", "movie"),
        "d52313e3-23ca-4bb1-85c6-800447295788": ("Minisséries", "tt7366338", "series"),
    }),
    "collections-streaming": ("Streaming", {
        "netflix": ("Netflix", "tt4574334", "series"),
        "prime-video": ("Prime Video", "tt1190634", "series"),
        "disney-plus": ("Disney+", "tt8111088", "series"),
        "hbo-max": ("HBO Max", "tt3581920", "series"),
        "apple-tv": ("Apple TV", "tt11280740", "series"),
        "paramount-plus": ("Paramount+", "tt4236770", "series"),
        "crunchyroll": ("Crunchyroll", "tt12343534", "series"),
        "discovery-plus": ("Discovery+", "tt0446809", "series"),
        "starz": ("Starz", "tt3006802", "series"),
    }),
    "collections-genres": ("Gêneros", {
        "action": ("Ação", "tt1392190", "movie"),
        "fantasy": ("Fantasia e Ficção", "tt0120737", "movie"),
        "drama": ("Drama", "tt0111161", "movie"),
        "comedy": ("Comédia", "tt2278388", "movie"),
        "thriller": ("Suspense", "tt0114369", "movie"),
        "crime": ("Crime", "tt0113277", "movie"),
        "horror": ("Terror", "tt0081505", "movie"),
        "romance": ("Romance", "tt3783958", "movie"),
        "mystery": ("Mistério", "tt8946378", "movie"),
        "animation": ("Animação", "tt4633694", "movie"),
        "anime": ("Anime", "tt5311514", "movie"),
        "family": ("Família", "tt1049413", "movie"),
        "history": ("História e Guerra", "tt8579674", "movie"),
        "documentary": ("Documentários", "tt7775622", "movie"),
        "music": ("Música", "tt1727824", "movie"),
        "western": ("Faroeste", "tt0105695", "movie"),
        "reality": ("Reality", "tt0239195", "series"),
    }),
    "collections-themes": ("Temas", {
        "time-travel": ("Viagem no Tempo", "tt0088763", "movie"),
        "revenge": ("Vingança", "tt1663202", "movie"),
        "spy": ("Espionagem", "tt0381061", "movie"),
        "magic": ("Magia", "tt0241527", "movie"),
        "k-drama": ("K-Drama", "tt10850932", "series"),
        "treasure-hunt": ("Caça ao Tesouro", "tt0082971", "movie"),
        "romantic-comedy": ("Comédia Romântica", "tt0098635", "movie"),
        "coming-of-age": ("Amadurecimento", "tt1065073", "movie"),
        "superhero": ("Super-Heróis", "tt0848228", "movie"),
        "space": ("Espaço", "tt0816692", "movie"),
        "martial-arts": ("Artes Marciais", "tt0070034", "movie"),
        "vampire": ("Vampiros", "tt0110148", "movie"),
        "satire": ("Sátira", "tt11286314", "movie"),
    }),
    "collections-studios": ("Estúdios", {
        "marvel": ("Marvel", "tt4154796", "movie"),
        "dc": ("DC", "tt1877830", "movie"),
        "pixar": ("Pixar", "tt2380307", "movie"),
        "lucasfilm": ("Lucasfilm", "tt0076759", "movie"),
        "ghibli": ("Studio Ghibli", "tt0245429", "movie"),
        "dreamworks": ("DreamWorks", "tt0126029", "movie"),
        "cartoon-network": ("Cartoon Network", "tt1305826", "series"),
        "nickelodeon": ("Nickelodeon", "tt0417299", "series"),
    }),
    "collections-decades": ("Décadas", {
        "2020s": ("Anos 2020", "tt1160419", "movie"),
        "2010s": ("Anos 2010", "tt1856101", "movie"),
        "2000s": ("Anos 2000", "tt0468569", "movie"),
        "1990s": ("Anos 90", "tt0110912", "movie"),
        "1980s": ("Anos 80", "tt0083658", "movie"),
        "1970s": ("Anos 70", "tt0078788", "movie"),
        "1960s": ("Anos 60", "tt0056172", "movie"),
        "1950s": ("Anos 50", "tt0052618", "movie"),
    }),
    "collections-world": ("Cinema do Mundo", {
        "brazilian": ("Brasil", "tt0317248", "movie"),
        "latin-american": ("América Latina", "tt3011894", "movie"),
        "korean": ("Coreia", "tt6751668", "movie"),
        "japanese": ("Japão", "tt14039582", "movie"),
        "french": ("França", "tt0211915", "movie"),
        "spanish": ("Espanha", "tt0457430", "movie"),
        "italian": ("Itália", "tt0095765", "movie"),
        "german": ("Alemanha", "tt1016150", "movie"),
        "nordic": ("Países Nórdicos", "tt2106476", "movie"),
        "indian": ("Índia", "tt8178634", "movie"),
        "chinese": ("China", "tt0190332", "movie"),
        "russian": ("Rússia", "tt2802154", "movie"),
        "turkish": ("Turquia", "tt2758880", "movie"),
    }),
}
LOGO_TILES = {"collections-streaming", "collections-studios"}


def curl(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1024:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    subprocess.run(["curl", "-sSL", "--max-time", "60", "-A", "Mozilla/5.0", "-o", path, url], check=True)
    return path


def fetch_still(imdb):
    path = curl(f"https://images.metahub.space/background/large/{imdb}/img",
                os.path.join(CACHE, "stills", imdb + ".jpg"))
    return Image.open(path).convert("RGB")


def fit(im, width, height):
    scale = max(width / im.width, height / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    x, y = (im.width - width) // 2, (im.height - height) // 2
    return im.crop((x, y, x + width, y + height))


def exposure_gamma(gray):
    mean = ImageStat.Stat(gray).mean[0] / 255
    return math.log(TARGET_MEAN) / math.log(max(min(mean, .95), .05))


def grade(im, variant):
    """One treatment per variant, with every image normalized to the same exposure."""
    if variant == "mono":
        gray = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1)
        gamma = exposure_gamma(gray)
        gray = gray.point(lambda v: round(255 * (v / 255) ** gamma))
        return ImageOps.colorize(gray, black=(9, 9, 11), mid=(118, 116, 113), white=(242, 240, 236))
    color = ImageOps.autocontrast(im, cutoff=1, preserve_tone=True)
    gamma = exposure_gamma(ImageOps.grayscale(color))
    color = color.point(lambda v: round(255 * (v / 255) ** gamma))
    return ImageEnhance.Color(color).enhance(COLOR_SATURATION)


def shaded(im):
    mask = Image.new("L", (1, H))
    for y in range(H):
        t = max(0, (y - H * .42) / (H * .58))
        mask.putpixel((0, y), round(236 * t ** 1.4))
    shade = Image.new("RGBA", (W, H), (9, 9, 11, 255))
    shade.putalpha(mask.resize((W, H)))
    return Image.alpha_composite(im.convert("RGBA"), shade)


def text_tile(base, title):
    size = 76
    font = ImageFont.truetype(FONT, size)
    draw = ImageDraw.Draw(base)
    while draw.textlength(title, font=font) > W - 128:
        size -= 2
        font = ImageFont.truetype(FONT, size)
    draw.text((64, H - 56), title, font=font, fill=(255, 255, 255, 255), anchor="ls")
    return base.convert("RGB")


def logo_tile(base, url, slug):
    """Same layout as a title, with the real logo flattened to white."""
    logo = Image.open(curl(url, os.path.join(CACHE, "logos", slug + ".webp"))).convert("RGBA")
    box = logo.getchannel("A").getbbox()
    logo = logo.crop(box)
    scale = min(math.sqrt(LOGO_AREA / (logo.width * logo.height)), W * .46 / logo.width, 112 / logo.height)
    alpha = logo.getchannel("A").resize((round(logo.width * scale), round(logo.height * scale)), Image.LANCZOS)
    white = Image.new("RGBA", alpha.size, (255, 255, 255, 255))
    white.putalpha(alpha)
    base.alpha_composite(white, (64, H - 56 - alpha.height))
    return base.convert("RGB")


def verify(imdb, kind, title):
    path = os.path.join(CACHE, "meta", imdb + ".json")
    curl(f"https://v3-cinemeta.strem.io/meta/{kind}/{imdb}.json", path)
    meta = json.load(open(path, encoding="utf-8")).get("meta") or {}
    return f"{title:24} {imdb:11} {meta.get('name', '??? NOT FOUND')} ({meta.get('releaseInfo', '')})"


def contact_sheet(tiles, variant):
    tw, th, gap, cols = 320, 180, 14, 6
    rows = [[t for t in tiles if t[0] == ctitle] for ctitle, _ in COLLECTIONS.values()]
    height = sum(34 + ((len(r) + cols - 1) // cols) * (th + gap) for r in rows) + 24
    sheet = Image.new("RGB", (cols * (tw + gap) + gap, height), (10, 10, 12))
    draw = ImageDraw.Draw(sheet)
    label = ImageFont.truetype(FONT, 20)
    y = 12
    for row in rows:
        draw.text((gap, y), row[0][0], font=label, fill=(235, 235, 240))
        y += 34
        for i, tile in enumerate(row):
            if i and i % cols == 0:
                y += th + gap
            sheet.paste(tile[2].resize((tw, th), Image.LANCZOS), (gap + (i % cols) * (tw + gap), y))
        y += th + gap
    sheet.save(os.path.join(OUT, f"preview-{variant}.jpg"), "JPEG", quality=78, optimize=True)


def build(variant, source):
    result, tiles = [], []
    for cid, (ctitle, folders) in COLLECTIONS.items():
        col = dict(source[cid])
        col.update(title=ctitle, viewMode="FOLLOW_LAYOUT", pinToTop=True, showAllTab=False,
                   backdropImageUrl=None, focusGlowEnabled=False)
        by_slug = {f["id"].split(".")[-1]: f for f in col["folders"]}
        short = cid.split("-", 1)[1]
        out = []
        for slug, (title, imdb, kind) in folders.items():
            folder = dict(by_slug[slug])
            raw = fetch_still(imdb)
            base = shaded(grade(fit(raw, W, H), variant))
            use_logo = cid in LOGO_TILES and slug not in TEXT_INSTEAD_OF_LOGO
            image = logo_tile(base, folder["coverImageUrl"], slug) if use_logo else text_tile(base, title)
            name = "minisseries" if slug.startswith("d52313e3") else slug
            rel = f"art/{variant}/{short}/{name}.webp"
            hero = f"art/{variant}/hero/{short}-{name}.webp"
            for path in (rel, hero):
                os.makedirs(os.path.dirname(os.path.join(OUT, path)), exist_ok=True)
            image.save(os.path.join(OUT, rel), "WEBP", quality=TILE_QUALITY, method=6)
            grade(fit(raw, HERO_W, HERO_H), variant).save(os.path.join(OUT, hero), "WEBP", quality=HERO_QUALITY, method=6)
            tiles.append((ctitle, title, image))
            folder.update(title=title, tileShape="LANDSCAPE", hideTitle=True, coverEmoji=None,
                          focusGifUrl=None, focusGifEnabled=False, heroVideoUrl=None, titleLogoUrl=None,
                          coverImageUrl=f"{BASE}/{rel}", heroBackdropUrl=f"{BASE}/{hero}")
            out.append(folder)
        col["folders"] = out
        result.append(col)
    with open(os.path.join(OUT, f"nuvio-premium-{variant}.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)
    print(variant, "collections", len(result), "folders", sum(len(c["folders"]) for c in result))
    contact_sheet(tiles, variant)


def main():
    source = {c["id"]: c for c in json.load(open(SRC, encoding="utf-8"))}
    for variant in VARIANTS:
        build(variant, source)


main()
