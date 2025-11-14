from sqlalchemy import MetaData, Column, String, Table, DateTime, Integer, ForeignKey, Text

meta = MetaData()

black_table = Table(
    'black',
    meta,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('user_id', String, ForeignKey("users.id")),
    Column('phone', String),
    Column('email', String),
    Column('Sanction', Text),
    Column('period', DateTime),
    Column('started_at', DateTime),
)