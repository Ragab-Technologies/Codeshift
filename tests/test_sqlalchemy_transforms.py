"""Tests for SQLAlchemy transformation."""

from codeshift.migrator.transforms.sqlalchemy_transformer import (
    transform_sqlalchemy,
)


class TestImportTransforms:
    """Tests for SQLAlchemy import transformations."""

    def test_declarative_base_import_transform(self):
        """Test declarative_base import transform to DeclarativeBase."""
        code = """from sqlalchemy.ext.declarative import declarative_base"""
        result, changes = transform_sqlalchemy(code)
        assert "from sqlalchemy.orm import DeclarativeBase" in result
        assert "declarative_base" not in result
        assert any(c.transform_name == "import_declarative_base" for c in changes)

    def test_backref_import_removed(self):
        """Test backref import is removed with warning."""
        code = """from sqlalchemy.orm import relationship, backref"""
        result, changes = transform_sqlalchemy(code)
        assert "backref" not in result
        assert "relationship" in result
        assert any(c.transform_name == "remove_backref_import" for c in changes)

    def test_backref_only_import_removed(self):
        """Test that import is removed when backref is the only import."""
        code = """from sqlalchemy.orm import backref"""
        result, changes = transform_sqlalchemy(code)
        assert "backref" not in result or result.strip() == ""
        assert any(c.transform_name == "remove_backref_import" for c in changes)

    def test_non_sqlalchemy_import_unchanged(self):
        """Test that non-SQLAlchemy imports are unchanged."""
        code = """from datetime import datetime"""
        result, changes = transform_sqlalchemy(code)
        assert result == code
        assert len(changes) == 0


class TestDeclarativeBaseTransforms:
    """Tests for declarative_base() call transforms."""

    def test_declarative_base_call_transformed_to_class(self):
        """Test declarative_base() call is transformed to class definition."""
        code = """Base = declarative_base()"""
        result, changes = transform_sqlalchemy(code)
        assert "class Base(DeclarativeBase):" in result
        assert "pass" in result
        assert "declarative_base()" not in result
        assert any(c.transform_name == "declarative_base_to_class" for c in changes)

    def test_declarative_base_from_orm(self):
        """Test declarative_base from sqlalchemy.orm is transformed."""
        code = """from sqlalchemy.orm import declarative_base, Session

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
"""
        result, changes = transform_sqlalchemy(code)
        # Check import is transformed
        assert "from sqlalchemy.orm import DeclarativeBase, Session" in result
        assert "declarative_base" not in result
        # Check class is created
        assert "class Base(DeclarativeBase):" in result
        assert "pass" in result
        # Check User class is preserved
        assert "class User(Base):" in result
        assert '__tablename__ = "users"' in result
        # Check changes recorded
        assert any(c.transform_name == "import_declarative_base" for c in changes)
        assert any(c.transform_name == "declarative_base_to_class" for c in changes)

    def test_declarative_base_from_ext_declarative(self):
        """Test declarative_base from sqlalchemy.ext.declarative is also transformed."""
        code = """from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
"""
        result, changes = transform_sqlalchemy(code)
        assert "from sqlalchemy.orm import DeclarativeBase" in result
        assert "class Base(DeclarativeBase):" in result
        assert "pass" in result
        assert "declarative_base" not in result
        assert any(c.transform_name == "import_declarative_base" for c in changes)
        assert any(c.transform_name == "declarative_base_to_class" for c in changes)

    def test_declarative_base_with_custom_name(self):
        """Test declarative_base() with custom variable name."""
        code = """from sqlalchemy.orm import declarative_base

MyBase = declarative_base()
"""
        result, changes = transform_sqlalchemy(code)
        assert "class MyBase(DeclarativeBase):" in result
        assert "pass" in result
        assert "declarative_base()" not in result

    def test_declarative_base_preserves_other_orm_imports(self):
        """Test that other sqlalchemy.orm imports are preserved."""
        code = """from sqlalchemy.orm import declarative_base, relationship, Session

Base = declarative_base()
"""
        result, changes = transform_sqlalchemy(code)
        assert "DeclarativeBase" in result
        assert "relationship" in result
        assert "Session" in result
        assert "class Base(DeclarativeBase):" in result


class TestCreateEngineTransforms:
    """Tests for create_engine parameter transforms."""

    def test_create_engine_future_flag_removed(self):
        """Test future=True is removed from create_engine."""
        code = """engine = create_engine("sqlite:///db.sqlite", future=True)"""
        result, changes = transform_sqlalchemy(code)
        assert "future=" not in result
        assert any(c.transform_name == "remove_future_flag" for c in changes)

    def test_create_engine_without_future_unchanged(self):
        """Test create_engine without future flag is unchanged."""
        code = """engine = create_engine("sqlite:///db.sqlite", echo=True)"""
        result, changes = transform_sqlalchemy(code)
        assert "echo=True" in result
        assert not any(c.transform_name == "remove_future_flag" for c in changes)


class TestSyntaxErrorHandling:
    """Tests for syntax error handling."""

    def test_syntax_error_returns_original(self):
        """Test that syntax errors return original code."""
        code = """from sqlalchemy import"""
        result, changes = transform_sqlalchemy(code)
        assert result == code
        assert len(changes) == 0


class TestExecuteTextWrapper:
    """Tests for wrapping raw SQL strings with text()."""

    def test_execute_string_wrapped_with_text(self):
        """Test raw SQL string in execute() is wrapped with text()."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db")
with engine.connect() as conn:
    conn.execute("SELECT * FROM users")
"""
        result, changes = transform_sqlalchemy(code)
        assert 'conn.execute(text("SELECT * FROM users"))' in result
        assert any(c.transform_name == "wrap_execute_with_text" for c in changes)

    def test_execute_text_import_added(self):
        """Test that text import is added when execute() string is wrapped."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db")
with engine.connect() as conn:
    conn.execute("SELECT * FROM users")
"""
        result, changes = transform_sqlalchemy(code)
        assert "from sqlalchemy import create_engine, text" in result

    def test_execute_with_existing_text_import(self):
        """Test that text import is not duplicated if already present."""
        code = """from sqlalchemy import create_engine, text
engine = create_engine("sqlite:///test.db")
with engine.connect() as conn:
    conn.execute("SELECT * FROM users")
"""
        result, changes = transform_sqlalchemy(code)
        # Should only have one text in the import (not duplicated)
        # Count occurrences: 1 in import, 1 in text() call = 2 total
        assert result.count("text") == 2
        assert 'conn.execute(text("SELECT * FROM users"))' in result
        # Verify no duplicate import
        assert result.count("from sqlalchemy import") == 1

    def test_execute_insert_string_wrapped(self):
        """Test INSERT statement is wrapped with text()."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db")
with engine.connect() as conn:
    conn.execute("INSERT INTO users (name) VALUES ('test')")
"""
        result, changes = transform_sqlalchemy(code)
        assert "conn.execute(text(" in result
        assert "INSERT INTO users" in result

    def test_execute_with_non_string_unchanged(self):
        """Test execute() with non-string argument is unchanged."""
        code = """from sqlalchemy import create_engine, text
engine = create_engine("sqlite:///test.db")
stmt = text("SELECT * FROM users")
with engine.connect() as conn:
    conn.execute(stmt)
"""
        result, changes = transform_sqlalchemy(code)
        # Should not wrap stmt variable
        assert "conn.execute(stmt)" in result
        # No text wrapping change should be recorded for the variable call
        execute_wraps = [c for c in changes if c.transform_name == "wrap_execute_with_text"]
        assert len(execute_wraps) == 0


class TestTrailingCommaFix:
    """Tests for fixing trailing comma when removing future=True."""

    def test_create_engine_no_trailing_comma(self):
        """Test no trailing comma after removing future=True."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db", future=True)
"""
        result, changes = transform_sqlalchemy(code)
        assert 'create_engine("sqlite:///test.db")' in result
        assert ", )" not in result

    def test_create_engine_with_other_args_preserved(self):
        """Test other arguments are preserved when future=True is removed."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db", echo=True, future=True)
"""
        result, changes = transform_sqlalchemy(code)
        assert "echo=True" in result
        assert "future=" not in result
        assert ", )" not in result

    def test_create_engine_future_first_other_args_preserved(self):
        """Test when future=True is not the last argument."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db", future=True, echo=True)
"""
        result, changes = transform_sqlalchemy(code)
        assert "echo=True" in result
        assert "future=" not in result

    def test_create_engine_url_only_after_future_removal(self):
        """Test create_engine with only URL after future removal."""
        code = """from sqlalchemy import create_engine
engine = create_engine("postgresql://user:pass@localhost/db", future=True)
"""
        result, changes = transform_sqlalchemy(code)
        assert 'create_engine("postgresql://user:pass@localhost/db")' in result
        assert ", )" not in result
        assert "future" not in result


class TestComplexTransforms:
    """Tests for complex multi-transform scenarios."""

    def test_multiple_transforms_in_one_file(self):
        """Test multiple transforms applied to one file."""
        code = """from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine

engine = create_engine("sqlite:///test.db", future=True)
Base = declarative_base()
"""
        result, changes = transform_sqlalchemy(code)
        assert "DeclarativeBase" in result
        assert "future=" not in result
        assert len(changes) >= 3

    def test_combined_future_removal_and_text_wrapper(self):
        """Test future=True removal and text() wrapping together."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db", future=True)
with engine.connect() as conn:
    conn.execute("SELECT * FROM users")
"""
        result, changes = transform_sqlalchemy(code)
        assert "future=" not in result
        assert 'conn.execute(text("SELECT * FROM users"))' in result
        assert "from sqlalchemy import create_engine, text" in result
        assert ", )" not in result


class TestQueryAllTransforms:
    """Tests for session.query().all() transformations."""

    def test_query_all_to_select(self):
        """Test session.query(Model).all() transforms to session.execute(select(Model)).scalars().all()."""
        code = """from sqlalchemy import Column, Integer
users = session.query(User).all()
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.execute(select(User)).scalars().all()" in result
        assert "session.query(User).all()" not in result
        assert any(c.transform_name == "query_all_to_select" for c in changes)

    def test_query_all_adds_select_import(self):
        """Test that select import is added when query transforms are applied."""
        code = """from sqlalchemy import Column, Integer
users = session.query(User).all()
"""
        result, changes = transform_sqlalchemy(code)
        assert "select" in result
        # select should be added to the existing import
        assert "from sqlalchemy import Column, Integer, select" in result

    def test_query_all_no_existing_sqlalchemy_import(self):
        """Test that select import is added at top when no sqlalchemy import exists."""
        code = """users = session.query(User).all()
"""
        result, changes = transform_sqlalchemy(code)
        assert "from sqlalchemy import select" in result
        assert "session.execute(select(User)).scalars().all()" in result


class TestQueryFirstTransforms:
    """Tests for session.query().first() transformations."""

    def test_query_first_to_select(self):
        """Test session.query(Model).first() transforms correctly."""
        code = """from sqlalchemy import Column
user = session.query(User).first()
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.execute(select(User)).scalars().first()" in result
        assert "session.query(User).first()" not in result
        assert any(c.transform_name == "query_first_to_select" for c in changes)


class TestQueryOneTransforms:
    """Tests for session.query().one() transformations."""

    def test_query_one_to_select(self):
        """Test session.query(Model).one() transforms correctly."""
        code = """from sqlalchemy import Column
user = session.query(User).one()
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.execute(select(User)).scalars().one()" in result
        assert "session.query(User).one()" not in result
        assert any(c.transform_name == "query_one_to_select" for c in changes)

    def test_query_one_or_none_to_select(self):
        """Test session.query(Model).one_or_none() transforms correctly."""
        code = """from sqlalchemy import Column
user = session.query(User).one_or_none()
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.execute(select(User)).scalars().one_or_none()" in result
        assert any(c.transform_name == "query_one_or_none_to_select" for c in changes)


class TestQueryFilterTransforms:
    """Tests for session.query().filter() transformations."""

    def test_query_filter_all(self):
        """Test session.query(Model).filter(...).all() transforms correctly."""
        code = """from sqlalchemy import Column
users = session.query(User).filter(User.id == 1).all()
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.execute(select(User).where(User.id == 1)).scalars().all()" in result
        assert "session.query" not in result
        assert ".filter(" not in result

    def test_query_filter_first(self):
        """Test session.query(Model).filter(...).first() transforms correctly."""
        code = """from sqlalchemy import Column
user = session.query(User).filter(User.id == 1).first()
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.execute(select(User).where(User.id == 1)).scalars().first()" in result

    def test_query_multiple_filters(self):
        """Test multiple chained filters are transformed correctly."""
        code = """from sqlalchemy import Column
users = session.query(User).filter(User.active == True).filter(User.id > 5).all()
"""
        result, changes = transform_sqlalchemy(code)
        assert "select(User).where(User.active == True).where(User.id > 5)" in result
        assert "scalars().all()" in result


class TestQueryFilterByTransforms:
    """Tests for session.query().filter_by() transformations."""

    def test_query_filter_by_all(self):
        """Test session.query(Model).filter_by(key=val).all() transforms correctly."""
        code = """from sqlalchemy import Column
users = session.query(User).filter_by(name="John").all()
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.execute(select(User).where(User.name == " in result
        assert "scalars().all()" in result
        assert ".filter_by" not in result


class TestQueryGetTransforms:
    """Tests for session.query().get() transformations."""

    def test_query_get_to_session_get(self):
        """Test session.query(Model).get(id) transforms to session.get(Model, id)."""
        code = """from sqlalchemy import Column
user = session.query(User).get(1)
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.get(User, 1)" in result
        assert "session.query(User).get(1)" not in result
        assert any(c.transform_name == "query_get_to_session_get" for c in changes)

    def test_query_get_with_variable_id(self):
        """Test session.query(Model).get(user_id) transforms correctly."""
        code = """from sqlalchemy import Column
user = session.query(User).get(user_id)
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.get(User, user_id)" in result


class TestQueryCountTransforms:
    """Tests for session.query().count() transformations."""

    def test_query_count_to_select(self):
        """Test session.query(Model).count() transforms correctly."""
        code = """from sqlalchemy import Column
count = session.query(User).count()
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.execute(select(func.count()).select_from(User)).scalar()" in result
        assert "session.query(User).count()" not in result
        assert any(c.transform_name == "query_count_to_select_count" for c in changes)

    def test_query_count_adds_func_import(self):
        """Test that func import is added when count() is transformed."""
        code = """from sqlalchemy import Column
count = session.query(User).count()
"""
        result, changes = transform_sqlalchemy(code)
        assert "func" in result
        # Both select and func should be in imports
        assert "select" in result


class TestQueryTransformImportManagement:
    """Tests for import management during query transformations."""

    def test_select_not_duplicated(self):
        """Test select import is not added if already present."""
        code = """from sqlalchemy import Column, select
users = session.query(User).all()
"""
        result, changes = transform_sqlalchemy(code)
        # select should only appear once in import
        import_line = [line for line in result.split("\n") if "from sqlalchemy import" in line][0]
        assert import_line.count("select") == 1

    def test_func_not_duplicated(self):
        """Test func import is not added if already present."""
        code = """from sqlalchemy import Column, func
count = session.query(User).count()
"""
        result, changes = transform_sqlalchemy(code)
        # func should only appear twice: in import and in func.count()
        import_line = [line for line in result.split("\n") if "from sqlalchemy import" in line][0]
        assert import_line.count("func") == 1


class TestQueryNonQueryCallsUnchanged:
    """Tests to ensure non-query calls are not affected."""

    def test_other_all_calls_unchanged(self):
        """Test that .all() on non-query objects is unchanged."""
        code = """from sqlalchemy import Column
items = some_list.all()
"""
        result, changes = transform_sqlalchemy(code)
        assert "some_list.all()" in result
        assert "select" not in result

    def test_other_first_calls_unchanged(self):
        """Test that .first() on non-query objects is unchanged."""
        code = """from sqlalchemy import Column
item = collection.first()
"""
        result, changes = transform_sqlalchemy(code)
        assert "collection.first()" in result
        assert "select" not in result

    def test_db_session_query_unchanged_without_terminal_method(self):
        """Test that query without terminal method is unchanged."""
        code = """from sqlalchemy import Column
query = session.query(User)
"""
        result, changes = transform_sqlalchemy(code)
        assert "session.query(User)" in result
        assert "select" not in result


class TestEngineExecuteDetection:
    """Tests for engine.execute() detection and warning."""

    def test_engine_execute_detected_by_create_engine_assignment(self):
        """Test engine.execute() is detected when engine is from create_engine()."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db")
result = engine.execute("SELECT * FROM users")
"""
        result, changes = transform_sqlalchemy(code)
        # Should record a warning with low confidence
        engine_changes = [c for c in changes if c.transform_name == "engine_execute_to_connect"]
        assert len(engine_changes) == 1
        assert engine_changes[0].confidence == 0.5
        assert "MANUAL MIGRATION REQUIRED" in engine_changes[0].notes
        # The code should still have text() wrapping applied
        assert 'engine.execute(text("SELECT * FROM users"))' in result

    def test_engine_execute_detected_by_variable_name(self):
        """Test engine.execute() is detected by variable name containing 'engine'."""
        code = """from sqlalchemy import create_engine
db_engine = some_factory()
result = db_engine.execute("SELECT * FROM users")
"""
        result, changes = transform_sqlalchemy(code)
        # Should record a warning based on name heuristic
        engine_changes = [c for c in changes if c.transform_name == "engine_execute_to_connect"]
        assert len(engine_changes) == 1
        assert engine_changes[0].confidence == 0.5

    def test_engine_execute_detected_simple_name(self):
        """Test engine.execute() is detected when variable is just 'engine'."""
        code = """from sqlalchemy import create_engine
engine = get_engine()
result = engine.execute("SELECT 1")
"""
        result, changes = transform_sqlalchemy(code)
        engine_changes = [c for c in changes if c.transform_name == "engine_execute_to_connect"]
        assert len(engine_changes) == 1

    def test_conn_execute_not_flagged_as_engine(self):
        """Test conn.execute() is not flagged as engine.execute()."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db")
with engine.connect() as conn:
    conn.execute("SELECT * FROM users")
"""
        result, changes = transform_sqlalchemy(code)
        # Should not have engine_execute_to_connect warning for conn.execute
        engine_changes = [c for c in changes if c.transform_name == "engine_execute_to_connect"]
        # Only the engine.execute on line 3 should be detected, not conn.execute
        # Actually there's no engine.execute in this code, so 0 changes expected
        assert len(engine_changes) == 0
        # But text wrapping should still happen
        assert 'conn.execute(text("SELECT * FROM users"))' in result

    def test_session_execute_not_flagged_as_engine(self):
        """Test session.execute() is not flagged as engine.execute()."""
        code = """from sqlalchemy import create_engine
session.execute("SELECT * FROM users")
"""
        result, changes = transform_sqlalchemy(code)
        # Should not have engine_execute_to_connect warning
        engine_changes = [c for c in changes if c.transform_name == "engine_execute_to_connect"]
        assert len(engine_changes) == 0
        # Text wrapping should still happen
        assert 'session.execute(text("SELECT * FROM users"))' in result

    def test_engine_execute_with_text_already_wrapped(self):
        """Test engine.execute() with text() already applied still gets warning."""
        code = """from sqlalchemy import create_engine, text
engine = create_engine("sqlite:///test.db")
result = engine.execute(text("SELECT * FROM users"))
"""
        result, changes = transform_sqlalchemy(code)
        # Should still record the warning even if text() is already used
        engine_changes = [c for c in changes if c.transform_name == "engine_execute_to_connect"]
        assert len(engine_changes) == 1
        # Code should be unchanged since text() already wraps it
        assert 'engine.execute(text("SELECT * FROM users"))' in result

    def test_engine_execute_multiple_calls(self):
        """Test multiple engine.execute() calls each get warnings."""
        code = """from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db")
result1 = engine.execute("SELECT * FROM users")
result2 = engine.execute("SELECT * FROM orders")
"""
        result, changes = transform_sqlalchemy(code)
        engine_changes = [c for c in changes if c.transform_name == "engine_execute_to_connect"]
        assert len(engine_changes) == 2
