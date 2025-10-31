from sqlalchemy import MetaData, Column, String, Table, Integer

meta = MetaData()

tags_table = Table(
    'tags',
    meta,
    Column('id', Integer, primary_key=True),
    Column('name', String(255)),
)