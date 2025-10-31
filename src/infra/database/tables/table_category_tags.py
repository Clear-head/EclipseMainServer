from sqlalchemy import MetaData, Column, String, Table, ForeignKey, Integer

meta = MetaData()

category_tags_table = Table(
    'category_tags',
    meta,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), nullable=False),
    Column('category_id', String(255), ForeignKey('category.id'), nullable=False),
    Column('count', Integer),
)