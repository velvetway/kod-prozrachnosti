"""Отчёт по проверке в формате DOCX: параметры, версии данных, таблица позиций,
карточки сигналов с источниками и формулами, решения специалиста."""
import io

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Mm, Pt, RGBColor

from .core.calc import fmt
from .core.pipeline import ACTIVE_LEVELS, summary
from .models import Check

LEVEL = {"high": "Высокий", "medium": "Средний", "review": "Проверить сопоставление", "none": "Нет",
         "nomatch": "Нет ориентира", "nodata": "Нет данных"}
KIND = {"price": "Цена", "volume": "Объём на 1 м²", "escalation": "Удорожание"}
SOURCES = {"fgiscs": "ФГИС ЦС", "eis": "ЕИС", "market": "рынок"}


def _cell(cell, text: str, bold: bool = False, size: int = 9) -> None:
    cell.text = ""
    run = cell.paragraphs[0].add_run(text)
    run.bold = bold
    run.font.size = Pt(size)


def build(check: Check) -> bytes:
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Mm(297), Mm(210)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Mm(15))
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(11)

    sm = summary(check)
    demo = any(v.get("is_demo") for v in check.data_versions.values())

    doc.add_heading(f"Отчёт о проверке № {check.number}", level=1)
    doc.add_paragraph(check.title)
    synthetic_used = [x for x in check.params["sources"] if x in ("eis", "market")]
    if demo and (synthetic_used or check.object_type):
        p = doc.add_paragraph()
        parts = []
        if synthetic_used:
            parts.append("контракты-аналоги ЕИС и рыночные предложения")
        if check.object_type:
            parts.append("объекты-аналоги для контроля объёмов")
        r = p.add_run("Сметные цены ФГИС ЦС — реальные данные портала fgiscs.minstroyrf.ru. "
                      f"Синтетические (демонстрационные) данные: {', '.join(parts)}. Выводы, зависящие от "
                      "синтетических данных, не являются подтверждёнными.")
        r.bold = True
        r.font.color.rgb = RGBColor(0x9A, 0x1C, 0x14)

    doc.add_heading("Параметры проверки", level=2)
    rows = [
        ("Документ", f"{check.file_name}; SHA-256 {check.file_sha256}"),
        ("Регион и ценовая зона", f"{check.region.name}; {check.zone.name if check.zone else 'зона не указана'}"),
        ("Уровень цен", check.quarter + (f"; квартал исходных цен {check.base_quarter}" if check.base_quarter else "")),
        ("Объект", f"{check.object_type}, {fmt(check.capacity, 0)} м²" if check.object_type else "не указан"),
        ("Источники ориентиров", ", ".join(SOURCES[x] for x in check.params["sources"])),
        ("Пороги, %", f"цена {check.params['price_thresholds']}; объём {check.params['volume_thresholds']}; "
                      f"удорожание {check.params['escalation_thresholds']} (средний, высокий)"),
        ("Версии справочников", "; ".join(
            f"{code} — {v['source_file']}, {v['records']} записей, "
            f"{'синтетические' if v['is_demo'] else 'реальные'}, SHA-256 {v['sha256'][:12]}…"
            for code, v in check.data_versions.items())),
        ("Контрольная сумма результата", check.result_sha256),
        ("Дата проверки", check.created_at.strftime("%d.%m.%Y %H:%M")),
    ]
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for k, v in rows:
        c = t.add_row().cells
        _cell(c[0], k, True)
        _cell(c[1], v)
    t.columns[0].width = Mm(60)

    doc.add_heading("Итоги", level=2)
    doc.add_paragraph(
        f"Позиций: {sm['items']}, сопоставлено с ориентиром: {sm['matched']}. "
        f"Сигналов: высоких {sm['high']}, средних {sm['medium']}, на проверку сопоставления {sm['review']}. "
        f"Превышение над ценовым ориентиром по высоким и средним сигналам: {fmt(sm['overpay_price'])} ₽; "
        f"стоимость перерасхода материалов: {fmt(sm['overpay_volume'])} ₽; "
        f"удорожание сверх индекса: {fmt(sm['overpay_escalation'])} ₽. Суммы не складываются: "
        f"одна позиция может давать сигналы разных видов.")

    doc.add_heading("Позиции", level=2)
    head = ["№", "Наименование", "Ед.", "Кол-во", "Цена, ₽", "Ресурс КСР / сопоставимость",
            "Ориентир, ₽ за ед. ресурса", "Цена", "Объём", "Удорожание"]
    t = doc.add_table(rows=1, cols=len(head))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in zip(t.rows[0].cells, head):
        _cell(c, h, True, 8)
    for it in check.items:
        sig = {sg.kind: sg for sg in it.signals}
        price = sig.get("price")
        m = it.match
        res = f"{m.resource.code} {m.resource.name} / {m.level} ({m.score:.2f})" if m and m.resource else "не сопоставлено"

        def lv(kind):
            sg = sig.get(kind)
            if not sg:
                return "—"
            return LEVEL[sg.level] + (f", {fmt(sg.deviation_pct, 1)} %" if sg.deviation_pct is not None else "")

        vals = [str(it.position), it.name, it.unit, fmt(it.quantity, 3).rstrip("0").rstrip(","), fmt(it.price), res,
                fmt(price.benchmark) if price and price.benchmark else "—", lv("price"), lv("volume"), lv("escalation")]
        cells = t.add_row().cells
        for c, v in zip(cells, vals):
            _cell(c, v, False, 8)
    widths = [8, 58, 12, 18, 22, 58, 24, 24, 24, 19]          # мм, сумма = ширина полосы набора
    t.autofit = False
    for row in t.rows:
        for c, w in zip(row.cells, widths):
            c.width = Mm(w)

    active = [(it, sg) for it in check.items for sg in it.signals if sg.level in ACTIVE_LEVELS]
    doc.add_heading("Карточки сигналов", level=2)
    if not active:
        doc.add_paragraph("Сигналов нет.")
    for it, sg in active:
        doc.add_heading(f"Позиция {it.position}. {it.name} — {KIND[sg.kind]}: {LEVEL[sg.level]}", level=3)
        doc.add_paragraph(f"Расчёт: {sg.formula}")
        if sg.details.get("overpay_formula"):
            doc.add_paragraph(f"Сумма: {sg.details['overpay_formula']}")
        if sg.kind == "price":
            for src in sg.details.get("sources", []):
                kind = "синтетические данные" if src.get("synthetic") else "реальные данные"
                doc.add_paragraph(f"{src['title']}: {fmt(src['value'])} ₽ (записей: {src['count']}; {kind})",
                                  style="List Bullet")
                for row in src["rows"][:8]:
                    basis = f" ({row['index_basis']})" if row.get("index_basis") and row["index"] != 1 else ""
                    doc.add_paragraph(f"{row['doc_ref']}: {fmt(row['price'])} ₽ × индекс {row['index']}{basis} = "
                                      f"{fmt(row['indexed'])} ₽", style="List Bullet 2")
        if sg.kind == "volume":
            d = sg.details
            doc.add_paragraph(f"Медиана удельного расхода {fmt(d['median'], 4)} {d['unit']}/м², коридор "
                              f"{fmt(d['low'], 4)}–{fmt(d['high'], 4)}; {d['scope']}, объектов: {d['count']}.")
        if sg.kind == "escalation":
            d = sg.details
            doc.add_paragraph(f"Исходная цена {fmt(d['base_price'])} ₽ ({d['base_quarter']}); индекс {d['index']} — "
                              f"{d.get('index_basis', d['group'])}"
                              f"{', ресурсов: ' + str(d['index_n']) if d.get('index_n') else ''} (по сметным ценам ФГИС ЦС).")
        if it.match and it.match.level in ("Низкая", "Средняя"):
            doc.add_paragraph(f"Сопоставимость {it.match.level.lower()} ({it.match.score:.2f}): {it.match.note}.")
        for dec in sg.decisions:
            doc.add_paragraph(f"Решение {dec.created_at.strftime('%d.%m.%Y %H:%M')}, {dec.author}: {dec.outcome}. "
                              f"{dec.comment}")

    doc.add_heading("Оговорка", level=2)
    doc.add_paragraph("Сигнал указывает на позицию, требующую проверки обоснования цены или объёма. Система не "
                      "устанавливает факт нарушения и не делает выводов о действиях должностных лиц или "
                      "участников закупки. Расчёт воспроизводится по приведённым формулам и источникам.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
