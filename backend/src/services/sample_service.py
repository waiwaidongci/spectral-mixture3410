from fastapi import HTTPException
from ..models import SpectralLibrary,MixtureSample
from ..utils.serialize import record
from ..utils.clock import now
from ..constants.alignment import RULE_VERSION,DEFAULT_MAX_GAP
from .spectrum_service import align_to_grid
from .audit_service import log

def list_samples(db,lid):
    if not db.get(SpectralLibrary,lid):raise HTTPException(404,"光谱库不存在")
    return [record(s) for s in db.query(MixtureSample).filter_by(library_id=lid).order_by(MixtureSample.code)]
def annotate_sample(db,sid,data,user):
    row=db.get(MixtureSample,sid)
    if not row:raise HTTPException(404,"样本不存在")
    row.note=data.note;log(db,user.email,"sample.annotate",row.code);db.commit();return record(row)

def _apply_alignment(row,library,gap,rule_version=RULE_VERSION):
    """从样本留存的原始谱按给定规则重算对齐，写回 observed 与插值依据。"""
    result=align_to_grid(row.raw_wavelengths,row.raw_values,library.wavelengths,
                         max_gap=gap,rule_version=rule_version)
    row.observed=result["aligned_observed"]
    row.alignment=result
    row.alignment_rule=rule_version
    row.alignment_max_gap=result["max_gap_nm"]
    row.aligned_at=now()
    return result

def import_pointwise(db,sid,data,user):
    row=db.get(MixtureSample,sid)
    if not row:raise HTTPException(404,"样本不存在")
    library=db.get(SpectralLibrary,row.library_id)
    gap=DEFAULT_MAX_GAP if data.max_gap_nm is None else data.max_gap_nm
    if data.max_gap_nm is None and library.max_interp_gap:
        gap=library.max_interp_gap
    # 先校验/整理并对齐；任何拒绝都在写库前抛 422，原始 observed 不被破坏。
    result=align_to_grid(data.raw_wavelengths,data.raw_values,library.wavelengths,
                         max_gap=gap,rule_version=RULE_VERSION)
    # 保存整理后的原始谱（升序、去重）与插值依据；observed 换成库网格对齐读数。
    row.raw_wavelengths=result["raw_wavelengths"]
    row.raw_values=result["raw_values"]
    row.observed=result["aligned_observed"]
    row.alignment=result
    row.alignment_rule=RULE_VERSION
    row.alignment_max_gap=result["max_gap_nm"]
    row.aligned_at=now()
    log(db,user.email,"sample.pointwise_import",row.code)
    db.commit()
    return record(row)

def realign_sample(db,sid,user):
    """规则（库插值跨度）更新后，从原始谱按当前规则重算。无原始谱的旧样本无可重算。"""
    row=db.get(MixtureSample,sid)
    if not row:raise HTTPException(404,"样本不存在")
    if not row.raw_wavelengths:
        raise HTTPException(422,"该样本没有留存逐点原始谱，无需也无法重算；其 observed 仍为原始网格读数")
    library=db.get(SpectralLibrary,row.library_id)
    before_rule,before_gap=row.alignment_rule,row.alignment_max_gap
    _apply_alignment(row,library,library.max_interp_gap or DEFAULT_MAX_GAP)
    log(db,user.email,"sample.realign",
        f"{row.code}|{before_rule}/{before_gap}->{row.alignment_rule}/{row.alignment_max_gap}")
    db.commit()
    return record(row)

def realign_library(db,lid,user):
    """库规则更新后批量重算该库全部含原始谱的样本；旧网格样本保持原样可照常分析。"""
    library=db.get(SpectralLibrary,lid)
    if not library:raise HTTPException(404,"光谱库不存在")
    rows=db.query(MixtureSample).filter_by(library_id=lid).filter(
        MixtureSample.raw_wavelengths.isnot(None)).order_by(MixtureSample.code).all()
    if not rows:raise HTTPException(422,"该库暂无逐点导入的样本，没有需要重算的原始谱")
    changed=[]
    for row in rows:
        before=f"{row.alignment_rule}/{row.alignment_max_gap}"
        _apply_alignment(row,library,library.max_interp_gap or DEFAULT_MAX_GAP)
        changed.append({"code":row.code,"before":before,
                        "after":f"{row.alignment_rule}/{row.alignment_max_gap}"})
    log(db,user.email,"library.realign_samples",f"{library.code}:{len(rows)}")
    db.commit()
    return {"library_id":lid,"rule_version":RULE_VERSION,"max_interp_gap":library.max_interp_gap,
            "realigned":changed}
