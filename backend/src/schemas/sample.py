from pydantic import BaseModel,Field
class InterpolationBasisPoint(BaseModel):
    target_wavelength:float
    left_wavelength:float
    right_wavelength:float
    left_value:float
    right_value:float
    weight_right:float
    span:float
    exact:bool
    aligned_value:float
class AlignmentInfo(BaseModel):
    rule_version:str
    method:str
    target_wavelengths:list[float]
    aligned_observed:list[float]
    raw_wavelengths:list[float]
    raw_values:list[float]
    max_gap_nm:float
    extrapolation:str
    interpolation_basis:list[InterpolationBasisPoint]
    raw_point_count:int
    grid_point_count:int
class SampleOutput(BaseModel):
    id:int
    code:str
    library_id:int
    name:str
    observed:list[float]
    note:str
    raw_wavelengths:list[float]|None=None
    raw_values:list[float]|None=None
    alignment:AlignmentInfo|None=None
    alignment_rule:str|None=None
    alignment_max_gap:float|None=None
    aligned_at:str|None=None
class SampleAnnotation(BaseModel):
    note:str=Field(min_length=8,max_length=1500)
class PointwiseSpectrumImport(BaseModel):
    # 逐点测谱：波长与反射率读数一一对应，允许乱序；长度 2–512。
    raw_wavelengths:list[float]=Field(min_length=2,max_length=512)
    raw_values:list[float]=Field(min_length=2,max_length=512)
    # 可选：本次导入临时指定插值跨度上限；缺省用库设置。
    max_gap_nm:float|None=Field(default=None,ge=5,le=200)
