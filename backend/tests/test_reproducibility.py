from conftest import run_demo


def test_same_input_same_result(client, demo):
    d = demo["01_bryansk_school_smeta.xlsx"]
    a, b = run_demo(client, d), run_demo(client, d)
    assert a["result_sha256"] == b["result_sha256"]
    assert a["file_sha256"] == b["file_sha256"]


def test_rerun_identical_and_keeps_decisions(client, demo):
    c = run_demo(client, demo["01_bryansk_school_smeta.xlsx"])
    sig = next(s for it in c["items"] for s in it["signals"] if s["level"] == "high")
    assert client.post(f"/api/signals/{sig['id']}/decision", json={"outcome": "Передать на проверку", "comment": "т"}).status_code == 200
    r = client.post(f"/api/checks/{c['id']}/rerun").json()
    assert r["identical"]
    after = client.get(f"/api/checks/{c['id']}").json()
    decided = [s for it in after["items"] for s in it["signals"] if s["decision"]]
    assert len(decided) == 1 and decided[0]["decision"]["outcome"] == "Передать на проверку"


def test_threshold_change_changes_digest(client, demo):
    d = demo["01_bryansk_school_smeta.xlsx"]
    a = run_demo(client, d)
    b = run_demo(client, d, price_thresholds="[10, 20]")
    assert a["result_sha256"] != b["result_sha256"]
    assert b["summary"]["high"] > a["summary"]["high"]
