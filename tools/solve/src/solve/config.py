"""저장소 루트를 찾고 solved.ac 인증 정보를 불러옵니다."""

import os
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = ".env"
CLIENT_ID_KEY = "SOLVEDAC_CLIENT_ID"
CLIENT_SECRET_KEY = "SOLVEDAC_CLIENT_SECRET"


class ConfigError(Exception):
    """저장소나 인증 정보를 찾지 못하면 발생합니다."""


@dataclass(frozen=True)
class Credentials:
    client_id: str
    client_secret: str


def find_repo_root(start: Path | None = None) -> Path:
    """`start`부터 상위로 올라가며 `.git`이 있는 디렉터리를 찾습니다."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / ".git").exists():
            return directory
    raise ConfigError(f"git 저장소를 찾을 수 없습니다: {current}")


def parse_env_file(text: str) -> dict[str, str]:
    """KEY=VALUE 줄을 읽습니다. 빈 줄과 주석은 건너뛰고, 값을 감싼 따옴표는 제거합니다."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_credentials(repo_root: Path) -> Credentials:
    """환경 변수가 `.env`보다 우선합니다. 둘 다 없으면 ConfigError를 냅니다."""
    env_path = repo_root / ENV_FILE
    file_values = parse_env_file(env_path.read_text(encoding="utf-8")) if env_path.exists() else {}

    def pick(key: str) -> str:
        value = os.environ.get(key) or file_values.get(key)
        if not value:
            raise ConfigError(f"{key}가 없습니다. {env_path} 또는 환경 변수에 설정하세요.")
        return value

    return Credentials(pick(CLIENT_ID_KEY), pick(CLIENT_SECRET_KEY))
