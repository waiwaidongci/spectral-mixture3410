from pydantic import BaseModel,Field
class LibraryOutput(BaseModel):
    id:int
    code:str
    name:str
    description:str
    wavelengths:list[float]
    source:str
    endmember_count:int
    sample_count:int
    supported:bool
    condition_number:float|None
    reason:str
    max_interp_gap:float
class LibraryGapUpdate(BaseModel):
    max_interp_gap:float=Field(ge=5,le=200)
