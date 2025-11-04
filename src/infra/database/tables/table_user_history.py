from sqlalchemy import MetaData, Column, String, DateTime, Table, ForeignKey, Text, Integer

meta = MetaData()

user_history_table = Table(
    'user_history',
    meta,
    Column('id', String, primary_key=True),
    Column('order', String(1), primary_key=True),
    Column('visited_at', DateTime, nullable=False),
    Column('user_id', String(255), ForeignKey('users.id'), nullable=False),
    Column('category_id', String(255), ForeignKey('category.id')),
    Column("category_name", String(255), ForeignKey('category.name')),
    Column("duration", Integer),
    Column("transportation", String(1))
)

# Table "user_history" {
#   "id" VARCHAR(255) [pk]
#   "order" char(1)
#   "visited_at" datetime
#   "user_id" VARCHAR(255)
#   "category_id" varchar(255)
#   "category_name" varchar(255)
#   "duration" int
#   "transportation" char(1)
# }