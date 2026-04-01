from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session


class CounselorRepository:
    def __init__(self, db: Session):
        self._db = db

    def list_id_and_name(self) -> List:
        sql = "SELECT id, name FROM counselor"
        result = self._db.execute(text(sql)).mappings().all()
        return list(result)
