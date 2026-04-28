from pydantic import BaseModel, ConfigDict


class MLModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    cost_per_request: float
