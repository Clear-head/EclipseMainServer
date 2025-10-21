from sqlalchemy import MetaData, Column, String, DateTime, Boolean, Table

meta = MetaData()

users_table = Table(
    'users',
    meta,
    Column('id', String(255), primary_key=True),
    Column('password', String(255), nullable=False),
    Column('username', String(255), nullable=False),
    Column('nickname', String(255), nullable=False),
    Column('birth', DateTime),
    Column('phone', String(12)),
    Column('email', String(255), nullable=False),
    Column('sex', Boolean),
    Column('address', String(255))
)
