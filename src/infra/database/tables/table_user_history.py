from sqlalchemy import MetaData, Column, String, DateTime, Table, ForeignKey, Text

meta = MetaData()

user_history_table = Table(
    'user_history',
    meta,
    Column('id', String, primary_key=True),
    Column('user_id', String(255), ForeignKey('users.id'), nullable=False),
    Column('visited_at', DateTime, nullable=False),
    Column('cafe', String(255), ForeignKey('category.id'), nullable=True),
    Column('restaurant', String(255), ForeignKey('category.id'), nullable=True),
    Column('category_id', String(255), ForeignKey('category.id'), nullable=True),
    Column("template", Text, nullable=True)
)