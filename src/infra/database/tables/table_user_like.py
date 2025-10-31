from sqlalchemy import MetaData, Column, String, Table, ForeignKey

meta = MetaData()

user_like_table = Table(
    'user_like',
    meta,
    Column('user_id', String(255), ForeignKey('users.id'), nullable=False),
    Column('category_id', String(255), ForeignKey('category.id'), nullable=False)
)