from sqlalchemy import MetaData, Column, String, DateTime, Boolean, Table, Index, ForeignKey

meta = MetaData()

user_like_table = Table(
    'user_like',
    meta,
    Column('user_id', String(255), ForeignKey('users.id'), notnull=True),
    Column('category_id', String(255), ForeignKey('category.id'), notnull=True)
)