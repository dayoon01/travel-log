"""trip.json + _media.json → dist/<여행>/index.html (사진은 웹용으로 줄여 복사).

    python tools/build.py              # trips/ 아래 모든 여행
    python tools/build.py kyoto-osaka-2026

dist/ 폴더를 그대로 GitHub Pages·Cloudflare Pages 등에 올리면 된다.
사진은 EXIF(위치·기기 정보)를 지운 사본만 dist/에 들어간다.
"""
import html
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
TRIPS, DIST = ROOT / "trips", ROOT / "dist"
TEMPLATE = Path(__file__).with_name("template.html")
INDEX_TEMPLATE = Path(__file__).with_name("index_template.html")
FULL, THUMB = 1800, 720
WEEK = "월화수목금토일"
DAY_COLORS = ["#c0603a", "#3f7d5c", "#3c63a8", "#8a5a9c", "#b5832a", "#2f8a8a", "#a8434f"]


def dist_km(a, b):
    r = math.radians
    h = math.sin(r(b[0] - a[0]) / 2) ** 2 + math.cos(r(a[0])) * math.cos(r(b[0])) * math.sin(r(b[1] - a[1]) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def zoom_for(spread_m):
    for limit, z in ((300, 17), (700, 16), (1500, 15), (4000, 14), (10000, 13)):
        if spread_m <= limit:
            return z
    return 12


def md(t):
    return f"{t.month}.{t.day}"


def resize(src, dst, size):
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((size, size), Image.LANCZOS)
        im.save(dst, quality=84, optimize=True, progressive=True)  # exif를 넘기지 않으므로 위치 정보가 빠진다


def build_trip(slug):
    src = TRIPS / slug
    trip = json.loads((src / "trip.json").read_text(encoding="utf-8"))
    media = {m["file"]: m for m in json.loads((src / "_media.json").read_text(encoding="utf-8"))}
    out = DIST / slug
    days = trip.get("days", [])
    day_idx = {d["date"]: i for i, d in enumerate(days)}

    stops, prev, total_km, n_photo, n_video = [], None, 0.0, 0, 0
    for n, s in enumerate(trip["stops"], 1):
        items = [media[f] for f in s["photos"] if f in media]
        missing = [f for f in s["photos"] if f not in media]
        if missing:
            print(f"  경고: {s['id']}의 파일을 찾지 못함 → {', '.join(missing)}")
        pts = [(m["lat"], m["lng"]) for m in items if m.get("lat") is not None]
        if s.get("c"):
            c = tuple(s["c"])
        elif pts:
            c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        else:
            print(f"  경고: {s['id']}에 위치가 없어 건너뜀 (trip.json에 \"c\": [위도, 경도]를 넣으세요)")
            continue
        spread = max([dist_km(c, p) * 1000 for p in pts] or [0])
        times = sorted(datetime.fromisoformat(m["time"]) for m in items)
        place = s.get("place") or s["title"].split(" — ")[0]
        di = day_idx.get(times[0].date().isoformat(), 0) if times else 0
        leg = dist_km(prev, c) if prev else None
        total_km += leg or 0
        prev = c
        out_media = []
        for m in items:
            t = datetime.fromisoformat(m["time"])
            cap = s.get("captions", {}).get(m["file"], "")
            entry = {"file": m["file"], "caption": cap, "sub": f"{place} · {md(t)} {t:%H:%M}", "time": f"{t:%H:%M}", "kind": m["kind"],
                     "lat": m.get("lat"), "lng": m.get("lng")}
            if m["kind"] == "photo":
                stem = Path(m["file"]).stem + ".jpg"
                resize(src / "photos" / m["file"], out / "img" / stem, FULL)
                resize(src / "photos" / m["file"], out / "thumb" / stem, THUMB)
                entry.update(src=f"img/{stem}", thumb=f"thumb/{stem}", w=m["w"], h=m["h"])
                n_photo += 1
            else:
                dst = out / "video" / m["file"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists():
                    shutil.copy2(src / "photos" / m["file"], dst)
                entry.update(src=f"video/{m['file']}")
                n_video += 1
            out_media.append(entry)
        if times:
            span = f"{md(times[0])} {times[0]:%H:%M}" + (f"~{times[-1]:%H:%M}" if times[-1] != times[0] else "")
        else:
            span = ""
        acts = s.get("acts") or [[e["time"], e["caption"]] for e in out_media if e["caption"]]
        stops.append({"id": s["id"], "n": n, "day": di, "badge": s.get("badge", ""), "title": s["title"], "route": s.get("route", ""),
                      "text": s.get("text", []), "note": s.get("note", ""), "c": [round(c[0], 6), round(c[1], 6)],
                      "z": s.get("z") or zoom_for(spread), "span": span, "leg": round(leg, 1) if leg is not None else None,
                      "acts": acts, "media": out_media})

    day_out = []
    for i, d in enumerate(days):
        t = datetime.fromisoformat(d["date"])
        day_out.append({"n": i + 1, "md": md(t), "wd": WEEK[t.weekday()], "label": d.get("label", ""),
                        "color": d.get("color") or DAY_COLORS[i % len(DAY_COLORS)]})
    stats = [[str(len(days)), "일"], [str(len(stops)), "기록 지점"], [str(n_photo), "사진"]]
    if n_video:
        stats.append([str(n_video), "영상"])
    stats.append([f"{total_km:,.0f}", "이동 거리(km, 직선)"])
    data = {"trip": {k: trip.get(k) for k in ("title", "subtitle", "eyebrow", "intro", "meta", "outro", "theme", "cover")},
            "days": day_out, "stops": stops, "stats": stats}

    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("__TITLE__", html.escape(f"{trip['title']} {trip.get('subtitle', '')}".strip()))
    page = page.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    cover = next((m["thumb"] for s in stops for m in s["media"] if m.get("thumb")), "")
    print(f"{slug}: 지점 {len(stops)} · 사진 {n_photo} · 영상 {n_video} · {total_km:.0f} km → {out / 'index.html'}")
    first = min((m["time"] for m in media.values()), default="")
    return {"slug": slug, "title": trip["title"], "subtitle": trip.get("subtitle", ""), "cover": f"{slug}/{cover}" if cover else "",
            "date": first[:10], "stops": len(stops), "photos": n_photo, "km": round(total_km)}


def main():
    slugs = sys.argv[1:] or sorted(p.name for p in TRIPS.iterdir() if (p / "trip.json").exists())
    cards = [build_trip(s) for s in slugs]
    if not sys.argv[1:]:  # 전체 빌드일 때만 목록 페이지를 새로 쓴다
        cards.sort(key=lambda c: c["date"], reverse=True)
        page = INDEX_TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", json.dumps(cards, ensure_ascii=False).replace("</", "<\\/"))
        (DIST / "index.html").write_text(page, encoding="utf-8")
        print(f"목록 페이지: {DIST / 'index.html'}")


if __name__ == "__main__":
    main()
