from sqlalchemy import MetaData, Column, String, Table, ForeignKey, Integer, Text

meta = MetaData()

reviews_table = Table(
    'reviews',
    meta,
    Column('id', String(255), primary_key=True),
    Column('user_id', String(255), ForeignKey('users.id'), notnull=True),
    Column('category_id', String(255), ForeignKey('category.id'), notnull=True),
    Column('stars', Integer),
)