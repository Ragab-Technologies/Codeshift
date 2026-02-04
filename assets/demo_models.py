from pydantic import BaseModel, validator


class User(BaseModel):
    name: str
    email: str

    class Config:
        orm_mode = True

    @validator("email")
    def validate_email(cls, v):
        return v.lower()


user = User(name="John", email="JOHN@EXAMPLE.COM")
data = user.dict()
