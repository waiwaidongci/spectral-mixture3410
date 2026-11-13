from sqlalchemy import String,Text,JSON,ForeignKey,Double
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..constants.alignment import DEFAULT_MAX_GAP
class MixtureSample(Base):
    __tablename__="mixture_samples"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(80),unique=True)
    library_id:Mapped[int]=mapped_column(ForeignKey("spectral_libraries.id"))
    name:Mapped[str]=mapped_column(String(120))
    observed:Mapped[list]=mapped_column(JSON)
    note:Mapped[str]=mapped_column(Text)
    # 逐点测谱导入：原始测点（乱序已按波长升序整理）与按库网格对齐后的读数。
    # 旧样本没有逐点导入时 raw_wavelengths 为 None，observed 即原始网格读数，照常分析。
    raw_wavelengths:Mapped[list|None]=mapped_column(JSON,nullable=True)
    raw_values:Mapped[list|None]=mapped_column(JSON,nullable=True)
    alignment:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    alignment_rule:Mapped[str|None]=mapped_column(String(40),nullable=True)
    alignment_max_gap:Mapped[float|None]=mapped_column(Double,nullable=True)
    aligned_at:Mapped[str|None]=mapped_column(String(64),nullable=True)
