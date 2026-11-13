import numpy as np
from fastapi import HTTPException
from ..models import SpectralLibrary,Endmember,MixtureSample
from ..utils.serialize import record
from .unmix_algorithm import matrix_diagnostics
from .audit_service import log

def list_libraries(db):
    rows=[]
    for library in db.query(SpectralLibrary).order_by(SpectralLibrary.code):
        members=db.query(Endmember).filter_by(library_id=library.id).order_by(Endmember.code).all()
        try:_,d=matrix_diagnostics(np.array([e.spectrum for e in members]).T)
        except ValueError as e:d={"supported":False,"condition_number":None,"reason":str(e)}
        rows.append(dict(record(library),endmember_count=len(members),sample_count=db.query(MixtureSample).filter_by(library_id=library.id).count(),supported=d['supported'],condition_number=d['condition_number'],reason=d['reason']))
    return rows

def update_gap(db,lid,data,user):
    library=db.get(SpectralLibrary,lid)
    if not library:raise HTTPException(404,"光谱库不存在")
    before=library.max_interp_gap
    library.max_interp_gap=data.max_interp_gap
    pending=db.query(MixtureSample).filter_by(library_id=lid).filter(
        MixtureSample.raw_wavelengths.isnot(None)).count()
    log(db,user.email,"library.gap_update",f"{library.code}|{before}->{library.max_interp_gap}nm")
    db.commit()
    # 既有样本的对齐结果不会被静默改写：需要从原始谱显式重算后，新研究才使用新读数。
    return {"library_id":lid,"max_interp_gap":library.max_interp_gap,
            "pointwise_samples_pending_realignment":pending}
