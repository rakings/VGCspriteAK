"""Sprite animati dei Pokémon per il sito rAKings VGC.

Scarica da Pokémon Showdown le animazioni (sprites/ani/<id>.gif) di tutti i Pokémon e forme,
le converte in WebP animato SENZA PERDITA di qualità (stesso movimento, di solito 10% più leggero) e le salva in ani/<id>.webp.
Gira con il flusso .github/workflows/sprite.yml: da solo al primo caricamento, poi a mano quando
esce un gioco nuovo (Actions -> Sprite animati -> Run workflow). Converte solo i Pokémon che mancano. Nessuna chiave segreta.
"""
import io, json, os, re, sys, time, urllib.request, concurrent.futures as cf
from PIL import Image

BASE = "https://play.pokemonshowdown.com"
CARTELLA = "ani"
UA = {"User-Agent": "rakings-vgc-sprite (https://rakings.github.io/VGCrAKings/)"}
MAX_PER_GIRO = int(os.environ.get("MAX_PER_GIRO", "2000"))


def scarica(url, tentativi=3):
    for i in range(tentativi):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
        time.sleep(2 + i * 3)
    return None


def toid(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def elenco_id():
    dex = json.loads(scarica(BASE + "/data/pokedex.json").decode("utf-8"))
    ids = set()
    for v in dex.values():
        if v.get("num", 0) <= 0:
            continue
        b, f = v.get("baseSpecies", v["name"]), v.get("forme", "")
        ids.add(toid(b) + ("-" + toid(f) if f else ""))
        for c in v.get("cosmeticFormes", []) or []:          # es. Gastrodon-East, Vivillon-Savanna
            ids.add(toid(b) + "-" + toid(c.split("-", 1)[1] if "-" in c else c))
    return sorted(ids)


def converti(gif):
    im = Image.open(io.BytesIO(gif))
    quadri, durate = [], []
    try:
        while True:
            quadri.append(im.convert("RGBA").copy())
            durate.append(max(20, int(im.info.get("duration", 40) or 40)))
            im.seek(im.tell() + 1)
    except EOFError:
        pass
    if not quadri:
        return None
    out = io.BytesIO()                                       # senza perdita: identica alla GIF, di solito più leggera
    quadri[0].save(out, "WEBP", save_all=True, append_images=quadri[1:], duration=durate, loop=0,
                   lossless=True, quality=100, method=4)
    migliore = out.getvalue()
    return migliore


def lavora(sid):
    dest = os.path.join(CARTELLA, sid + ".webp")
    gif = scarica(BASE + "/sprites/ani/" + sid + ".gif")
    if not gif or len(gif) < 5000:                           # niente animazione (o segnaposto): il sito usa l'immagine ferma
        return sid, "manca", 0, 0
    try:
        w = converti(gif)
    except Exception as ex:
        return sid, "errore " + str(ex)[:60], len(gif), 0
    if not w:
        return sid, "vuota", len(gif), 0
    with open(dest, "wb") as f:
        f.write(w)
    return sid, "ok", len(gif), len(w)


def main():
    os.makedirs(CARTELLA, exist_ok=True)
    ids = elenco_id()
    gia = {n[:-5] for n in os.listdir(CARTELLA) if n.endswith(".webp")}
    da_fare = [i for i in ids if i not in gia][:MAX_PER_GIRO]
    print("Pokémon e forme su Showdown:", len(ids), "· già convertiti:", len(gia), "· da provare ora:", len(da_fare))
    tot_g = tot_w = fatti = 0
    with cf.ThreadPoolExecutor(6) as ex:
        for sid, esito, g, w in ex.map(lavora, da_fare):
            if esito == "ok":
                fatti += 1; tot_g += g; tot_w += w
            elif esito != "manca":
                print(" ", sid, esito)
    presenti = sorted(n[:-5] for n in os.listdir(CARTELLA) if n.endswith(".webp"))
    try:
        vecchio = json.load(open("elenco.json", encoding="utf-8")).get("id")
    except Exception:
        vecchio = None
    if vecchio != presenti:                                  # si riscrive solo se cambia (niente commit inutili)
        with open("elenco.json", "w", encoding="utf-8") as f:
            json.dump({"aggiornato": time.strftime("%Y-%m-%d"), "totale": len(presenti), "id": presenti}, f, separators=(",", ":"))
    if fatti:
        print("Convertiti ora:", fatti, "· GIF %.1f MB -> WebP %.1f MB" % (tot_g / 1048576, tot_w / 1048576))
    print("Animazioni disponibili:", len(presenti))


if __name__ == "__main__":
    sys.exit(main())
