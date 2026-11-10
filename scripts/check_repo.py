"""Проверки репозитория для pre-commit и GitHub Actions CI.

Запуск:
  python scripts/check_repo.py --staged       # проверка индексированных файлов перед коммитом
  python scripts/check_repo.py --all          # проверка всех отслеживаемых файлов в CI
  python scripts/check_repo.py --verify-dist  # проверка целостности и актуальности web/dist
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.log",
    "YandexMusicRemote.exe",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
)
ALLOWED_EXCEPTIONS: frozenset[str] = frozenset({".env.example"})

CONFLICT_MARKER_RE = re.compile(r"^(?:<{7}(?: .*)?|>{7}(?: .*)?)$", re.MULTILINE)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Яндекс OAuth-токен (y0_...)", re.compile(r"\by0_[A-Za-z0-9_-]{20,}\b")),
    ("Яндекс OAuth-токен (AQAAAA.../AgAAAA...)", re.compile(r"\bA[Qg]AAAA[A-Za-z0-9_-]{20,}\b")),
    ("GitHub Personal Access Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("GitHub Fine-Grained Token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("Приватный криптографический ключ", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
)

ENV_ASSIGN_RE = re.compile(r"^[ \t]*YANDEX_MUSIC_TOKEN[ \t]*=[ \t]*([^\r\n#]*?)[ \t]*$", re.MULTILINE)
SAFE_TOKEN_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "",
        '""',
        "''",
        "ваш_токен_яндекс_музыки",
        "your_token_here",
        "test-token",
    }
)

ASSET_REF_RE = re.compile(r"""(?:src|href)=["']/assets/([^"'?#]+)["']""")


def _git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def staged_files(cwd: Path = ROOT) -> list[str]:
    out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", cwd=cwd).stdout
    return [item for item in out.decode("utf-8", errors="replace").split("\0") if item]


def tracked_files(cwd: Path = ROOT) -> list[str]:
    out = _git("ls-files", "-z", cwd=cwd).stdout
    return [item for item in out.decode("utf-8", errors="replace").split("\0") if item]


def read_staged_bytes(rel_path: str, cwd: Path = ROOT) -> bytes:
    return _git("show", f":{rel_path}", cwd=cwd).stdout


def is_forbidden_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    if name in ALLOWED_EXCEPTIONS or normalized in ALLOWED_EXCEPTIONS:
        return False
    for pattern in FORBIDDEN_PATTERNS:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def scan_content(rel_path: str, data: bytes) -> list[str]:
    if b"\x00" in data[:8192]:
        return []
    text = data.decode("utf-8", errors="replace")
    errors: list[str] = []

    if CONFLICT_MARKER_RE.search(text):
        errors.append(f"{rel_path}: обнаружены неразрешённые маркеры конфликта слияния (<<<<<<< / >>>>>>>)")

    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{rel_path}: обнаружен возможный секрет ({label})")

    for match in ENV_ASSIGN_RE.finditer(text):
        raw_val = match.group(1).strip().strip('"').strip("'")
        if raw_val in SAFE_TOKEN_PLACEHOLDERS or raw_val.startswith("<") or raw_val.startswith("$"):
            continue
        errors.append(f"{rel_path}: обнаружено непустое значение YANDEX_MUSIC_TOKEN")

    return errors


def check_files(*, staged: bool, cwd: Path = ROOT) -> list[str]:
    paths = staged_files(cwd) if staged else tracked_files(cwd)
    errors: list[str] = []
    for rel_path in paths:
        if is_forbidden_path(rel_path):
            errors.append(f"{rel_path}: запрещённый к коммиту файл")
            continue
        if staged:
            data = read_staged_bytes(rel_path, cwd)
        else:
            full = cwd / rel_path
            if not full.is_file():
                continue
            data = full.read_bytes()
        errors.extend(scan_content(rel_path, data))
    return errors


def verify_dist(cwd: Path = ROOT) -> list[str]:
    errors: list[str] = []
    dist_dir = cwd / "web" / "dist"
    index_html = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"

    if not index_html.is_file():
        return ["web/dist/index.html отсутствует. Выполните: npm --prefix web run build"]

    html = index_html.read_text(encoding="utf-8")
    referenced = set(ASSET_REF_RE.findall(html))
    if not referenced:
        errors.append("web/dist/index.html не содержит ссылок на собранные бандлы /assets/*")

    existing = {p.name for p in assets_dir.iterdir() if p.is_file()} if assets_dir.is_dir() else set()
    missing = sorted(referenced - existing)
    stale = sorted(existing - referenced)

    for name in missing:
        errors.append(f"web/dist/index.html ссылается на отсутствующий файл web/dist/assets/{name}")
    for name in stale:
        errors.append(f"В web/dist/assets/ остался устаревший файл {name}. Пересоберите web/dist")

    unstaged = _git("diff", "--name-only", "--", "web/dist", cwd=cwd).stdout.decode("utf-8").strip()
    untracked = _git("ls-files", "--others", "--exclude-standard", "--", "web/dist", cwd=cwd).stdout.decode("utf-8").strip()
    if unstaged or untracked:
        errors.append(
            "Сборка web/dist не совпадает с индексом Git (изменены исходники в web/). "
            "Выполните: npm --prefix web run build && git add web/dist"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Проверки безопасности и целостности репозитория")
    parser.add_argument("--staged", action="store_true", help="Проверить индексированные файлы (pre-commit)")
    parser.add_argument("--all", action="store_true", help="Проверить все отслеживаемые файлы (CI)")
    parser.add_argument("--verify-dist", action="store_true", help="Проверить синхронизацию web/dist")
    args = parser.parse_args(argv)

    if not (args.staged or args.all or args.verify_dist):
        parser.error("Укажите хотя бы один режим: --staged, --all или --verify-dist")

    errors: list[str] = []
    if args.staged:
        errors.extend(check_files(staged=True))
    if args.all:
        errors.extend(check_files(staged=False))
    if args.verify_dist:
        errors.extend(verify_dist())

    if errors:
        print("Проверка репозитория не пройдена:", file=sys.stderr)
        for item in errors:
            print(f"  - {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
