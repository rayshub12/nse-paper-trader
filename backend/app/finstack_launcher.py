"""Launch FinStack MCP with short cache TTLs for intraday paper trading."""
from finstack.utils.cache import TTLCache, quotes_cache, historical_cache

_original_set = TTLCache.set

def _set_with_intraday_ttl(self, key, value, ttl=None):
    # Clamp even upstream decorators that explicitly request 5m/24h caching.
    if self is quotes_cache or self is historical_cache:
        ttl = 60
    return _original_set(self, key, value, ttl)

TTLCache.set = _set_with_intraday_ttl

from finstack.server import main  # noqa: E402

if __name__ == "__main__":
    main()
