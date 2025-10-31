from sqlalchemy import MetaData, Column, String, Text, Table, DateTime

meta = MetaData()

category_table = Table(
    'category',
    meta,
    Column("id",String(255), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("do", String(63)),
    Column("si", String(63)),
    Column("gu", String(63)),
    Column("detail_address", String(255)),
    Column("sub_category", String(63)),
    Column("business_hour", String(255)),
    Column("phone", String(12)),
    Column("type", String(1), nullable=False),
    Column("image", Text),
    Column("latitude", String(63), nullable=False),
    Column("longitude", String(63), nullable=False),
    Column("menu", Text),
    Column("last_crawl", DateTime, nullable=False),
)