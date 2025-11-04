from sqlalchemy import MetaData, Column, String, Table, ForeignKey, DateTime, Text

meta = MetaData()

merge_history_table = Table(
    'merge_history',
    meta,
    Column('id', String(255), primary_key=True),
    Column('user_id', String(255), ForeignKey('users.id'), nullable=False),
    Column("template_type", Text, nullable=True),
    Column('categories_name', Text, nullable=False),
    Column('visited_at', DateTime),
)