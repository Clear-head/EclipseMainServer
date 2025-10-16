from sqlalchemy import MetaData, Column, String, DateTime, Boolean, Table, Index, ForeignKey

meta = MetaData()

user_history_table = Table(
    'user_history_table',
    meta,
    Column('user_id', String(10), ForeignKey('users.id')),
    Column('visited_at', DateTime),
    Column('category_id', ForeignKey('category.id'))
)