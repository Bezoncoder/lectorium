from typing import Annotated

from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass


uniq_str_an = Annotated[
    str,
    mapped_column(
        unique=True,
        nullable=False,
    ),
]