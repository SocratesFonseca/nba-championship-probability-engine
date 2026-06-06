from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.data_ingestion import get_data_status

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/status")
def data_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    return get_data_status(db)