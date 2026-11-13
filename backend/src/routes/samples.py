from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..controllers.dependencies import current_user,roles
from ..constants.roles import Role
from ..schemas.sample import SampleOutput,SampleAnnotation,PointwiseSpectrumImport
from ..services.sample_service import (
    list_samples,annotate_sample,import_pointwise,realign_sample,realign_library,
)
router=APIRouter(tags=["samples"])
@router.get("/libraries/{lid}/samples",response_model=list[SampleOutput])
def index(lid:int,db:Session=Depends(get_db),user=Depends(current_user)):return list_samples(db,lid)
@router.patch("/samples/{sid}")
def annotate(sid:int,data:SampleAnnotation,db:Session=Depends(get_db),user=Depends(roles(Role.ADMIN,Role.ANALYST))):return annotate_sample(db,sid,data,user)
@router.post("/samples/{sid}/pointwise-spectrum",response_model=SampleOutput)
def import_spectrum(sid:int,data:PointwiseSpectrumImport,db:Session=Depends(get_db),user=Depends(roles(Role.ADMIN,Role.ANALYST))):
    """导入逐点测谱，按所选库波长网格线性插值对齐；不外推，冲突/越界/跨度过大即拒绝。"""
    return import_pointwise(db,sid,data,user)
@router.post("/samples/{sid}/realign",response_model=SampleOutput)
def realign(sid:int,db:Session=Depends(get_db),user=Depends(roles(Role.ADMIN,Role.ANALYST))):
    """规则更新后从留存的原始谱按当前库规则重算对齐读数。"""
    return realign_sample(db,sid,user)
@router.post("/libraries/{lid}/realign-samples")
def realign_lib(lid:int,db:Session=Depends(get_db),user=Depends(roles(Role.ADMIN,Role.ANALYST))):
    """批量重算该库全部逐点导入样本；旧网格样本保持原样、照常分析。"""
    return realign_library(db,lid,user)
