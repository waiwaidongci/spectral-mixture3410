from sqlalchemy import String,Text,JSON,Double
from sqlalchemy.orm import Mapped,mapped_column
from ..config.database import Base
from ..constants.alignment import DEFAULT_MAX_GAP
class SpectralLibrary(Base):
    __tablename__="spectral_libraries"
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    name:Mapped[str]=mapped_column(String(120))
    description:Mapped[str]=mapped_column(Text)
    wavelengths:Mapped[list]=mapped_column(JSON)
    source:Mapped[str]=mapped_column(String(160))
    # 逐点测谱对齐所用的可设插值跨度上限（相邻测点，nm）；不外推。
    max_interp_gap:Mapped[float]=mapped_column(Double,default=DEFAULT_MAX_GAP)
