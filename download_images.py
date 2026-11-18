"""Скачивает реальные фото товаров/категорий с Wikimedia Commons.
Имена файлов = ровно те, что ожидает seed.py (.png), поэтому seed не трогаем."""
import json, os, ssl, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TrophyShop/1.0"
API = "https://commons.wikimedia.org/w/api.php"
CTX = ssl.create_default_context()

PRODUCTS = {
    "rod-hand.png": "spinning rod cork handle",
    "rod-camo.png": "fishing rod boat lake",
    "rods-lake.png": "fishing rods lake sunset",
    "reel-black.png": "spinning fishing reel",
    "reel-talica.png": "fishing reel closeup",
    "reel-spool.png": "fishing reel spool line",
    "braid-pack.png": "braided fishing line spool",
    "line-spool.png": "fishing monofilament line spool",
    "lure-pack.png": "fishing lures tackle box",
    "lure-vib.png": "fishing rattlebait lure",
    "lure-spoon.png": "fishing spoon lure metal",
    "lure-crank.png": "fishing crankbait lure",
    "scope-side.png": "rifle scope optic",
    "scope-long.png": "telescopic rifle scope",
    "decoy-duck.png": "mallard duck decoy",
    "game-bag.png": "hunting game bag canvas",
    "jacket-winter.png": "winter camouflage jacket",
    "jacket-camo.png": "camo softshell hunting jacket",
    "boots-black.png": "rubber EVA winter boots",
    "boots-pair.png": "rubber boots pair",
    "tent-forest.png": "camping tent forest",
    "tent-camp.png": "camping tent lake",
    "thermos-steel.png": "stainless steel thermos flask",
    "thermos-set.png": "thermos camping flask",
    "knife-black.png": "folding pocket knife",
    "knife-wood.png": "hunting knife wooden handle",
}
CATEGORIES = {
    "fishing.png": "fishing rod lake water",
    "hunting.png": "hunter binoculars field",
    "clothes.png": "camouflage clothing forest",
    "tourism.png": "camping tent pine forest",
    "knives.png": "hunting knife leather sheath",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30, context=CTX)


def _looks_like_image(blob):
    return blob[:3] == b"\xff\xd8\xff" or blob[:8] == b"\x89PNG\r\n\x1a\n"


def fetch(query, dest):
    params = {"action": "query", "generator": "search", "gsrsearch": query,
              "gsrnamespace": "6", "gsrlimit": "12", "prop": "imageinfo",
              "iiprop": "url|mime", "iiurlwidth": "800", "format": "json"}
    data = json.loads(_get(API + "?" + urllib.parse.urlencode(params)).read())
    pages = sorted(data.get("query", {}).get("pages", {}).values(),
                   key=lambda p: p.get("index", 999))
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        if not info.get("mime", "").startswith("image/"):
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        try:
            blob = _get(url).read()
        except Exception:
            continue
        if len(blob) < 8000 or not _looks_like_image(blob):
            continue  # отсекаем схемы, иконки, битые и HTML-ошибки
        with open(dest, "wb") as f:
            f.write(blob)
        return True
    return False


def run():
    ok, fail = 0, []
    for group, folder in ((PRODUCTS, "products"), (CATEGORIES, "categories")):
        out = os.path.join(ROOT, "app", "static", "img", folder)
        os.makedirs(out, exist_ok=True)
        for name, query in group.items():
            dest = os.path.join(out, name)
            found = fetch(query, dest)
            print(("OK  " if found else "FAIL") + f"  {folder}/{name}")
            ok, fail = (ok + 1, fail) if found else (ok, fail + [name])
            time.sleep(0.4)  # не словить rate-limit
    print(f"\nСкачано: {ok}, не найдено: {len(fail)}")
    if fail:
        print("Не найдено:", ", ".join(fail))
        print("→ сохрани любое фото из браузера под этим именем в ту же папку.")


if __name__ == "__main__":
    run()