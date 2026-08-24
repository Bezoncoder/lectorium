from pydantic import BaseModel, ConfigDict


class BasePydantic(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )