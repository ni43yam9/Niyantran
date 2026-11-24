import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.device import Device
from backend.app.schemas.device import DeviceRegisterRequest, DeviceUpdateRequest


def register_or_update_device(db: Session, user_id: str, req: DeviceRegisterRequest) -> Device:
    """
    Registers a client device for a user.
    If the device UUID already exists, updates its activity, name, type, and status to active.
    Ensures device registration does not trigger data synchronization.
    """
    now = datetime.now(timezone.utc)
    target_uuid = req.device_uuid.strip() if req.device_uuid else str(uuid.uuid4())

    device = db.query(Device).filter(Device.device_uuid == target_uuid).first()

    if device:
        # Update existing device record
        device.user_id = user_id
        device.device_name = req.device_name.strip()
        device.device_type = req.device_type
        device.operating_system = req.operating_system
        if req.client_version:
            device.client_version = req.client_version
        device.status = "active"
        device.last_active_at = now
    else:
        # Create fresh device identity
        device = Device(
            id=str(uuid.uuid4()),
            device_uuid=target_uuid,
            user_id=user_id,
            device_name=req.device_name.strip(),
            device_type=req.device_type,
            operating_system=req.operating_system,
            client_version=req.client_version,
            registered_at=now,
            last_active_at=now,
            status="active",
            last_synced_at=None,
        )
        db.add(device)

    db.commit()
    db.refresh(device)
    return device


def list_user_devices(db: Session, user_id: str, include_revoked: bool = True) -> List[Device]:
    """Lists all registered devices belonging to the authenticated user."""
    query = db.query(Device).filter(Device.user_id == user_id)
    if not include_revoked:
        query = query.filter(Device.status == "active")
    return query.order_by(Device.last_active_at.desc()).all()


def get_user_device(db: Session, user_id: str, device_id: str) -> Device:
    """
    Retrieves a single device by ID with strict user ownership validation.
    Raises 404 if not found or belongs to another user.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device or device.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id}' was not found or access is unauthorized.",
        )
    return device


def update_device(db: Session, user_id: str, device_id: str, req: DeviceUpdateRequest) -> Device:
    """Updates device metadata with ownership verification."""
    device = get_user_device(db, user_id, device_id)
    now = datetime.now(timezone.utc)

    if req.device_name is not None:
        device.device_name = req.device_name.strip()
    if req.device_type is not None:
        device.device_type = req.device_type
    if req.operating_system is not None:
        device.operating_system = req.operating_system
    if req.client_version is not None:
        device.client_version = req.client_version

    device.last_active_at = now
    db.commit()
    db.refresh(device)
    return device


def revoke_device(db: Session, user_id: str, device_id: str) -> Device:
    """
    Revokes authorization for a device.
    Revoked devices are preserved in database for audit history and tombstone tracking.
    """
    device = get_user_device(db, user_id, device_id)
    now = datetime.now(timezone.utc)

    device.status = "revoked"
    device.last_active_at = now
    db.commit()
    db.refresh(device)
    return device
