import uuid

from pydantic import BaseModel, Field


class AgentStreamRequest(BaseModel):
    user_text: str | None = None
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audio_base64: str | None = None


class StoreItem(BaseModel):
    branch_id: str
    name: str
    city: str | None = None
    address: str | None = None
    display_address: str
    distance_km: float
    has_pickup: bool = False
    latitude: float | None = None
    longitude: float | None = None


class NearestStoresResponse(BaseModel):
    query: str
    resolved_address: str
    latitude: float
    longitude: float
    stores: list[StoreItem]


class SavedAddressItem(BaseModel):
    address_id: str
    label: str | None = None
    text: str
