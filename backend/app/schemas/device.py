from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

DeviceType = Literal["Laptop", "Mobile", "Tablet", "Desktop", "Other"]
DeviceStatus = Literal["active", "revoked"]


class DeviceRegisterRequest(BaseModel):
    device_uuid: Optional[str] = Field(None, description="Client generated stable device UUID; generated server-side if omitted")
    device_name: str = Field(..., min_length=1, max_length=128, description="Human readable device name (e.g. Nityam's Laptop)")
    device_type: DeviceType = Field("Laptop", description="Form factor of the client device")
    operating_system: str = Field("Unknown", max_length=64, description="Host operating system (e.g. Windows 11, macOS, Android)")
    client_version: Optional[str] = Field("2.0.0", max_length=32, description="Niyantra application client version")


class DeviceUpdateRequest(BaseModel):
    device_name: Optional[str] = Field(None, min_length=1, max_length=128)
    device_type: Optional[DeviceType] = None
    operating_system: Optional[str] = Field(None, max_length=64)
    client_version: Optional[str] = Field(None, max_length=32)


class DeviceResponse(BaseModel):
    id: str
    device_uuid: str
    user_id: str
    device_name: str
    device_type: str
    operating_system: str
    client_version: Optional[str]
    registered_at: datetime
    last_active_at: datetime
    status: str
    last_synced_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
