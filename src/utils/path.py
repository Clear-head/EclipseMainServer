from pathlib import Path

project_dir = Path(__file__).resolve().parent.parent

path_dic = {
    "database_config": project_dir.joinpath( "resources").joinpath("config").joinpath("database_config.json"),
    "log_config": project_dir.joinpath( "resources").joinpath("config").joinpath("log_config.json"),
    "env": project_dir.joinpath( "resources").joinpath("config").joinpath(".env")
}