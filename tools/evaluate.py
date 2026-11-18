"""Оценка прототипа на тестовом наборе с заранее известными отклонениями (demo/expected.json).

Считает: извлечение позиций, корректность сопоставления с ресурсом КСР, совпадение сигналов
с ожидаемыми (без лишних и пропущенных), полноту объяснения в карточках сигналов,
воспроизводимость (повторный расчёт → та же контрольная сумма) и время обработки документа.
Расчёт выполняется дважды: по трём источникам и только по реальным сметным ценам ФГИС ЦС.

Запуск: python tools/evaluate.py → docs/test_results.md и docs/test_results.json
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/eval.db"
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ACTIVE = {"high", "medium", "review"}


def expected_signals(exp: str) -> set[tuple[str, str]]:
    if exp == "нет ориентира":
        return set()
    kind, level = exp.split(";")[0].split(" ")[0].split(":")
    return {(kind, level)} if level in ACTIVE else set()


def main() -> None:
    manifest = json.loads((ROOT / "demo" / "expected.json").read_text(encoding="utf-8"))
    results = {}
    with TestClient(app) as c:
        assert c.post("/api/login", json={"login": "admin", "password": "admin"}).status_code == 200
        demo = {d["file"]: d for d in c.get("/api/demo").json()}
        for mode, sources in (("три источника", ["fgiscs", "eis", "market"]), ("только ФГИС ЦС", ["fgiscs"])):
            m = {"docs": 0, "rows": 0, "parsed": 0, "to_match": 0, "matched_ok": 0, "nomatch_expected": 0,
                 "nomatch_ok": 0, "tp": 0, "fp": 0, "fn": 0, "explained": 0, "active": 0, "reproducible": 0,
                 "seconds": [], "errors": []}
            for d in manifest:
                info = demo[d["file"]]
                data = {k: str(info[k]) for k in ("region_id", "zone_id", "quarter", "object_type", "capacity",
                                                  "base_quarter") if info.get(k)}
                data["sources"] = json.dumps(sources)
                t = time.perf_counter()
                r = c.post("/api/checks", files={"file": (d["file"], (ROOT / "demo" / d["file"]).read_bytes())}, data=data)
                m["seconds"].append(time.perf_counter() - t)
                check = c.get(f"/api/checks/{r.json()['id']}").json()
                m["docs"] += 1
                m["rows"] += len(d["items"])
                m["parsed"] += len(check["items"])
                for it, e in zip(check["items"], d["items"]):
                    got_res = (it["match"]["resource"] or {}).get("code")
                    if e["resource"]:
                        m["to_match"] += 1
                        m["matched_ok"] += got_res == e["resource"]
                        if got_res != e["resource"]:
                            m["errors"].append(f"{d['file']} поз. {it['position']}: сопоставлено {got_res}, ожидалось {e['resource']}")
                    else:
                        m["nomatch_expected"] += 1
                        m["nomatch_ok"] += got_res is None
                    got = {(s["kind"], s["level"]) for s in it["signals"] if s["level"] in ACTIVE}
                    want = expected_signals(e["expected"])
                    m["tp"] += len(got & want)
                    m["fp"] += len(got - want)
                    m["fn"] += len(want - got)
                    for kind, level in got ^ want:
                        m["errors"].append(f"{d['file']} поз. {it['position']}: сигнал {kind}/{level} не совпал с ожиданием «{e['expected']}»")
                    for s in it["signals"]:
                        if s["level"] in ACTIVE:
                            m["active"] += 1
                            card = c.get(f"/api/signals/{s['id']}").json()["signal"]
                            ok = bool(card["formula"]) and "%" in card["formula"]
                            if s["kind"] == "price":
                                ok &= all(r_["doc_ref"] and r_["quarter"] for src in card["details"]["sources"] for r_ in src["rows"])
                            m["explained"] += ok
                rerun = c.post(f"/api/checks/{check['id']}/rerun").json()
                m["reproducible"] += rerun["identical"]
            results[mode] = m
    out_json = {k: {**v, "seconds": [round(x, 3) for x in v["seconds"]]} for k, v in results.items()}
    (ROOT / "docs" / "test_results.json").write_text(json.dumps(out_json, ensure_ascii=False, indent=1), encoding="utf-8")

    def pct(a, b):
        return f"{a} из {b} ({100 * a / b:.0f} %)" if b else "—"

    lines = ["# Результаты тестирования прототипа", "",
             "Тестовый набор: 3 синтетических документа (смета школы и смета благоустройства — Брянская область, "
             "спецификация поликлиники с изменением цены — Томская область), 25 позиций. Коды, наименования и "
             "сметные цены ресурсов — реальные данные ФГИС ЦС; цены в документах заданы как ориентир × известный "
             "коэффициент, поэтому правильный ответ известен заранее (`demo/expected.json`). Контракты ЕИС, "
             "рыночные предложения и объекты-аналоги — синтетические.", "",
             "Набор мал и составлен командой: результаты показывают, что логика работает как задумано, "
             "но не являются оценкой точности на реальных сметах. Эта оценка — задача пилота.", "",
             "| Показатель | " + " | ".join(results) + " |", "|---|" + "---|" * len(results)]
    rows = [
        ("Извлечено позиций из документов", lambda m: pct(m["parsed"], m["rows"])),
        ("Позиции сопоставлены с нужным ресурсом КСР", lambda m: pct(m["matched_ok"], m["to_match"])),
        ("Позиция без аналога в КСР не сопоставлена", lambda m: pct(m["nomatch_ok"], m["nomatch_expected"])),
        ("Ожидаемые сигналы выявлены (полнота)", lambda m: pct(m["tp"], m["tp"] + m["fn"])),
        ("Лишние сигналы (ложные срабатывания)", lambda m: str(m["fp"])),
        ("Сигналы с формулой и источниками", lambda m: pct(m["explained"], m["active"])),
        ("Повторный расчёт дал ту же контрольную сумму", lambda m: pct(m["reproducible"], m["docs"])),
        ("Время проверки документа, с (макс.)", lambda m: f"{max(m['seconds']):.2f}"),
    ]
    for title, fn in rows:
        lines.append(f"| {title} | " + " | ".join(fn(m) for m in results.values()) + " |")
    errs = [e for m in results.values() for e in m["errors"]]
    lines += ["", "Расхождения: " + ("нет." if not errs else ""), *[f"- {e}" for e in errs], "",
              "Автотесты (`cd backend && python -m pytest -q`) проверяют то же на уровне кода, а также пересчёт "
              "единиц, отказ на некорректных файлах, роли доступа и журнал аудита.", "",
              "Воспроизвести: `python tools/evaluate.py`."]
    (ROOT / "docs" / "test_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
