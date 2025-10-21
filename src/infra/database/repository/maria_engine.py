import asyncio
import urllib
from json import load
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import URL
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
                f'mysql+asyncmy://{config["user"]}:{config["password"]}@{config["host"]}:{config["port"]}/{config["database"]}'
            )

            # password = urllib.parse.quote_plus(config['password'])

            # _ENGINE = create_async_engine(
            #     f"mysql+aiomysql://{config['user']}:{password}"
            #     f"@{config['host']}:{config['port']}/{config['database']}",
            #     pool_size=config.get('pool_size', 5),
            #     pool_pre_ping=config.get('pool_pre_ping', True),
            #     max_overflow=config.get('max_overflow', 10)
            # )

            # url_object = URL.create(
            #     "mysql+aiomysql",
            #     username=config["user"],
            #     password=config["password"],
            #     host=config["host"],
            #     port=config["port"],
            #     database=config["database"],
            # )
            #
            # _ENGINE = create_async_engine(url_object)

        return _ENGINE

    except Exception as e:
        print(e)
        raise Exception(e)