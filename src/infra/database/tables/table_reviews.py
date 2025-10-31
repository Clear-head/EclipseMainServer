from sqlalchemy import MetaData, Column, String, Table, ForeignKey, Integer

meta = MetaData()

reviews_table = Table(
    'reviews',
    meta,
    Column('id', String(255), primary_key=True),
    Column('user_id', String(255), ForeignKey('users.id'), nullable=False),
    Column('category_id', String(255), ForeignKey('category.id'), nullable=False),
    Column('stars', Integer),
    Column('comments', String(300))
)