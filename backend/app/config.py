import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    starting_cash: float = float(os.getenv('STARTING_CASH', '50000'))
    max_risk_per_trade: float = float(os.getenv('MAX_RISK_PER_TRADE', '250'))
    daily_loss_limit: float = float(os.getenv('DAILY_LOSS_LIMIT', '1000'))
    max_open_positions: int = int(os.getenv('MAX_OPEN_POSITIONS', '3'))
    database_path: str = os.getenv('DATABASE_PATH', './paper_trader.db')

settings = Settings()
