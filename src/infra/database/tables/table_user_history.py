from sqlalchemy import MetaData, Column, String, DateTime, Table, ForeignKey, Integer, Text

meta = MetaData()

user_history_table = Table(
    'user_history',
    meta,
    Column('id', String, primary_key=True),
    Column('merge_id', Integer, ForeignKey('merge_history.id')),
    Column('seq', Integer),
    Column('visited_at', DateTime, nullable=False),
    Column('user_id', String(255), ForeignKey('users.id'), nullable=False),
    Column('category_id', String(255), ForeignKey('category.id')),
    Column("category_name", String(255), ForeignKey('category.name')),
    Column("duration", Integer),
    Column("transportation", String(1)),
    Column("description", Text)
)