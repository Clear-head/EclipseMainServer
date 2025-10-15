from sqlalchemy import MetaData, Column, String, DateTime, Boolean, Table, Index, ForeignKey

meta = MetaData()

user_like_table = Table(
    'user_like_table',
    meta,
    Column('user_id', String(255), ForeignKey('users.id')),
    Column('category_id', String(255), ForeignKey('category.id'))
)