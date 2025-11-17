from sqlalchemy import MetaData, Column, String, Table, DateTime, Integer, ForeignKey, Text, Boolean

meta = MetaData()

report_table = Table(
    'report',
    meta,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('reporter', String, ForeignKey("users.id")),
    Column('user_id', String, ForeignKey("users.id")),
    Column('type', Integer, nullable=False),
    Column('cause_id', String, nullable=False),
    Column('cause', Text),
    Column('reported_at', DateTime),
    Column('is_processed', Boolean, default=False, server_default='0', nullable=False),
)
