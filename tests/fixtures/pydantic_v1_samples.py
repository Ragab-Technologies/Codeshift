"""Sample Pydantic v1 code for testing transforms."""

# Sample 1: Basic model with Config class
BASIC_MODEL_WITH_CONFIG = '''
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

    class Config:
        orm_mode = True
'''

BASIC_MODEL_WITH_CONFIG_EXPECTED = '''
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    age: int
'''

# Sample 2: Model with validator
MODEL_WITH_VALIDATOR = '''
from pydantic import BaseModel, validator

class User(BaseModel):
    name: str

    @validator("name")
    def validate_name(cls, v):
        return v.strip()
'''

MODEL_WITH_VALIDATOR_EXPECTED = '''
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return v.strip()
'''

# Sample 3: Model with root_validator
MODEL_WITH_ROOT_VALIDATOR = '''
from pydantic import BaseModel, root_validator

class User(BaseModel):
    name: str
    email: str

    @root_validator
    def validate_model(cls, values):
        return values
'''

MODEL_WITH_ROOT_VALIDATOR_EXPECTED = '''
from pydantic import BaseModel, model_validator

class User(BaseModel):
    name: str
    email: str

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, values):
        return values
'''

# Sample 4: Method calls
METHOD_CALLS = '''
from pydantic import BaseModel

class User(BaseModel):
    name: str

user = User(name="test")
data = user.dict()
json_str = user.json()
schema = User.schema()
parsed = User.parse_obj({"name": "test"})
'''

METHOD_CALLS_EXPECTED = '''
from pydantic import BaseModel

class User(BaseModel):
    name: str

user = User(name="test")
data = user.model_dump()
json_str = user.model_dump_json()
schema = User.model_json_schema()
parsed = User.model_validate({"name": "test"})
'''

# Sample 5: Field with regex
FIELD_WITH_REGEX = '''
from pydantic import BaseModel, Field

class User(BaseModel):
    email: str = Field(..., regex=r"^[\\w.-]+@[\\w.-]+\\.\\w+$")
'''

FIELD_WITH_REGEX_EXPECTED = '''
from pydantic import BaseModel, Field

class User(BaseModel):
    email: str = Field(..., pattern=r"^[\\w.-]+@[\\w.-]+\\.\\w+$")
'''

# Sample 6: Config with multiple options
CONFIG_MULTIPLE_OPTIONS = '''
from pydantic import BaseModel

class User(BaseModel):
    name: str

    class Config:
        orm_mode = True
        validate_assignment = True
        extra = "forbid"
        allow_mutation = False
'''

CONFIG_MULTIPLE_OPTIONS_EXPECTED = '''
from pydantic import BaseModel, ConfigDict

class User(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        extra="forbid",
        frozen=True,
    )

    name: str
'''

# Sample 7: Multiple validators
MULTIPLE_VALIDATORS = '''
from pydantic import BaseModel, validator

class User(BaseModel):
    name: str
    age: int
    email: str

    @validator("name")
    def validate_name(cls, v):
        return v.strip()

    @validator("age")
    def validate_age(cls, v):
        if v < 0:
            raise ValueError("Age must be positive")
        return v

    @validator("email")
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.lower()
'''

MULTIPLE_VALIDATORS_EXPECTED = '''
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str
    age: int
    email: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return v.strip()

    @field_validator("age")
    @classmethod
    def validate_age(cls, v):
        if v < 0:
            raise ValueError("Age must be positive")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.lower()
'''
