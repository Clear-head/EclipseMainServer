from sqlalchemy import MetaData, Column, String, DateTime, Boolean, Table

meta = MetaData()

users_table = Table(
    'users',
    meta,
    Column('id', String(255), primary_key=True),
    Column('password', String(255), notnull=True),
    Column('username', String(255), notnull=True),
    Column('nickname', String(255), notnull=True),
    Column('birth', DateTime),
    Column('phone', String(12)),
    Column('email', String(255), notnull=True),
    Column('sex', Boolean),
    Column('address', String(255))
)
