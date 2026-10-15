"""예시 여행 사진 생성기.

실제 사진이 없을 때 파이프라인을 시험하려고, 촬영 위치(GPS)와 촬영 시각이
EXIF에 들어 있는 가짜 사진을 만든다. 실제 여행에서는 이 단계가 필요 없다.

    python tools/make_samples.py
"""
import math
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ExifTags

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "trips" / "kyoto-osaka-2026" / "photos"
FONT = "C:/Windows/Fonts/malgunbd.ttf"
FONT_LIGHT = "C:/Windows/Fonts/malgun.ttf"

# (장소, 위도, 경도, 날짜, [(시각, 장면), ...])
STOPS = [
    ("간사이국제공항", 34.4320, 135.2304, "2026-04-03", [("09:42", "도착 로비"), ("10:15", "하루카 특급 승강장")]),
    ("교토역", 34.9858, 135.7588, "2026-04-03", [("11:48", "교토역 대계단"), ("11:55", "교토타워"), ("12:20", "버스 1일권")]),
    ("후시미이나리 대사", 34.9671, 135.7727, "2026-04-03", [("13:31", "천본도리이 입구"), ("13:52", "붉은 도리이 터널"), ("14:30", "여우 석상"), ("14:48", "참배길 노점")]),
    ("기요미즈데라", 34.9949, 135.7850, "2026-04-03", [("16:18", "니오몬"), ("16:35", "무대에서 본 교토 시내"), ("16:50", "벚꽃 너머 본당")]),
    ("산넨자카·니넨자카", 34.9965, 135.7811, "2026-04-03", [("17:12", "돌계단 골목"), ("17:25", "야사카탑"), ("17:40", "말차 아이스크림")]),
    ("기온 하나미코지", 35.0037, 135.7750, "2026-04-03", [("19:02", "저녁 등불 골목"), ("19:30", "오반자이 저녁상")]),
    ("아라시야마 대나무숲", 35.0170, 135.6713, "2026-04-04", [("08:08", "이른 아침 대숲길"), ("08:20", "하늘로 뻗은 대나무"), ("08:41", "노노미야 신사")]),
    ("도게쓰교", 35.0129, 135.6777, "2026-04-04", [("09:33", "도게쓰교와 아라시야마"), ("09:50", "가쓰라강 보트")]),
    ("금각사", 35.0394, 135.7292, "2026-04-04", [("12:41", "경호지 너머 금각"), ("12:55", "정원 산책로")]),
    ("니시키 시장", 35.0050, 135.7649, "2026-04-04", [("15:02", "시장 아케이드"), ("15:20", "다시마키 계란말이"), ("15:34", "두유 도넛")]),
    ("가모가와 산조", 35.0090, 135.7720, "2026-04-04", [("18:28", "강변에 앉은 사람들"), ("18:45", "해 질 녘 산조대교")]),
    ("오사카성", 34.6873, 135.5262, "2026-04-05", [("10:03", "해자와 성벽"), ("10:30", "천수각"), ("10:52", "니시노마루 정원 벚꽃")]),
    ("구로몬 시장", 34.6655, 135.5068, "2026-04-05", [("12:31", "시장 입구"), ("12:45", "구운 가리비")]),
    ("도톤보리", 34.6687, 135.5013, "2026-04-05", [("19:28", "글리코 간판"), ("19:40", "운하 야경"), ("20:05", "다코야키")]),
]

PALETTES = [
    ((236, 214, 186), (122, 156, 186)), ((214, 92, 62), (245, 214, 170)), ((60, 92, 70), (196, 222, 186)),
    ((180, 120, 160), (250, 226, 214)), ((40, 54, 88), (232, 168, 96)), ((92, 140, 108), (230, 240, 210)),
]


def to_dms(v):
    v = abs(v)
    d = int(v)
    m = int((v - d) * 60)
    s = round(((v - d) * 60 - m) * 60, 2)
    return (float(d), float(m), s)


def jitter(lat, lng, meters):
    r = meters * math.sqrt(random.random())
    t = random.random() * 2 * math.pi
    return lat + r * math.cos(t) / 111_000, lng + r * math.sin(t) / (111_000 * math.cos(math.radians(lat)))


def painting(w, h, pal, seed):
    rnd = random.Random(seed)
    top, bottom = pal
    img = Image.new("RGB", (w, h))
    px = ImageDraw.Draw(img)
    for y in range(h):
        k = y / h
        px.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - k) + bottom[i] * k) for i in range(3)))
    blobs = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    for _ in range(7):
        r = rnd.randint(h // 8, h // 3)
        x, y = rnd.randint(0, w), rnd.randint(h // 3, h)
        c = tuple(min(255, int(v * rnd.uniform(0.7, 1.25))) for v in (bottom if rnd.random() < .5 else top))
        bd.ellipse([x - r, y - r, x + r, y + r], fill=c + (110,))
    blobs = blobs.filter(ImageFilter.GaussianBlur(60))
    img.paste(blobs, (0, 0), blobs)
    # 지평선 실루엣
    hz = int(h * rnd.uniform(.62, .75))
    pts = [(0, h)]
    for x in range(0, w + 40, 40):
        pts.append((x, hz - rnd.randint(0, int(h * .12))))
    pts.append((w, h))
    sil = tuple(int(v * .35) for v in top)
    ImageDraw.Draw(img).polygon(pts, fill=sil)
    return img


def main():
    random.seed(7)
    OUT.mkdir(parents=True, exist_ok=True)
    big = ImageFont.truetype(FONT, 64)
    small = ImageFont.truetype(FONT_LIGHT, 28)
    n = 0
    for si, (place, lat, lng, day, shots) in enumerate(STOPS):
        for ti, (hhmm, scene) in enumerate(shots):
            n += 1
            portrait = (si + ti) % 4 == 3
            w, h = (1067, 1600) if portrait else (1600, 1067)
            img = painting(w, h, PALETTES[si % len(PALETTES)], si * 10 + ti)
            d = ImageDraw.Draw(img)
            d.text((60, h - 190), scene, font=big, fill=(255, 255, 255))
            d.text((62, h - 105), f"{place} · 예시 사진", font=small, fill=(255, 255, 255))
            plat, plng = jitter(lat, lng, 70)
            ex = Image.Exif()
            ex[ExifTags.Base.Make] = "Example"
            ex[ExifTags.Base.Model] = "Sample Camera"
            sub = ex.get_ifd(ExifTags.IFD.Exif)
            stamp = datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M").strftime("%Y:%m:%d %H:%M:%S")
            sub[ExifTags.Base.DateTimeOriginal] = stamp
            gps = ex.get_ifd(ExifTags.IFD.GPSInfo)
            gps[ExifTags.GPS.GPSLatitudeRef] = "N" if plat >= 0 else "S"
            gps[ExifTags.GPS.GPSLatitude] = to_dms(plat)
            gps[ExifTags.GPS.GPSLongitudeRef] = "E" if plng >= 0 else "W"
            gps[ExifTags.GPS.GPSLongitude] = to_dms(plng)
            img.save(OUT / f"IMG_{n:04d}.jpg", quality=86, exif=ex.tobytes())
    print(f"{n}장 생성 → {OUT}")


if __name__ == "__main__":
    main()
