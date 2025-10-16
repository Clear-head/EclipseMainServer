from sqlalchemy import MetaData, Column, String, DateTime, Text, Index, Table

meta = MetaData()

original_data_table = Table(
    'original_data',
    meta,
    Column('id', String(255), primary_key=True),
    Column('name', String(255)),
    Column('address', String(255)),
    Column('phone', String(12)),
    Column('type', String(1)),
    Column('image', String(255)),
    Column('longitude', String(10)),
    Column('latitude', String(10)),
    Column('business_hour', String(255)),
    Column('original_data', Text),
    Column('last_crawl', DateTime),

    Index('type_idx', 'type'),
    Index('location_idx', 'longitude', 'latitude')
)
