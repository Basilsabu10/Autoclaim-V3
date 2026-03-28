

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.db import models

logger = logging.getLogger(__name__)

RR_COUNTER_KEY = "rr_last_agent_index"


def assign_claim_to_agent(claim_id: int, db: Session) -> Optional[models.User]:
    
    # Fetch all active agents in stable registration order
    agents = (
        db.query(models.User)
        .filter(
            models.User.role == "agent",
            models.User.is_active == True,
        )
        .order_by(models.User.created_at.asc())   # stable order — new agents append to tail
        .all()
    )

    if not agents:
        logger.warning(
            "[AutoAssign] No active agents in pool — claim %s left unassigned.", claim_id
        )
        return None

    # Retrieve (or initialise) the rotation counter
    setting = (
        db.query(models.SystemSetting)
        .filter(models.SystemSetting.key == RR_COUNTER_KEY)
        .first()
    )
    if not setting:
        setting = models.SystemSetting(key=RR_COUNTER_KEY, value="0")
        db.add(setting)
        next_index = 0
    else:
        current_index = int(setting.value)
        next_index = (current_index + 1) % len(agents)

    setting.value = str(next_index)

    assigned = agents[next_index]
    logger.info(
        "[AutoAssign] Claim %s → Agent '%s' (slot %s / %s)",
        claim_id, assigned.name or assigned.email, next_index, len(agents) - 1,
    )
    return assigned


def get_rotation_status(db: Session) -> dict:
   
    agents = (
        db.query(models.User)
        .filter(
            models.User.role == "agent",
            models.User.is_active == True,
        )
        .order_by(models.User.created_at.asc())
        .all()
    )

    setting = (
        db.query(models.SystemSetting)
        .filter(models.SystemSetting.key == RR_COUNTER_KEY)
        .first()
    )

    if not agents:
        return {
            "agent_pool_size": 0,
            "next_agent": None,
            "next_index": None,
            "agents": [],
        }

    current_index = int(setting.value) if setting else 0
    next_index = (current_index + 1) % len(agents)
    next_agent = agents[next_index]

    return {
        "agent_pool_size": len(agents),
        "next_index": next_index,
        "next_agent": {
            "id": next_agent.id,
            "name": next_agent.name or next_agent.email,
            "email": next_agent.email,
        },
        "agents": [
            {
                "id": a.id,
                "name": a.name or a.email,
                "email": a.email,
                "is_next": (i == next_index),
            }
            for i, a in enumerate(agents)
        ],
    }
