"""Tests for ORM relationship validation (M2M secondary style + mapper gate)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "agents"))

from _shared.validate_orm_relationships import (  # noqa: E402
    check_m2m_secondary_style,
    validate_orm_relationships,
)


def _write_models(app_dir: Path, author: str, book: str) -> None:
    models = app_dir / "app" / "models"
    models.mkdir(parents=True)
    (models / "__init__.py").write_text(
        "from app.models import author, book  # noqa: F401\n",
        encoding="utf-8",
    )
    (models / "author.py").write_text(author, encoding="utf-8")
    (models / "book.py").write_text(book, encoding="utf-8")


def test_flags_string_secondary_like_bookstore_bug(tmp_path: Path) -> None:
    app_dir = tmp_path / "bookstore"
    _write_models(
        app_dir,
        author='''\
from sqlalchemy.orm import Mapped, relationship
class Author:
    books: Mapped[list] = relationship("Book", secondary="book_authors", back_populates="authors")
''',
        book='''\
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Mapped, relationship
from app.database import Base
book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", ForeignKey("books.id"), primary_key=True),
    Column("author_id", ForeignKey("authors.id"), primary_key=True),
)
class Book:
    authors: Mapped[list] = relationship("Author", secondary=book_authors, back_populates="books")
''',
    )
    errors = check_m2m_secondary_style(app_dir)
    assert errors, "string secondary must fail"
    assert any('secondary="book_authors"' in e for e in errors)
    assert any("string form is forbidden" in e for e in errors)


def test_allows_shared_table_object_on_both_sides(tmp_path: Path) -> None:
    app_dir = tmp_path / "bookstore-ok"
    _write_models(
        app_dir,
        author='''\
from sqlalchemy.orm import Mapped, relationship
from app.models.book import book_authors
class Author:
    books: Mapped[list] = relationship("Book", secondary=book_authors, back_populates="authors")
''',
        book='''\
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Mapped, relationship
from app.database import Base
book_authors = Table(
    "book_authors",
    Base.metadata,
    Column("book_id", ForeignKey("books.id"), primary_key=True),
    Column("author_id", ForeignKey("authors.id"), primary_key=True),
)
class Book:
    authors: Mapped[list] = relationship("Author", secondary=book_authors, back_populates="books")
''',
    )
    assert check_m2m_secondary_style(app_dir) == []


def test_validate_skips_mapper_when_no_models(tmp_path: Path) -> None:
    app_dir = tmp_path / "api-only"
    (app_dir / "app").mkdir(parents=True)
    assert validate_orm_relationships(app_dir, run_mapper_check=True) == []


def test_developer_prompt_documents_m2m_rule() -> None:
    text = (
        _REPO_ROOT / "agents" / "developer-agent" / "developer_agent.py"
    ).read_text(encoding="utf-8")
    assert 'secondary="book_authors"' in text or "secondary=\"...\"" in text
    assert "M2M / junction" in text or "Many-to-many / junction" in text
    assert "validate_orm_relationships" in text
