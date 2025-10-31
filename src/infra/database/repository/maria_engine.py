
from json import load
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

_ENGINE = None


async def get_engine() -> AsyncEngine:
    global _ENGINE

    if _ENGINE is not None:
        return _ENGINE

    try:

        config_path = Path(__file__).parent.parent.parent.parent.joinpath('resources').joinpath('config').joinpath('database_config.json')

        with open(config_path) as f:
            config = load(f)["maria"]

            _ENGINE = create_async_engine(
                f'mysql+asyncmy://{config["user"]}:{config["password"]}'
                f'@{config["host"]}:{config["port"]}/{config["database"]}'
            )

        return _ENGINE

    except Exception as e:
        print(e)
        raise Exception("engine error: ") from e