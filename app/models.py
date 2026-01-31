from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Trim(BaseModel):
    left: float = Field(..., ge=0)
    right: float = Field(..., ge=0)
    top: float = Field(..., ge=0)
    bottom: float = Field(..., ge=0)

    class Config:
        extra = "forbid"


class Engine(BaseModel):
    packer: Optional[Literal["guillotine", "maxrects", "skyline"]] = None
    bin_select: Optional[Literal["best_fit", "first_fit"]] = None
    sort: Optional[Literal["area_desc", "maxside_desc", "none"]] = None

    class Config:
        extra = "forbid"


class Params(BaseModel):
    mode: Optional[Literal["guillotine", "nested"]] = None
    spacing_mm: float = Field(..., ge=0)
    trim_mm: Trim
    time_limit_ms: int = Field(..., ge=50)
    restarts: int = Field(..., ge=1)
    objective: Literal["min_waste", "min_sheets"]
    seed: Optional[int] = None
    engine: Optional[Engine] = None
    unit_scale: Optional[int] = None

    class Config:
        extra = "forbid"


class Stock(BaseModel):
    id: str
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    qty: int = Field(..., ge=1)

    class Config:
        extra = "forbid"


class Item(BaseModel):
    id: str
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    qty: int = Field(..., ge=1)
    rotation: Literal["forbid", "allow_90"]
    pattern_direction: Literal["none", "along_width", "along_height"]

    class Config:
        extra = "forbid"


class OptimizeRequest(BaseModel):
    units: Literal["mm"]
    params: Params
    stock: List[Stock] = Field(..., min_items=1)
    items: List[Item] = Field(..., min_items=1)

    class Config:
        extra = "forbid"


class EngineSummary(BaseModel):
    packer: str
    bin_select: str
    sort: str

    class Config:
        extra = "forbid"


class Summary(BaseModel):
    mode: str
    objective: str
    used_stock_count: int
    total_waste_area_mm2: float
    waste_percent: float
    time_ms: int
    restarts_used: int
    seed: int
    engine: EngineSummary

    class Config:
        extra = "forbid"


class Placement(BaseModel):
    item_id: str
    instance: int
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    rotated: bool
    pattern_direction: str

    class Config:
        extra = "forbid"


class Solution(BaseModel):
    stock_id: str
    index: int
    width_mm: float
    height_mm: float
    trim_mm: Trim
    placements: List[Placement]

    class Config:
        extra = "forbid"


class Artifacts(BaseModel):
    svg: str

    class Config:
        extra = "forbid"


class OptimizeResponse(BaseModel):
    status: Literal["ok"]
    summary: Summary
    solutions: List[Solution]
    artifacts: Artifacts

    class Config:
        extra = "forbid"


class ErrorResponse(BaseModel):
    status: Literal["error"]
    error_code: str
    message: str
    details: Optional[dict] = None

    class Config:
        extra = "forbid"
