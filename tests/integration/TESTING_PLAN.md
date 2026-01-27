# Codeshift Integration Testing Plan

## Overview

This plan outlines comprehensive end-to-end integration tests for the Codeshift tool. Each test creates a realistic Python project with known breaking changes, runs the full codeshift workflow (scan → upgrade → apply), and validates the results.

## Test Strategy

### Goals
1. Validate the complete workflow works end-to-end
2. Ensure transformations produce syntactically valid Python code
3. Verify all expected breaking changes are detected and fixed
4. Test edge cases and complex scenarios
5. Validate that migrated code maintains semantic correctness

### Test Structure
Each test follows this pattern:
1. **Setup**: Create a temporary Python project with specific breaking changes
2. **Scan**: Run `codeshift scan` to detect dependencies
3. **Upgrade**: Run `codeshift upgrade <library> --target <version>`
4. **Diff**: Run `codeshift diff` to preview changes
5. **Apply**: Run `codeshift apply` to write changes
6. **Validate**: Check syntax, verify transformations, optionally run tests

---

## Test Cases

### Test 1: Pydantic v1 → v2 Basic Model Methods
**Target**: Core method renames (.dict(), .json(), .parse_obj(), .copy())

```python
# Input: pydantic_basic.py
from pydantic import BaseModel

class User(BaseModel):
    name: str
    age: int

user = User(name="John", age=30)
data = user.dict()
json_str = user.json()
user_copy = user.copy()
restored = User.parse_obj({"name": "Jane", "age": 25})
```

**Expected transformations:**
- `.dict()` → `.model_dump()`
- `.json()` → `.model_dump_json()`
- `.copy()` → `.model_copy()`
- `.parse_obj()` → `.model_validate()`

---

### Test 2: Pydantic v1 → v2 Validators
**Target**: Validator decorators (@validator, @root_validator)

```python
# Input: pydantic_validators.py
from pydantic import BaseModel, validator, root_validator

class User(BaseModel):
    name: str
    email: str

    @validator("name")
    def validate_name(cls, v):
        if len(v) < 2:
            raise ValueError("Name too short")
        return v

    @root_validator
    def validate_all(cls, values):
        return values
```

**Expected transformations:**
- `@validator` → `@field_validator` with `@classmethod`
- `@root_validator` → `@model_validator`
- Add `from pydantic import field_validator, model_validator`

---

### Test 3: Pydantic v1 → v2 Config Class
**Target**: Inner Config class migration

```python
# Input: pydantic_config.py
from pydantic import BaseModel

class User(BaseModel):
    name: str

    class Config:
        orm_mode = True
        allow_mutation = False
        use_enum_values = True
```

**Expected transformations:**
- Config class → `model_config = ConfigDict(...)`
- `orm_mode` → `from_attributes`
- `allow_mutation=False` → `frozen=True`
- Add `from pydantic import ConfigDict`

---

### Test 4: SQLAlchemy 1.4 → 2.0 Query API
**Target**: Session.query() → select() migration

```python
# Input: sqlalchemy_queries.py
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import Session, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

session = Session()
users = session.query(User).all()
user = session.query(User).filter(User.id == 1).first()
count = session.query(User).count()
```

**Expected transformations:**
- `session.query(User).all()` → `session.execute(select(User)).scalars().all()`
- `session.query(User).filter(...).first()` → `session.execute(select(User).where(...)).scalars().first()`
- `declarative_base()` → `DeclarativeBase` class
- Add `from sqlalchemy import select`

---

### Test 5: SQLAlchemy 1.4 → 2.0 Engine & Imports
**Target**: Engine execution and import changes

```python
# Input: sqlalchemy_engine.py
from sqlalchemy import create_engine

engine = create_engine("sqlite:///test.db", future=True)
result = engine.execute("SELECT 1")

with engine.connect() as conn:
    conn.execute("SELECT * FROM users")
```

**Expected transformations:**
- `future=True` removed from create_engine
- Raw SQL → `text()` wrapper
- `engine.execute()` → `with engine.connect() as conn: conn.execute()`

---

### Test 6: FastAPI Starlette Import Migration
**Target**: Starlette imports → FastAPI imports

```python
# Input: fastapi_imports.py
from starlette.responses import JSONResponse, HTMLResponse
from starlette.requests import Request
from starlette.websockets import WebSocket
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root(request: Request):
    return JSONResponse({"status": "ok"}, status_code=HTTP_200_OK)
```

**Expected transformations:**
- `from starlette.responses` → `from fastapi.responses`
- `from starlette.requests` → `from fastapi`
- `from starlette.websockets` → `from fastapi`

**Note:** `from starlette.status` imports are intentionally NOT transformed. FastAPI does not re-export status constants (HTTP_200_OK, HTTP_404_NOT_FOUND, etc.) directly. These imports should remain as `from starlette.status import ...` since FastAPI depends on Starlette and these imports work correctly.

---

### Test 7: FastAPI Parameter Regex Migration
**Target**: regex → pattern parameter rename

```python
# Input: fastapi_params.py
from fastapi import FastAPI, Query, Path, Body

app = FastAPI(openapi_prefix="/api")

@app.get("/users/{user_id}")
def get_user(
    user_id: str = Path(..., regex=r"^[a-z]+$"),
    filter: str = Query(None, regex=r"^[A-Z]+$"),
):
    return {"user_id": user_id}
```

**Expected transformations:**
- `regex=` → `pattern=` in Query, Path, Body
- `openapi_prefix=` → `root_path=`

---

### Test 8: Pandas 1.5 → 2.0 Deprecations
**Target**: append(), iteritems(), and other removals

```python
# Input: pandas_deprecated.py
import pandas as pd

df1 = pd.DataFrame({"a": [1, 2]})
df2 = pd.DataFrame({"a": [3, 4]})
combined = df1.append(df2)

s1 = pd.Series([1, 2, 3])
s2 = pd.Series([4, 5, 6])
combined_series = s1.append(s2)

for key, value in df1.iteritems():
    print(key, value)

index = df1.index
is_mono = index.is_monotonic
```

**Expected transformations:**
- `df.append(other)` → `pd.concat([df, other])`
- `series.append(other)` → `pd.concat([series, other])`
- `.iteritems()` → `.items()`
- `.is_monotonic` → `.is_monotonic_increasing`

---

### Test 9: Requests Library Urllib3 Migration
**Target**: requests.packages.urllib3 import fixes

```python
# Input: requests_urllib3.py
from requests.packages import urllib3
from requests.packages.urllib3.util.retry import Retry
import requests

urllib3.disable_warnings()

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.1)
adapter = urllib3.HTTPAdapter(max_retries=retry)
```

**Expected transformations:**
- `from requests.packages import urllib3` → `import urllib3`
- `from requests.packages.urllib3.util.retry` → `from urllib3.util.retry`

---

### Test 10: Multi-Library Complex Project
**Target**: Real-world project with multiple libraries

```python
# Input: complex_project/
# - models.py (Pydantic v1)
# - database.py (SQLAlchemy 1.4)
# - api.py (FastAPI with Starlette imports)
# - data_processing.py (Pandas 1.5)
# - http_client.py (Requests with urllib3)
```

This test creates a realistic project structure with:
- Multiple files across different libraries
- Cross-file dependencies
- Mixed usage patterns
- Edge cases in each library

---

## Validation Criteria

### Syntax Validation
- All output files must be valid Python (parseable by ast.parse())
- No syntax errors introduced by transformations

### Transform Validation
- Expected method/function renames applied
- Correct imports added/modified
- No unrelated code changed
- Comments and formatting preserved

### Semantic Validation (where possible)
- Import statements resolve correctly
- Method calls match new signatures
- Type hints remain valid

---

## Test Execution

Each test will be run by a subagent that:
1. Creates the test project in a temp directory
2. Runs the codeshift workflow
3. Validates results
4. Reports success/failure with details

Results will be aggregated into a final report.
