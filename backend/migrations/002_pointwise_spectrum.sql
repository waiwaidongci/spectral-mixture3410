-- 逐点测谱导入与按库波长网格对齐（pointwise-linear-v1）。
-- 仅用于升级已存在的库；全新数据库由 SQLAlchemy metadata 自动建表，无需执行。
-- MySQL 8 的 ADD COLUMN 不支持通用 IF NOT EXISTS，本脚本只对升级前的旧库执行一次。

ALTER TABLE spectral_libraries
    ADD COLUMN max_interp_gap DOUBLE NOT NULL DEFAULT 60.0;

ALTER TABLE mixture_samples
    ADD COLUMN raw_wavelengths JSON NULL,
    ADD COLUMN raw_values JSON NULL,
    ADD COLUMN alignment JSON NULL,
    ADD COLUMN alignment_rule VARCHAR(40) NULL,
    ADD COLUMN alignment_max_gap DOUBLE NULL,
    ADD COLUMN aligned_at VARCHAR(64) NULL;

-- 旧样本逐点字段为 NULL：observed 即原始网格读数，照常分析；新导入样本才走插值对齐。
-- 单库样本量小（演示为40），重算全表扫描即可，不额外建函数索引。
