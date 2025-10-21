from pydantic import BaseModel, ConfigDict


class BaseEntity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    def keys(self):
        for i in self.__dict__:
            if not i.startswith("_"):
                yield i

        if self.__pydantic_extra__:
            yield from self.__pydantic_extra__.keys()


    @classmethod
    def from_dto(cls, dto):
        pass