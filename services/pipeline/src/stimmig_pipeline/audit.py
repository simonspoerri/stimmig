"""Audit log: every write records who did what, with the changed fields."""

from typing import Any

from sqlalchemy.orm import Session

from .auth import Principal
from .models import AuditEvent


def record(
    session: Session, principal: Principal, action: str, entity: str, entity_id: object, **data: Any
) -> None:
    session.add(
        AuditEvent(actor=principal.actor, action=action, entity=entity, entity_id=str(entity_id), data=data)
    )
