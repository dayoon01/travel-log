"""여행 폴더의 사진·영상에서 촬영 위치와 시각을 읽고, 가까운 것끼리 묶어 '지점' 초안을 만든다.

    python tools/extract.py trips/<여행폴더>

결과
- trips/<여행>/_media.json : 파일별 위치·시각·크기 (build.py가 읽음, 매번 새로 씀)
- trips/<여행>/trip.json   : 없을 때만 뼈대를 만든다. 제목·본문·캡션은 여기에 채운다.
                             이미 있으면 덮어쓰지 않고, 새로 묶인 지점 구성만 화면에 보여 준다.
"""
import json
import math
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ExifTags

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm"}
GAP_MIN = 60        # 이 시간(분) 넘게 비면 새 지점
RADIUS_M = 400      # 지점 중심에서 이 거리(m) 넘게 벗어나면 새 지점


def dist_m(a, b):
    r = math.radians
    dlat, dlng = r(b[0] - a[0]), r(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(r(a[0])) * math.cos(r(b[0])) * math.sin(dlng / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def dms(v, ref):
    d, m, s = (float(x) for x in v)
    deg = d + m / 60 + s / 3600
    return -deg if ref in ("S", "W") else deg


def read_photo(p):
    im = Image.open(p)
    exif = im.getexif()
    w, h = im.size
    if exif.get(ExifTags.Base.Orientation) in (5, 6, 7, 8):
        w, h = h, w
    sub = exif.get_ifd(ExifTags.IFD.Exif)
    stamp = sub.get(ExifTags.Base.DateTimeOriginal) or exif.get(ExifTags.Base.DateTime)
    t = datetime.strptime(stamp, "%Y:%m:%d %H:%M:%S") if stamp else datetime.fromtimestamp(p.stat().st_mtime)
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    lat = lng = None
    if gps.get(2) and gps.get(4):
        lat, lng = round(dms(gps[2], gps.get(1, "N")), 6), round(dms(gps[4], gps.get(3, "E")), 6)
    return {"file": p.name, "kind": "photo", "time": t.isoformat(timespec="minutes"), "lat": lat, "lng": lng, "w": w, "h": h,
            "timeFromExif": bool(stamp)}


def read_video(p):
    t = datetime.fromtimestamp(p.stat().st_mtime)
    return {"file": p.name, "kind": "video", "time": t.isoformat(timespec="minutes"), "lat": None, "lng": None, "timeFromExif": False}


def borrow_location(items):
    """위치 없는 항목(영상, GPS 꺼진 사진)은 시간상 가장 가까운 사진(30분 이내)의 위치를 빌린다."""
    located = [x for x in items if x["lat"] is not None]
    for x in items:
        if x["lat"] is not None or not located:
            continue
        t = datetime.fromisoformat(x["time"])
        near = min(located, key=lambda y: abs((datetime.fromisoformat(y["time"]) - t).total_seconds()))
        if abs((datetime.fromisoformat(near["time"]) - t).total_seconds()) <= 1800:
            x["lat"], x["lng"], x["locationFrom"] = near["lat"], near["lng"], near["file"]


def cluster(items):
    stops, cur = [], None
    for x in items:
        if x["lat"] is None:
            continue
        t = datetime.fromisoformat(x["time"])
        if cur:
            c = (sum(m["lat"] for m in cur) / len(cur), sum(m["lng"] for m in cur) / len(cur))
            gap = (t - datetime.fromisoformat(cur[-1]["time"])).total_seconds() / 60
            if gap <= GAP_MIN and dist_m(c, (x["lat"], x["lng"])) <= RADIUS_M:
                cur.append(x)
                continue
            stops.append(cur)
        cur = [x]
    if cur:
        stops.append(cur)
    return stops


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    trip = Path(sys.argv[1]).resolve()
    src = trip / "photos"
    items = []
    for p in sorted(src.iterdir()):
        ext = p.suffix.lower()
        if ext in PHOTO_EXT:
            items.append(read_photo(p))
        elif ext in VIDEO_EXT:
            items.append(read_video(p))
    items.sort(key=lambda x: x["time"])
    borrow_location(items)
    (trip / "_media.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    groups = cluster(items)
    lost = [x["file"] for x in items if x["lat"] is None]
    print(f"파일 {len(items)}개 · 지점 {len(groups)}곳 · 위치 없음 {len(lost)}개")
    for i, g in enumerate(groups, 1):
        print(f"  s{i:02d}  {g[0]['time'][5:16].replace('T', ' ')}~{g[-1]['time'][11:16]}  {len(g)}개  {', '.join(m['file'] for m in g)}")
    if lost:
        print("  위치를 못 정한 파일:", ", ".join(lost), "→ trip.json의 지점 photos에 직접 넣으세요.")

    tj = trip / "trip.json"
    if tj.exists():
        print(f"{tj.name}이 이미 있어 그대로 둡니다. 위 묶음과 비교해 필요하면 직접 고치세요.")
        return
    skeleton = {
        "title": trip.name, "subtitle": "", "eyebrow": "", "intro": [""], "meta": [],
        "days": [{"date": d, "label": ""} for d in sorted({m["time"][:10] for g in groups for m in g})],
        "stops": [{"id": f"s{i:02d}", "badge": "", "title": "", "route": "", "text": [""], "note": "",
                   "photos": [m["file"] for m in g], "captions": {m["file"]: "" for m in g}}
                  for i, g in enumerate(groups, 1)],
        "outro": [""],
    }
    tj.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{tj.name} 뼈대를 만들었습니다. 제목·본문·캡션을 채운 뒤 build.py를 실행하세요.")


if __name__ == "__main__":
    main()
