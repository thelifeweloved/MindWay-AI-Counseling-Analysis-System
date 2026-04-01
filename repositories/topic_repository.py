from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session


class TopicRepository:
    def __init__(self, db: Session):
        self._db = db

    def list_register_topics_ordered(self) -> List:
        rows = self._db.execute(
            text("""
                SELECT id, code, name FROM topic
                WHERE type = 'REGISTER'
                ORDER BY FIELD(code,
                    'ANXIETY', 'DEPRESSION', 'RELATION', 'FAMILY',
                    'ROMANCE', 'CAREER', 'WORK', 'TRAUMA', 'SELF_ESTEEM', 'ETC')
            """)
        ).mappings().all()
        return list(rows)
