from sqlalchemy import MetaData, Column, String, DateTime, Boolean, Table

meta = MetaData()

users_table = Table(
    'users',
    meta,
    Column('id', String(255), primary_key=True),
    Column('password', String(255)),
    Column('nickname', String(255)),
    Column('birth', DateTime),
    Column('username', String(255)),
    Column('phone', String(11)),
    Column('email', String(255)),
    Column('sex', Boolean),
    Column('address', String(255))
)
