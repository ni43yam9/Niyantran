from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.security import get_current_user
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.device import (
    DeviceRegisterRequest,
    DeviceUpdateRequest,
    DeviceResponse,
)
from backend.app.services.device_service import (
    register_or_update_device,
    list_user_devices,
    get_user_device,
    update_device,
    revoke_device,
)

devices_router = APIRouter(prefix="/api/devices", tags=["Device Management"])


@devices_router.post(
    "/register",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register or update client device",
)
def register_device(
    req: DeviceRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Registers a client device for multi-device identification.
    Device registration does not initiate data synchronization.
    """
    device = register_or_update_device(db, user_id=current_user.id, req=req)
    return DeviceResponse.model_validate(device)


@devices_router.get(
    "",
    response_model=List[DeviceResponse],
    status_code=status.HTTP_200_OK,
    summary="List registered devices for authenticated user",
)
def list_devices(
    include_revoked: bool = Query(True, description="Whether to include revoked devices in list"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns all registered devices associated with the current user account."""
    devices = list_user_devices(db, user_id=current_user.id, include_revoked=include_revoked)
    return [DeviceResponse.model_validate(d) for d in devices]


@devices_router.get(
    "/{device_id}",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get single device details",
)
def get_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves metadata and status of a registered device with ownership validation."""
    device = get_user_device(db, user_id=current_user.id, device_id=device_id)
    return DeviceResponse.model_validate(device)


@devices_router.patch(
    "/{device_id}",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update device information",
)
def patch_device(
    device_id: str,
    req: DeviceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates device name, form factor or client version with ownership validation."""
    device = update_device(db, user_id=current_user.id, device_id=device_id, req=req)
    return DeviceResponse.model_validate(device)


@devices_router.post(
    "/{device_id}/revoke",
    response_model=DeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke device access",
)
def revoke(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revokes authorization for a device.
    The revoked device record is retained for audit logging and conflict tracking.
    """
    device = revoke_device(db, user_id=current_user.id, device_id=device_id)
    return DeviceResponse.model_validate(device)
