from sqlalchemy import MetaData, Column, String, DateTime, Boolean, Table, Index, ForeignKey

meta = MetaData()

user_history_table = Table(
    'user_history_table',
    meta,
    Column('user_id', String(255), ForeignKey('users.id'), notnull=True),
    Column('visited_at', DateTime, notnull=True),
    Column('category_id', String(255), ForeignKey('category.id'), notnull=True)
)