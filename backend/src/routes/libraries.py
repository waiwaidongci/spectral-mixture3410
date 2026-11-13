from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from ..config.database import get_db
from ..controllers.dependencies import current_user,roles
from ..constants.roles import Role
from ..schemas.library import LibraryOutput,LibraryGapUpdate
from ..schemas.endmember import EndmemberOutput
from ..services.library_service import list_libraries,update_gap
from ..services.endmember_service import list_endmembers
router=APIRouter(prefix="/libraries",tags=["libraries"])
@router.get("",response_model=list[LibraryOutput])
def index(db:Session=Depends(get_db),user=Depends(current_user)):return list_libraries(db)
@router.get("/{lid}/endmembers",response_model=list[EndmemberOutput])
def endmembers(lid:int,db:Session=Depends(get_db),user=Depends(current_user)):return list_endmembers(db,lid)
@router.patch("/{lid}/interpolation-gap")
def set_gap(lid:int,data:LibraryGapUpdate,db:Session=Depends(get_db),user=Depends(roles(Role.ADMIN,Role.ANALYST))):
    """设置该库逐点谱对齐的相邻测点最大跨度（nm）；不自动改写历史，需从原始谱重算。"""
    return update_gap(db,lid,data,user)
