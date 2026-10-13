from dataclasses import dataclass
import os
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_root: Path
    origins: tuple[str, ...] = ('http://localhost:3000', 'http://127.0.0.1:3000')
    cookie_secure: bool = False
    allow_fixtures: bool = False
    session_days: int = 7
    local_catalog: bool = False

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.environ['DATABASE_URL'],
            storage_root=Path(os.getenv('STORAGE_ROOT', './storage')).resolve(),
            origins=tuple(x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if x.strip()),
            cookie_secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
            allow_fixtures=os.getenv('ALLOW_FIXTURES', 'false').lower() == 'true',
            session_days=int(os.getenv('SESSION_DAYS', '7')),
            local_catalog=os.getenv('TP_ENVIRONMENT') in ('local_project','isolated_test'),
        )
