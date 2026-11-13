"""逐点测谱对齐规则的常量与版本。

规则调整时升级 RULE_VERSION；样本留存导入时的规则版本，
规则更新后从原始谱按新规则重算，已冻结的研究快照保持原对齐结果。
"""
RULE_VERSION = "pointwise-linear-v1"
# 可设的相邻测点最大波长跨度（nm）默认值与允许区间。
DEFAULT_MAX_GAP = 60.0
GAP_MIN = 5.0
GAP_MAX = 200.0
GAP_LIMITS = (GAP_MIN, GAP_MAX)
# 单次导入允许的测点数上限，防止异常大文件。
MAX_POINTS = 512
