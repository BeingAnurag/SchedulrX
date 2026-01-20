import json
import hashlib
from typing import Dict, List, Optional

import redis

from app.config.settings import get_settings

settings = get_settings()


class ScheduleCache:
    def __init__(self, redis_url: str = settings.redis_url):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    def get(self, constraint_hash: str) -> Optional[Dict]:
        """Retrieve cached schedule by constraint hash."""
        cached = self.redis_client.get(f"schedule:{constraint_hash}")
        if cached:
            return json.loads(cached)
        return None

    def set(self, constraint_hash: str, schedule: Dict, ttl_seconds: int = 3600) -> None:
        """Cache schedule with TTL (default 1 hour)."""
        self.redis_client.setex(
            f"schedule:{constraint_hash}",
            ttl_seconds,
            json.dumps(schedule, default=str)
        )

    def delete(self, constraint_hash: str) -> None:
        """Invalidate cache entry."""
        self.redis_client.delete(f"schedule:{constraint_hash}")

    @staticmethod
    def hash_constraints(tasks: List[Dict], resources: List[Dict]) -> str:
        """Generate hash from task/resource constraints."""
        data = json.dumps({"tasks": tasks, "resources": resources}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def health_check(self) -> bool:
        """Check Redis connection."""
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
