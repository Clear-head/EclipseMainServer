from sqlalchemy import MetaData, Column, Table, Integer, String

meta = MetaData()

delete_cause_table = Table(
    'delete_cause',
    meta,
    Column('cause', String(511), primary_key=True),
    Column('count', Integer),
)