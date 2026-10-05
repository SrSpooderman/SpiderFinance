"""Copy ORM columns into plain data for application read models."""


def snapshot(item) -> dict:
    return {column.key: getattr(item, column.key) for column in item.__mapper__.columns}
