from json import load
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

_ENGINE = None


async def get_engine() -> AsyncEngine:
    global _ENGINE

    if _ENGINE is not None:
        return _ENGINE

    try:

        config_path = Path(__file__).parent.parent / 'resources' / 'config' / 'database_config.json'

        with open(config_path) as f:
            config = load(f)

        _ENGINE = create_async_engine(
            f"mysql+aiomysql://{config['user']}:{config['password']}"
            f"@{config['host']}:{config['port']}/{config['database']}",
            pool_size=config.get('pool_size', 5),
            pool_pre_ping=config.get('pool_pre_ping', True),
            max_overflow=config.get('max_overflow', 10)
        )

        return _ENGINE

    except Exception as e:
        raise e