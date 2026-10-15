"""전체를 다시 빌드하고 dist/를 GitHub의 gh-pages 브랜치로 올린다.

    python tools/deploy.py

- 원본 사진은 올라가지 않는다. dist/에 들어간 웹용 사본(EXIF 제거)만 올라간다.
- gh-pages 브랜치는 매번 커밋 하나로 새로 덮어쓴다(지난 배포 이력을 쌓지 않아 저장소가 커지지 않는다).
- 올린 뒤 1~2분 지나면 https://<계정>.github.io/<저장소>/ 에 반영된다.
"""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def git(*args, cwd=DIST):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True, encoding="utf-8").stdout.strip()


def main():
    subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")], check=True)
    remote = git("remote", "get-url", "origin", cwd=ROOT)
    (DIST / ".nojekyll").write_text("", encoding="utf-8")  # GitHub Pages의 Jekyll 처리를 끈다
    if (DIST / ".git").exists():  # 매번 새로 만들어 커밋 하나만 남긴다 (윈도우의 읽기 전용 파일도 지운다)
        shutil.rmtree(DIST / ".git", onerror=lambda f, p, _: (os.chmod(p, stat.S_IWRITE), f(p)))
    git("init", "-q", "-b", "gh-pages")
    git("add", "-A")
    git("commit", "-q", "-m", "배포")
    git("push", "-q", "--force", remote, "gh-pages:gh-pages")
    print("올렸습니다. 1~2분 뒤 GitHub Pages 주소에서 확인하세요.")


if __name__ == "__main__":
    main()
