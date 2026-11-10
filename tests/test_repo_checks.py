from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_repo",
    Path(__file__).resolve().parents[1] / "scripts" / "check_repo.py",
)
assert _SPEC is not None and _SPEC.loader is not None
check_repo = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_repo)


def test_forbidden_paths_block_env_and_logs_but_allow_env_example():
    assert check_repo.is_forbidden_path(".env") is True
    assert check_repo.is_forbidden_path(".env.local") is True
    assert check_repo.is_forbidden_path("cdp/server-cdp.log") is True
    assert check_repo.is_forbidden_path("YandexMusicRemote.exe") is True
    assert check_repo.is_forbidden_path(".env.example") is False
    assert check_repo.is_forbidden_path("src/ym_remote/interfaces/asgi.py") is False


def test_scan_content_catches_tokens_and_conflict_markers():
    clean = b"YANDEX_MUSIC_TOKEN=\n# Next line comment\nLOCAL_IP=\nYANDEX_MUSIC_TOKEN=test-token\n=====\n"
    assert check_repo.scan_content(".env.example", clean) == []

    fake_token = b"y0_" + (b"B" * 28)
    token_leak = b"YANDEX_MUSIC_TOKEN=" + fake_token + b"\n"
    errors = check_repo.scan_content("config.txt", token_leak)
    assert any("OAuth" in err for err in errors)
    assert any("YANDEX_MUSIC_TOKEN" in err for err in errors)

    left = b"<" * 7
    right = b">" * 7
    conflict = b"line1\n" + left + b" HEAD\nmine\n=======\ntheirs\n" + right + b" dev\n"
    conflict_errors = check_repo.scan_content("app.py", conflict)
    assert len(conflict_errors) == 1
    assert "маркеры конфликта" in conflict_errors[0]
