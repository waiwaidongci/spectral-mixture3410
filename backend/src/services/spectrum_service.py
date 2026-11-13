"""逐点测谱的校验与线性插值对齐。

外协仪器的波长网格与所选光谱库不一致，不能直接按列套端元。本模块负责：
1. 校验逐点读数（有限数值、长度一致、乱序可整理、重复波长冲突拒绝）；
2. 按库波长网格做分段线性插值，保存原始谱与每个目标点的插值依据；
3. 覆盖不足（目标波长落在原始测程之外）或相邻测点跨度超过可设上限时拒绝；
4. 绝不外推：任何库波长必须夹在两个真实测点之间。

规则（插值跨度上限等）集中在 ``RULE_VERSION`` 对应的数据结构里，样本留存规则版本，
规则更新后从原始谱按新规则重算；已冻结进研究快照的对齐结果不受影响。
"""
import numpy as np
from fastapi import HTTPException
from ..constants.alignment import (
    RULE_VERSION, DEFAULT_MAX_GAP, GAP_LIMITS, MAX_POINTS,
)


def _reject(detail):
    raise HTTPException(422, detail)


def normalize_points(raw_wavelengths, raw_values):
    """校验并整理逐点读数，返回按波长升序排列的 (波长数组, 读数数组)。

    乱序允许，自动排序；同一波长出现多个不一致读数时拒绝（不擅自取均值）。
    """
    if not isinstance(raw_wavelengths, list) or not isinstance(raw_values, list):
        _reject("波长与读数须为等长数组")
    if len(raw_wavelengths) != len(raw_values):
        _reject("波长数组与读数数组长度不一致，无法逐点配对")
    if len(raw_wavelengths) < 2:
        _reject("逐点测谱至少需要两个测点，无法插值对齐")
    if len(raw_wavelengths) > MAX_POINTS:
        _reject(f"测点数 {len(raw_wavelengths)} 超过上限 {MAX_POINTS}")
    try:
        pairs = [(float(w), float(v)) for w, v in zip(raw_wavelengths, raw_values)]
    except (TypeError, ValueError):
        _reject("波长与读数须全部为数值")
    for w, v in pairs:
        if not (np.isfinite(w) and np.isfinite(v)):
            _reject("波长与读数均须为有限数值，拒绝 NaN/无穷")
    # 乱序可整理：按波长稳定排序。
    pairs.sort(key=lambda p: p[0])
    # 重复波长：读数一致视为重复登记去重，冲突则拒绝。
    deduped = []
    for w, v in pairs:
        if deduped and w == deduped[-1][0]:
            if not np.isclose(v, deduped[-1][1], rtol=1e-12, atol=1e-12):
                _reject(f"波长 {w:g}nm 存在互相冲突的重复读数，请核对原始测谱后重新导入")
            continue
        deduped.append((w, v))
    if len(deduped) < 2:
        _reject("去重后有效测点少于两个，无法插值对齐")
    wl = np.array([p[0] for p in deduped], dtype=float)
    val = np.array([p[1] for p in deduped], dtype=float)
    return wl, val


def align_to_grid(raw_wavelengths, raw_values, target_wavelengths, max_gap=DEFAULT_MAX_GAP,
                  rule_version=RULE_VERSION):
    """把逐点测谱线性插值到库波长网格，返回对齐结果与完整插值依据。

    拒绝条件（均不外推）：
    - 目标波长落在原始测程 [w_min, w_max] 之外（覆盖不足）；
    - 目标波长两侧真实测点的跨度超过 ``max_gap``（可设插值跨度）。
    """
    try:
        gap = float(max_gap)
    except (TypeError, ValueError):
        _reject("插值跨度上限须为数值")
    if not (GAP_LIMITS[0] <= gap <= GAP_LIMITS[1]):
        _reject(f"插值跨度上限须在 {GAP_LIMITS[0]:g}–{GAP_LIMITS[1]:g}nm 之间")

    wl, val = normalize_points(raw_wavelengths, raw_values)

    if not isinstance(target_wavelengths, list) or len(target_wavelengths) < 2:
        _reject("所选光谱库波长网格无效")
    try:
        grid = np.array([float(x) for x in target_wavelengths], dtype=float)
    except (TypeError, ValueError):
        _reject("光谱库波长须全部为数值")
    if not np.isfinite(grid).all() or np.any(np.diff(grid) <= 0):
        _reject("光谱库波长须有限且严格递增")

    src_min, src_max = float(wl[0]), float(wl[-1])
    below = grid[grid < src_min]
    above = grid[grid > src_max]
    if below.size or above.size:
        parts = []
        if below.size:
            parts.append(f"{below.min():g}–{below.max():g}nm 短于测程起点 {src_min:g}nm")
        if above.size:
            parts.append(f"{above.min():g}–{above.max():g}nm 超出测程终点 {src_max:g}nm")
        _reject("原始测谱覆盖不足：" + "；".join(parts) + "。系统不外推，请补测后重新导入")

    # 逐目标点显式分段线性插值。数组规模很小（库 ≤64 波段、测点 ≤512），
    # 显式循环能精确表达"命中测点"与"末点边界"，避免向量化的除零与索引边界问题。
    aligned = []
    basis = []
    for g in grid:
        j = int(np.searchsorted(wl, g, side="right"))
        if j == 0:  # 覆盖检查已保证 g >= wl[0]，此处仅为数值兜底
            j = 1
        if j >= len(wl):  # g == 测程终点：精确取末测点，不外推
            lo_i = hi_i = len(wl) - 1
            exact = True
        else:
            lo_i, hi_i = j - 1, j
            exact = wl[lo_i] == g
        lo_w, hi_w = float(wl[lo_i]), float(wl[hi_i])
        lo_v, hi_v = float(val[lo_i]), float(val[hi_i])
        span = hi_w - lo_w
        if span > gap + 1e-12:
            _reject(
                f"库波长 {g:g}nm 需在 {lo_w:g}–{hi_w:g}nm 间插值，"
                f"测点跨度 {span:g}nm 超过可设上限 {gap:g}nm；请加密该区间测点，不能外推补齐"
            )
        if exact or span == 0.0:
            weight = 0.0
            value = lo_v
            exact = True
        else:
            weight = (float(g) - lo_w) / span
            value = (1.0 - weight) * lo_v + weight * hi_v
        aligned.append(value)
        basis.append({
            "target_wavelength": float(g),
            "left_wavelength": lo_w,
            "right_wavelength": hi_w,
            "left_value": lo_v,
            "right_value": hi_v,
            "weight_right": float(weight),
            "span": float(span),
            "exact": bool(exact),
            "aligned_value": float(value),
        })
    return {
        "rule_version": rule_version,
        "method": "piecewise-linear",
        "target_wavelengths": grid.tolist(),
        "aligned_observed": aligned,
        "raw_wavelengths": wl.tolist(),
        "raw_values": val.tolist(),
        "max_gap_nm": gap,
        "extrapolation": "forbidden",
        "interpolation_basis": basis,
        "raw_point_count": int(len(wl)),
        "grid_point_count": int(len(grid)),
    }
