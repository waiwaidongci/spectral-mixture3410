"""对齐纯函数边界测试：不连数据库，直接验证 spectrum_service 的拒绝与插值依据。"""
import sys
sys.path.insert(0, "/workspace/backend")
import numpy as np
from fastapi import HTTPException
from src.services.spectrum_service import align_to_grid, normalize_points

GRID = [400.0, 425.0, 450.0, 475.0, 500.0]
# 每 25nm 一个测点的"仪器"原始谱，覆盖 400–500。
wl = [400, 425, 450, 475, 500]
val = [0.10, 0.20, 0.30, 0.40, 0.50]
fails = []

def check(name, fn):
    try:
        fn()
        print(f"PASS {name}")
    except AssertionError as e:
        fails.append(name)
        print(f"FAIL {name}: {e}")
    except Exception as e:  # noqa
        fails.append(name)
        print(f"ERROR {name}: {type(e).__name__} {e}")

def expect_reject(name, fn, needle):
    try:
        fn()
        fails.append(name)
        print(f"FAIL {name}: 应当拒绝但通过了")
    except HTTPException as e:
        ok = e.status_code == 422 and needle in e.detail
        print(("PASS " if ok else "FAIL ") + f"{name}: 422 {e.detail}")
        if not ok:
            fails.append(name)

# 1. 网格完全重合：对齐值=原值，exact=True，不外推。
def t1():
    r = align_to_grid(wl, val, GRID, max_gap=60)
    assert np.allclose(r["aligned_observed"], val), r["aligned_observed"]
    assert all(b["exact"] for b in r["interpolation_basis"])
    assert r["extrapolation"] == "forbidden"
    assert r["raw_point_count"] == 5 and r["grid_point_count"] == 5
    assert r["rule_version"] == "pointwise-linear-v1"
check("网格重合 exact", t1)

# 2. 乱序输入可整理，结果与升序一致。
def t2():
    order = [3, 0, 4, 1, 2]
    r = align_to_grid([wl[i] for i in order], [val[i] for i in order], GRID, max_gap=60)
    assert np.allclose(r["raw_wavelengths"], sorted(wl))
    assert np.allclose(r["aligned_observed"], val)
check("乱序整理", t2)

# 3. 半网格偏移线性插值：测点 412.5/437.5...，目标 425 落在中间，权重 0.5。
def t3():
    wl2 = [412.5, 437.5, 462.5, 487.5]
    v2 = [0.0, 1.0, 0.0, 1.0]
    r = align_to_grid(wl2, v2, [425.0, 450.0, 475.0], max_gap=60)
    assert np.allclose(r["aligned_observed"], [0.5, 0.5, 0.5]), r["aligned_observed"]
    b = r["interpolation_basis"][0]
    assert b["left_wavelength"] == 412.5 and b["right_wavelength"] == 437.5
    assert abs(b["weight_right"] - 0.5) < 1e-12 and abs(b["span"] - 25.0) < 1e-12
check("线性插值依据", t3)

# 4. 重复波长且读数一致 -> 去重通过。
def t4():
    w = [400, 400, 425, 450, 475, 500]
    v = [0.1, 0.1, 0.2, 0.3, 0.4, 0.5]
    r = align_to_grid(w, v, GRID, max_gap=60)
    assert r["raw_point_count"] == 5
check("重复波长一致去重", t4)

# 5. 重复波长读数冲突 -> 拒绝并说明。
expect_reject("重复波长冲突",
              lambda: align_to_grid([400, 400, 425], [0.1, 0.9, 0.2], [400.0, 425.0], 60),
              "冲突的重复读数")

# 6. 覆盖不足：测程短于库网格起点 -> 拒绝，不外推。
expect_reject("覆盖不足(左侧)",
              lambda: align_to_grid([425, 450, 500], [0.2, 0.3, 0.5], GRID, 60),
              "覆盖不足")
# 7. 覆盖不足：超出测程终点 -> 拒绝。
expect_reject("覆盖不足(右侧)",
              lambda: align_to_grid([400, 425, 475], [0.1, 0.2, 0.4], GRID, 60),
              "覆盖不足")

# 8. 跨度过大：测点 400 与 480，跨度 80 > 上限 60 -> 拒绝。
expect_reject("超过插值跨度",
              lambda: align_to_grid([400, 480, 500], [0.1, 0.4, 0.5], GRID, 60),
              "超过可设上限")
# 同一数据放宽上限到 80 -> 通过，且 425/450/475 都是内插。
def t8():
    r = align_to_grid([400, 480, 500], [0.1, 0.4, 0.5], GRID, max_gap=80)
    # 425: 0.1 + (25/80)*0.3
    assert abs(r["aligned_observed"][1] - (0.1 + 25 / 80 * 0.3)) < 1e-12
check("放宽跨度后内插", t8)

# 9. 非有限值拒绝。
expect_reject("NaN 拒绝", lambda: normalize_points([400, 425], [0.1, float("nan")]), "有限数值")
# 10. 长度不一致 / 点数不足。
expect_reject("长度不一致", lambda: normalize_points([400, 425, 450], [0.1, 0.2]), "长度不一致")
expect_reject("测点不足", lambda: normalize_points([400], [0.1]), "至少需要两个测点")
# 11. 跨度参数越界。
expect_reject("跨度参数越界", lambda: align_to_grid(wl, val, GRID, max_gap=999), "插值跨度上限须在")

# 12. 精确边界：测程恰好等于网格边界不算外推。
def t12():
    r = align_to_grid([400.0, 500.0], [0.1, 0.5], [400.0, 500.0], max_gap=200)
    assert np.allclose(r["aligned_observed"], [0.1, 0.5])
check("测程边界恰好覆盖", t12)

# 13. 浮点波长非严格但可排序、目标网格严格递增由库保证；非递增网格拒绝。
expect_reject("目标网格非递增",
              lambda: align_to_grid(wl, val, [400.0, 400.0, 450.0], 60),
              "严格递增")

print()
print("全部通过" if not fails else f"失败 {len(fails)} 项: {fails}")
sys.exit(1 if fails else 0)
