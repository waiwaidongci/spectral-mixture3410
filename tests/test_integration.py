"""端到端集成测试：SQLite 内存库 + FastAPI TestClient + 真实 JWT，假 Redis 队列。

验证关键业务不变量：
- 逐点谱导入按库网格对齐并留存原始谱/插值依据；冲突、覆盖不足、跨度过大拒绝且不外推；
- 规则更新后从原始谱重算，再建研究使用新读数；
- 既有研究 input_snapshot 与获批导出始终对应导入时的旧对齐结果；
- 旧网格样本（无原始谱）照常列出、照常进入研究；
- 写操作对 viewer 403、未认证 401。
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SEED_DEMO"] = "false"
os.environ["REDIS_URL"] = "redis://localhost:6399/0"

import sys
sys.path.insert(0, "/workspace/backend")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.database import Base, get_db
from src.config import database as db_module
from src.models import User, SpectralLibrary, Endmember, MixtureSample, UnmixRun, ReplicationNote
from src.utils.security import hash_password, make_token
from src.services import run_service
from src.services.analysis_service import analyze_unmix
from src.main import app

# 共享连接的内存 SQLite，保证多请求看到同一库。
engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                       poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)

# 假 Redis：只记录入队，不真正连接。
class FakeQueue:
    def __init__(self): self.jobs = []
    def rpush(self, key, value): self.jobs.append(int(value)); return len(self.jobs)
    def ping(self): return True
fake_queue = FakeQueue()
run_service.queue = fake_queue

def override_db():
    s = TestSession()
    try:
        yield s
    finally:
        s.close()
app.dependency_overrides[get_db] = override_db

client = TestClient(app)

GRID = [400.0, 425.0, 450.0, 475.0, 500.0]
_seq = 0

@pytest.fixture()
def seed_world():
    global _seq
    _seq += 1
    tag = str(_seq)
    s = TestSession()
    admin = User(email=f"a{tag}@x.demo", name="负责人", role="admin",
                 password_hash=hash_password("pw123456"))
    analyst = User(email=f"r{tag}@x.demo", name="研究员", role="analyst",
                   password_hash=hash_password("pw123456"))
    viewer = User(email=f"v{tag}@x.demo", name="阅读者", role="viewer",
                  password_hash=hash_password("pw123456"))
    s.add_all([admin, analyst, viewer]); s.flush()
    lib = SpectralLibrary(code=f"LT-{tag}", name="测试库", description="d",
                          wavelengths=GRID, source="unit", max_interp_gap=60.0)
    s.add(lib); s.flush()
    s.add_all([
        Endmember(library_id=lib.id, code="EM-1", name="端元一",
                  spectrum=[0.10, 0.20, 0.30, 0.40, 0.50]),
        Endmember(library_id=lib.id, code="EM-2", name="端元二",
                  spectrum=[0.50, 0.40, 0.30, 0.20, 0.10]),
    ])
    # 旧网格样本：无逐点原始谱，observed 直接是网格读数。
    legacy = MixtureSample(code=f"LT-{tag}-OLD", library_id=lib.id, name="旧样本",
                           observed=[0.3, 0.3, 0.3, 0.3, 0.3], note="旧网格读数，应可照常分析。")
    target = MixtureSample(code=f"LT-{tag}-NEW", library_id=lib.id, name="外协样本",
                           observed=[0.0] * 5, note="待导入逐点谱。")
    s.add_all([legacy, target]); s.commit()
    ids = dict(lib=lib.id, admin=admin.id, analyst=analyst.id, viewer=viewer.id,
               legacy=legacy.id, target=target.id)
    s.close()
    return ids

def auth(uid):
    return {"Authorization": "Bearer " + make_token(type("U", (), {"id": uid})())}

# 与库网格错开的外协测点：端点 400/500 精确命中，库内点 425/450/475 落在两测点正中。
def dense_raw(scale=1.0):
    wl = [400.0, 412.5, 437.5, 462.5, 487.5, 500.0]
    val = [round((0.2 + 0.05 * i) * scale, 6) for i in range(6)]
    return wl, val

def test_import_aligns_and_persists_basis(seed_world):
    # 改用半网格错开的测点：412.5/437.5 夹住库点 425。
    wl = [412.5, 437.5, 462.5, 487.5]
    val = [0.10, 0.30, 0.50, 0.70]
    r = client.post(f"/samples/{seed_world['target']}/pointwise-spectrum",
                    headers=auth(seed_world["analyst"]),
                    json={"raw_wavelengths": wl, "raw_values": val})
    assert r.status_code == 422 and "不外推" in r.json()["detail"]  # 400/500 未覆盖
    # 补足端点后再导入。
    wl = [400.0] + wl + [500.0]
    val = [0.08] + val + [0.80]
    r = client.post(f"/samples/{seed_world['target']}/pointwise-spectrum",
                    headers=auth(seed_world["analyst"]),
                    json={"raw_wavelengths": wl, "raw_values": val})
    assert r.status_code == 200, r.text
    body = r.json()
    # 对齐到 5 个库波段，长度与网格一致；原始谱与插值依据均留存。
    assert len(body["observed"]) == 5
    assert body["raw_wavelengths"] == sorted(wl)
    assert body["alignment"]["rule_version"] == "pointwise-linear-v1"
    assert body["alignment"]["extrapolation"] == "forbidden"
    assert len(body["alignment"]["interpolation_basis"]) == 5
    b0 = body["alignment"]["interpolation_basis"][1]  # 目标 425，落在 412.5/437.5 正中
    assert b0["target_wavelength"] == 425.0 and abs(b0["weight_right"] - 0.5) < 1e-12
    assert b0["exact"] is False and abs(b0["span"] - 25.0) < 1e-12
    # 端点 400 精确命中首测点。
    assert body["alignment"]["interpolation_basis"][0]["exact"] is True
    # 对齐值即相邻测点线性平均（425 处：(0.10+0.30)/2）。
    assert abs(body["observed"][1] - 0.20) < 1e-12

def test_rejects_duplicate_conflict_coverage_and_gap(seed_world):
    h = auth(seed_world["analyst"]); sid = seed_world["target"]
    # 重复波长冲突
    r = client.post(f"/samples/{sid}/pointwise-spectrum", headers=h,
                    json={"raw_wavelengths": [400, 400, 450], "raw_values": [0.1, 0.9, 0.3]})
    assert r.status_code == 422 and "冲突的重复读数" in r.json()["detail"]
    # 覆盖不足（左侧），不外推
    r = client.post(f"/samples/{sid}/pointwise-spectrum", headers=h,
                    json={"raw_wavelengths": [425, 450, 500], "raw_values": [0.2, 0.3, 0.5]})
    assert r.status_code == 422 and "不外推" in r.json()["detail"]
    # 跨度过大：400->480 跨度 80 > 库上限 60
    r = client.post(f"/samples/{sid}/pointwise-spectrum", headers=h,
                    json={"raw_wavelengths": [400, 480, 500], "raw_values": [0.1, 0.4, 0.5]})
    assert r.status_code == 422 and "超过可设上限" in r.json()["detail"]
    # 拒绝后样本 observed 不被破坏（仍是初始占位）
    s = TestSession(); row = s.get(MixtureSample, sid)
    assert row.raw_wavelengths is None and row.alignment is None; s.close()

def test_gap_setting_then_realign_from_raw(seed_world):
    h = auth(seed_world["analyst"]); sid = seed_world["target"]; lid = seed_world["lib"]
    wl, val = dense_raw()
    client.post(f"/samples/{sid}/pointwise-spectrum", headers=h,
                json={"raw_wavelengths": wl, "raw_values": val})
    # 收紧跨度到 10nm：重算应拒绝（相邻测点 12.5 > 10），且保留原对齐结果。
    r = client.patch(f"/libraries/{lid}/interpolation-gap", headers=h,
                     json={"max_interp_gap": 10})
    assert r.status_code == 200 and r.json()["pointwise_samples_pending_realignment"] == 1
    r = client.post(f"/samples/{sid}/realign", headers=h)
    assert r.status_code == 422 and "超过可设上限" in r.json()["detail"]
    s = TestSession(); before = list(s.get(MixtureSample, sid).observed); s.close()
    # 放宽到 25nm：重算成功，observed 由原始谱重新生成（数值应与首次一致，同规则同原始谱）。
    client.patch(f"/libraries/{lid}/interpolation-gap", headers=h, json={"max_interp_gap": 25})
    r = client.post(f"/samples/{sid}/realign", headers=h)
    assert r.status_code == 200 and r.json()["alignment_max_gap"] == 25.0
    s = TestSession(); after = s.get(MixtureSample, sid).observed; s.close()
    assert all(abs(a - b) < 1e-15 for a, b in zip(after, before))

def test_legacy_sample_still_analyzable_and_no_realign(seed_world):
    h = auth(seed_world["analyst"])
    # 旧样本列表正常返回，raw 字段为 None。
    r = client.get(f"/libraries/{seed_world['lib']}/samples", headers=h)
    legacy = next(x for x in r.json() if x["id"] == seed_world["legacy"])
    assert legacy["raw_wavelengths"] is None and legacy["alignment"] is None
    # 无原始谱不能重算。
    r = client.post(f"/samples/{seed_world['legacy']}/realign", headers=h)
    assert r.status_code == 422 and "原始谱" in r.json()["detail"]
    # 旧样本可直接进入研究（快照创建成功并入队）。
    r = client.post("/runs", headers=h, json={
        "name": "旧样本研究", "library_id": seed_world["lib"],
        "sample_ids": [seed_world["legacy"]], "noise_sigma": 0.005,
        "repeats": 20, "seed": 7})
    assert r.status_code == 202, r.text

def test_run_snapshot_and_approved_export_keep_old_alignment(seed_world):
    h = auth(seed_world["analyst"]); sid = seed_world["target"]
    wl, val = dense_raw()
    imported = client.post(f"/samples/{sid}/pointwise-spectrum", headers=h,
                           json={"raw_wavelengths": wl, "raw_values": val}).json()
    first_observed = list(imported["observed"])

    # 用首次对齐结果建研究并生成完成结果 + 批准记录。
    r = client.post("/runs", headers=h, json={
        "name": "外协样本研究", "library_id": seed_world["lib"],
        "sample_ids": [sid], "noise_sigma": 0.005, "repeats": 20, "seed": 11})
    assert r.status_code == 202
    run_id = r.json()["id"]
    s = TestSession(); run = s.get(UnmixRun, run_id)
    snapshot = run.input_snapshot
    assert snapshot["samples"][0]["observed"] == first_observed  # 冻结首次对齐
    result = analyze_unmix(snapshot, 0.005, 20, 11)
    run.status = "completed"; run.result = result
    s.add(ReplicationNote(run_id=run_id, title="t", interpretation="i" * 10,
                          proposal="p" * 10, status="approved", owner="研究员",
                          reviewer="负责人", review_note="ok"))
    s.commit(); old_hash = result["input_hash"]; s.close()

    # 重新导入一份不同读数的新逐点谱：样本当前 observed 改变。
    wl2, val2 = dense_raw(scale=1.3)
    again = client.post(f"/samples/{sid}/pointwise-spectrum", headers=h,
                        json={"raw_wavelengths": wl2, "raw_values": val2}).json()
    assert again["observed"] != first_observed

    # 既有研究快照与结果指纹不变；获批导出仍对应旧对齐。
    s = TestSession(); run = s.get(UnmixRun, run_id)
    assert run.input_snapshot["samples"][0]["observed"] == first_observed
    assert run.result["input_hash"] == old_hash; s.close()
    r = client.get(f"/runs/{run_id}/export", headers=auth(seed_world["viewer"]))
    assert r.status_code == 200 and old_hash in r.text
    # 新建研究才使用新读数。
    r = client.post("/runs", headers=h, json={
        "name": "新读数研究", "library_id": seed_world["lib"],
        "sample_ids": [sid], "noise_sigma": 0.005, "repeats": 20, "seed": 12})
    new_run = r.json()
    s = TestSession()
    assert s.get(UnmixRun, new_run["id"]).input_snapshot["samples"][0]["observed"] == again["observed"]
    s.close()

def test_rbac_and_auth(seed_world):
    sid = seed_world["target"]; wl, val = dense_raw()
    # viewer 写操作 403
    r = client.post(f"/samples/{sid}/pointwise-spectrum",
                    headers=auth(seed_world["viewer"]),
                    json={"raw_wavelengths": wl, "raw_values": val})
    assert r.status_code == 403
    # 未认证 401
    r = client.post(f"/samples/{sid}/pointwise-spectrum",
                    json={"raw_wavelengths": wl, "raw_values": val})
    assert r.status_code == 401
    # 跨度越界被 schema 拒绝
    r = client.patch(f"/libraries/{seed_world['lib']}/interpolation-gap",
                     headers=auth(seed_world["admin"]), json={"max_interp_gap": 999})
    assert r.status_code == 422
