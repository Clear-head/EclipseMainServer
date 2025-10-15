from sqlalchemy import MetaData, Column, String, Text, Table, ForeignKey, Index

meta = MetaData()

category_table = Table(
    'category',
    meta,
    Column('id', String, ForeignKey('original_data.id')),
    Column('tags', Text),
    Index('tags_idx', 'tags')
)