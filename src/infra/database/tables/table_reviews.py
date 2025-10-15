from sqlalchemy import MetaData, Column, String, DateTime, Boolean, Table, Index, ForeignKey, Integer, Text

meta = MetaData()

reviews_table = Table(
    'reviews',
    meta,
    Column('id', String(255), primary_key=True),
    Column('user_id', String(255), ForeignKey('users.id')),
    Column('category_id', String(255), ForeignKey('category.id')),
    Column('stars', Integer),
    Column('tag', Text)
)