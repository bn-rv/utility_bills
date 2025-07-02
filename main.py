from __future__ import annotations

import os
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from pydantic import BaseModel, Field, ValidationError
from telegram import Update
from telegram.ext import (ApplicationBuilder, ContextTypes, MessageHandler,
                          filters)

from parser_old_bill import TelegramBillParser

__all__ = ["main"]


class InputData(BaseModel):
    """Новые показания + возможные пользовательские тарифы."""

    cw: Decimal = Field(..., alias="cold_water")
    hw: Decimal = Field(..., alias="hot_water")
    el: Decimal = Field(..., alias="electricity")

    cw_rate: Optional[Decimal] = None
    hw_rate: Optional[Decimal] = None
    wd_rate: Optional[Decimal] = None
    el_rate: Optional[Decimal] = None

    model_config = {
        "extra": "forbid",
        "populate_by_name": True,
        "str_strip_whitespace": True,
    }


def _round(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), ROUND_HALF_UP)


def _parse_input(text: str) -> InputData:
    """Парсит строку команды после .meter и возвращает InputData."""

    payload = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) == 2 else ""

    # 1. Попробуем формат key=value (включая *_rate)
    if "=" in payload:
        pairs = re.findall(r"(\w+?)\s*=\s*([0-9]+(?:[.,][0-9]+)?)", payload, flags=re.I)
        if pairs:
            data = {
                k.lower(): Decimal(v.replace(",", "."))
                for k, v in pairs
            }
            # Проверим, есть ли хотя бы cw/hw/el
            if {"cw", "hw", "el"}.issubset(data.keys()):
                return InputData.model_validate(data)

    # 2. Формат три числа подряд + опциональные rate после них через key=value
    nums = re.findall(r"\d+(?:[.,]\d+)?", payload)
    if len(nums) >= 3:
        cw, hw, el = (Decimal(n.replace(",", ".")) for n in nums[:3])
        rest_pairs = re.findall(r"(\w+_rate)\s*=\s*([0-9]+(?:[.,][0-9]+)?)", payload, flags=re.I)
        rates = {k.lower(): Decimal(v.replace(",", ".")) for k, v in rest_pairs}
        return InputData(cw=cw, hw=hw, el=el, **rates)

    raise ValueError(
        "Не смог распознать команду. Форматы: 'cw=587 hw=49 el=8108 hw_rate=275' или '587 49 8108'.",
    )


def _get_rate(override: Optional[Decimal], fallback) -> Decimal:  # noqa: ANN001
    """Если пользователь дал rate — берём его, иначе старый из сообщения."""
    if override is not None:
        return override
    if hasattr(fallback, "rate") and fallback.rate is not None:
        return Decimal(str(fallback.rate))
    raise AttributeError("Отсутствует тариф (rate) в старом сообщении, и он не указан в команде.")


def _build_message(old_values, inp: InputData) -> str:  # noqa: ANN001
    """Собираем финальное сообщение, используя приоритет пользовательских тарифов."""

    # Тарифы
    cw_rate = _get_rate(inp.cw_rate, old_values.cold_water)
    hw_rate = _get_rate(inp.hw_rate, old_values.hot_water)
    el_rate = _get_rate(inp.el_rate, old_values.electricity)

    wd_reading = getattr(old_values, "water_disposal", None)
    wd_rate = _get_rate(inp.wd_rate, wd_reading) if wd_reading else (
        inp.wd_rate if inp.wd_rate is not None else Decimal("0")
    )

    # Расходы
    cw_cons = inp.cw - old_values.cold_water.current
    hw_cons = inp.hw - old_values.hot_water.current
    wd_cons = cw_cons + hw_cons
    el_cons = inp.el - old_values.electricity.current

    cw_amt = _round(cw_cons * cw_rate)
    hw_amt = _round(hw_cons * hw_rate)
    wd_amt = _round(wd_cons * wd_rate)
    el_amt = _round(el_cons * el_rate)
    total = _round(cw_amt + hw_amt + wd_amt + el_amt)

    date_str = datetime.now().strftime("%d.%m.%Y")

    return (
        f"Хол. вода:\nБыло - {old_values.cold_water.current}\nСтало - {inp.cw}\n\n"
        f"{cw_cons} * {cw_rate} = {cw_amt}\n\n"
        f"Гор. вода:\nБыло - {old_values.hot_water.current}\nСтало - {inp.hw}\n\n"
        f"{hw_cons} * {hw_rate} = {hw_amt}\n\n"
        f"Водоотведение:\n{wd_cons} * {wd_rate} = {wd_amt}\n\n"
        f"Электроэнергия:\nБыло - {old_values.electricity.current}\nСтало - {inp.el}\n\n"
        f"{el_cons} * {el_rate} = {el_amt}\n\n"
        f"Итого: {total}\n\n"
        f"#счетчики {date_str}"
    )


async def calc_bill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa: D401
    """.meter должен быть reply к сообщению со старыми показаниями."""
    if not update.message or not update.message.reply_to_message:
        await update.message.reply_text("Нужно ответить на сообщение со старыми показаниями.")
        return

    # Новые данные
    try:
        inp = _parse_input(update.message.text or "")
    except (ValueError, ValidationError) as err:
        await update.message.reply_text(str(err))
        return

    # Старые данные + тарифы
    old_text = update.message.reply_to_message.text or ""
    try:
        old_vals = TelegramBillParser().parse_message(old_text)
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"Не удалось разобрать старые показания: {exc}")
        return

    # Посчитаем
    try:
        result_msg = _build_message(old_vals, inp)
    except AttributeError as exc:  # нет rate
        await update.message.reply_text(str(exc))
        return

    await update.message.reply_text(result_msg)

# ──────────────────────────── Bootstrap ─────────────────────────────────

def main() -> None:  # noqa: D401
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Set BOT_TOKEN env var")

    app = (
        ApplicationBuilder()
        .token(token)
        .build()
    )

    pattern = re.compile(r"^[/.]?meter", flags=re.I)
    app.add_handler(MessageHandler(filters.Regex(pattern), calc_bill))

    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
