from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DatasetImport(Base):
    __tablename__ = "dataset_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    data_dir: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_files_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    present_files_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class DatasetFileMetadata(Base):
    __tablename__ = "dataset_file_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
