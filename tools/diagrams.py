"""Схемы для приложений: архитектура и схема данных → docs/img/*.png.
Нужен Playwright (pip install playwright && playwright install chromium); в работе прототипа не участвует."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "img"
C = "#5b6675"
n = [0]

def arrow(x, y, length, d, label):
    n[0] += 1; i = n[0]; h = 4
    mk = f'<defs><marker id="m{i}" orient="auto" markerWidth="5" markerHeight="5" refX="2" refY="2"><path d="M0 0 L4 2 L0 4 Z" fill="{C}"/></marker></defs>'
    st = f'position:absolute;overflow:visible;fill:none;stroke:{C};stroke-width:2;stroke-linecap:round'
    if d in ("right", "left"):
        p = f"M 0 4 L {length-h} 4" if d == "right" else f"M {length} 4 L {h} 4"
        return f'<svg aria-label="{label}" width="{length}" height="8" style="{st};left:{x}px;top:{y-4}px">{mk}<path d="{p}" marker-end="url(#m{i})"/></svg>'
    p = f"M 4 0 L 4 {length-h}" if d == "down" else f"M 4 {length} L 4 {h}"
    return f'<svg aria-label="{label}" width="8" height="{length}" style="{st};left:{x-4}px;top:{y}px">{mk}<path d="{p}" marker-end="url(#m{i})"/></svg>'

def card(l, t, w, h, title, sub, bg="#fff", bd="#c9d2de"):
    return (f'<div style="position:absolute;left:{l}px;top:{t}px;width:{w}px;height:{h}px;box-sizing:border-box;padding:8px 14px;'
            f'display:flex;align-items:center;justify-content:center;text-align:center;background:{bg};border:1px solid {bd};'
            f'border-radius:8px;font-size:15px;line-height:20px;color:#1b2430"><span><b>{title}</b><br>{sub}</span></div>')

def lab(l, t, text, w=300):
    return f'<div style="position:absolute;left:{l}px;top:{t}px;width:{w}px;font-size:12px;font-weight:700;letter-spacing:.06em;color:{C}">{text}</div>'

def small(l, t, text, w=120):
    return f'<div style="position:absolute;left:{l}px;top:{t}px;width:{w}px;font-size:13px;line-height:16px;color:{C}">{text}</div>'

REAL, RB = "#e6f4ea", "#9cc9a8"
SYN, SB = "#f1f2f4", "#c3c8d0"

def architecture():
    A, K, L = [], [], []
    cx = [200, 536, 872, 1208]
    for x in cx:
        A.append(arrow(x, 240, 63, "down", "источник → загрузка"))
    A += [arrow(536, 392, 63, "down", "загрузка → БД"), arrow(1208, 392, 63, "down", "парсер → БД"),
          arrow(256, 552, 63, "down", "БД → сопоставление"), arrow(1152, 553, 63, "up", "сигналы → БД"),
          arrow(448, 664, 63, "right", ""), arrow(896, 664, 63, "right", ""), arrow(704, 713, 63, "up", ""),
          arrow(264, 820, 51, "right", ""), arrow(516, 820, 51, "right", ""), arrow(840, 820, 63, "right", "")]
    K += [card(64, 152, 272, 88, "ФГИС ЦС", "сметные цены, КСР · реальные данные", REAL, RB),
          card(400, 152, 272, 88, "ЕИС", "контракты-аналоги · синтетические", SYN, SB),
          card(736, 152, 272, 88, "Рынок, объекты-аналоги", "прайс-листы, расходы · синтетические", SYN, SB),
          card(1072, 152, 272, 88, "Смета / спецификация", "загружает специалист: XLSX, CSV", "#eef4fb", "#b9cde4"),
          card(64, 304, 944, 88, "Загрузка справочников (CSV)", "tools/fetch_fgiscs.py с портала ФГИС ЦС; импорт в разделе «Справочники» — администратор; каждая загрузка — версия с SHA-256"),
          card(1072, 304, 272, 88, "Парсер документа", "поиск заголовка, позиции, единицы, цены"),
          card(64, 456, 1280, 96, "PostgreSQL (SQLite для локального запуска)", "89 субъектов РФ · ценовые зоны · 2 944 ресурса КСР · 13 349 цен · объекты-аналоги · проверки, позиции, сопоставления, сигналы · журнал решений · журнал аудита · версии данных", "#f6f7f9", "#aab4c2"),
          card(64, 616, 384, 96, "Сопоставление", "код КСР → иначе нечёткое сравнение наименований и характеристик; пересчёт единиц; показатель сопоставимости"),
          card(512, 616, 384, 96, "Ориентиры и отклонения", "медиана источников; индекс из динамики цен ФГИС ЦС; цена, расход на 1 м², удорожание"),
          card(960, 616, 384, 96, "Уровень сигнала", "пороги; формула, источники и версии данных в карточке; контрольная сумма"),
          card(64, 776, 200, 88, "Специалист", "проверяет и решает", "#fff7e8", "#e3c98f"),
          card(316, 776, 200, 88, "Веб-интерфейс", "React, вход по ролям"),
          card(568, 776, 272, 88, "API", "FastAPI, сессии, аудит"),
          card(904, 776, 200, 88, "Отчёт", "DOCX")]
    L += ['<div style="position:absolute;left:64px;top:52px;font-size:26px;font-weight:700;color:#1b2430">Архитектура прототипа</div>',
          '<div style="position:absolute;left:64px;top:90px;width:1200px;font-size:14px;color:#5b6675">Путь данных от источников до решения специалиста. Зелёным — реальные данные, серым — синтетические. Запуск: docker compose up.</div>',
          lab(64, 128, "ИСТОЧНИКИ"), lab(64, 280, "ЗАГРУЗКА"), lab(64, 432, "ХРАНЕНИЕ"), lab(64, 592, "РАСЧЁТНОЕ ЯДРО"), lab(64, 752, "РАБОТА СПЕЦИАЛИСТА"),
          small(272, 576, "справочники"), small(1168, 576, "результаты"), small(720, 736, "запуск проверки"),
          small(1144, 788, "Одинаковый вход и версия данных дают идентичный результат", 210)]
    return 1408, 920, "".join(A + K + L)

def schema():
    boxes = [
        ("Регион", "89 субъектов, федеральный округ, признак пилота", "ref"),
        ("Ценовая зона", "→ регион", "ref"),
        ("Ресурс КСР", "код, наименование, единица, раздел", "ref"),
        ("Версия набора данных", "источник, SHA-256, записей, реальный/синтетический", "ref"),
        ("Ценовой ориентир", "→ ресурс, регион, зона, версия; источник fgiscs | eis | market, цена, квартал, документ", "ref"),
        ("Индекс цен", "→ регион; группа, квартал (если загружен официальный; иначе считается из цен ФГИС ЦС)", "ref"),
        ("Объект-аналог", "→ регион; тип, мощность, расход на 1 м² по кодам КСР", "ref"),
        ("Проверка", "→ регион, зона; файл и SHA-256, квартал, объект, пороги, версии данных, SHA-256 результата", "chk"),
        ("Позиция", "→ проверка; строка документа, код, наименование, единица, количество, цена, исходная цена", "chk"),
        ("Сопоставление", "→ позиция, ресурс; способ (код, наименование, вручную), показатель, пересчёт единиц", "chk"),
        ("Сигнал", "→ позиция; вид (цена, объём, удорожание), ориентир, отклонение, уровень, формула, источники", "chk"),
        ("Решение специалиста", "→ сигнал; итог, комментарий, автор, время", "hum"),
        ("Пользователь и сессия", "логин, роль (специалист, администратор), хеш пароля", "hum"),
        ("Событие аудита", "время, пользователь, действие, объект", "hum"),
    ]
    col = {"ref": ("#eef4fb", "#b9cde4"), "chk": ("#ffffff", "#aab4c2"), "hum": ("#fff7e8", "#e3c98f")}
    cells = "".join(f'<div style="background:{col[k][0]};border:1px solid {col[k][1]};border-radius:8px;padding:12px 14px;font-size:13px;line-height:19px"><div style="font-size:15px;font-weight:700;margin-bottom:4px">{t}</div>{d}</div>' for t, d, k in boxes)
    body = (f'<div style="position:absolute;left:56px;top:48px;width:1170px"><div style="font-size:26px;font-weight:700">Схема данных</div>'
            f'<div style="font-size:14px;color:#5b6675;margin:8px 0 20px">Синим — справочники, белым — данные проверки, жёлтым — люди и журналы. Стрелка «→» — ссылка на другую таблицу.</div>'
            f'<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px">{cells}</div>'
            f'<div style="font-size:14px;line-height:20px;color:#5b6675;margin-top:18px">Маркеры риска хранятся в «Сигнале»: отклонение цены от ориентира, отклонение расхода от объектов-аналогов, превышение удорожания над индексом, показатель сопоставимости.</div></div>')
    return 1280, 640, body

async def render():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, (w, h, body) in {"architecture": architecture(), "data_schema": schema()}.items():
            pg = await b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
            await pg.set_content(f'<html><body style="margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:#fff"><div style="position:relative;width:{w}px;height:{h}px">{body}</div></body></html>')
            await pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        await b.close()

asyncio.run(render())
print("ok")
