"""Launch FinStack MCP with short cache TTLs for intraday paper trading."""
from finstack.utils.cache import quotes_cache, historical_cache

# Upstream historical cache defaults to 24 hours; that is too long for intraday use.
quotes_cache._default_ttl = 60
historical_cache._default_ttl = 60

from finstack.server import main  # noqa: E402

if __name__ == "__main__":
    main()
