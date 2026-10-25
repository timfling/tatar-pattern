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
    public_guest_mode: bool = True
    guest_ttl_seconds: int = 86400
    guest_concurrent_jobs: int = 2
    guest_creates_per_minute: int = 20
    guest_gpu_budget: int = 0
    session_days: int = 7
    local_catalog: bool = False
    ai_mvp_enabled: bool = False

    def __post_init__(self):
        if not 1 <= self.guest_ttl_seconds <= 86400:
            raise ValueError("GUEST_TTL_SECONDS must be 1..86400")
        if self.guest_concurrent_jobs < 1 or self.guest_creates_per_minute < 1 or self.guest_gpu_budget < 0:
            raise ValueError("Invalid guest admission limits")

    @classmethod
    def from_env(cls):
        return cls(
            database_url=os.environ['DATABASE_URL'],
            storage_root=Path(os.getenv('STORAGE_ROOT', './storage')).resolve(),
            origins=tuple(x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',') if x.strip()),
            cookie_secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
            allow_fixtures=os.getenv('ALLOW_FIXTURES', 'false').lower() == 'true',
            public_guest_mode=os.getenv('PUBLIC_GUEST_MODE','true').lower() == 'true',
            guest_ttl_seconds=int(os.getenv('GUEST_TTL_SECONDS','86400')),
            guest_concurrent_jobs=int(os.getenv('GUEST_CONCURRENT_JOBS','2')),
            guest_creates_per_minute=int(os.getenv('GUEST_CREATES_PER_MINUTE','20')),
            guest_gpu_budget=int(os.getenv('GUEST_GPU_BUDGET','0')),
            session_days=int(os.getenv('SESSION_DAYS', '7')),
            ai_mvp_enabled=os.getenv('AI_MVP_ENABLED','false').lower() == 'true',
            local_catalog=os.getenv('TP_ENVIRONMENT') in ('local_project','isolated_test'),
        )
