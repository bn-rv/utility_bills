import re
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class UtilityReading(BaseModel):
    """Модель для показаний счетчика"""
    previous: Decimal = Field(..., description="Предыдущие показания")
    current: Decimal = Field(..., description="Текущие показания")
    consumption: Decimal = Field(..., description="Расход")
    rate: Decimal = Field(..., description="Тариф")
    amount: Decimal = Field(..., description="Сумма к оплате")


class UtilityBill(BaseModel):
    """Модель для счета за коммунальные услуги"""
    cold_water: Optional[UtilityReading] = Field(..., description="хол_вода")
    hot_water: Optional[UtilityReading] = Field(..., description="гор_вода")
    water_disposal: Optional[UtilityReading] = Field(..., description="водоотведение")
    electricity: Optional[UtilityReading] = Field(..., description="электроэнергия")

    total: Decimal = Field(..., description="Общая сумма")
    date: datetime = Field(..., description="Дата счетчиков")


class TelegramBillParser:
    """Парсер для сообщений с показаниями счетчиков из Telegram"""

    def __init__(self):
        # Паттерны для извлечения данных (поддерживаем , и . как разделители)
        self.patterns = {
            'cold_water': r'Хол\.\s*вода:\s*Было\s*-\s*(\d+)\s*Стало\s*-\s*(\d+)\s*(\d+(?:[.,]\d+)?)\s*\*\s*(\d+(?:[.,]\d+)?)\s*=\s*(\d+(?:[.,]\d+)?)',
            'hot_water': r'Гор\.\s*вода:\s*Было\s*-\s*(\d+)\s*Стало\s*-\s*(\d+)\s*(\d+(?:[.,]\d+)?)\s*\*\s*(\d+(?:[.,]\d+)?)\s*=\s*(\d+(?:[.,]\d+)?)',
            'water_disposal': r'Водоотведение:\s*(\d+(?:[.,]\d+)?)\s*\*\s*(\d+(?:[.,]\d+)?)\s*=\s*(\d+(?:[.,]\d+)?)',
            'electricity': r'Электроэнергия:\s*Было\s*-\s*(\d+)\s*Стало\s*-\s*(\d+)\s*(\d+(?:[.,]\d+)?)\s*\*\s*(\d+(?:[.,]\d+)?)\s*=\s*(\d+(?:[.,]\d+)?)',
            'total': r'Итого:\s*(\d+(?:[.,]\d+)?)',
            'date': r'#счетчики\s*(\d{2}\.\d{2}\.\d{4})'
        }

    @staticmethod
    def _normalize_decimal(value_str: str) -> Decimal:
        """Нормализует строку с числом, заменяя запятую на точку и конвертируя в Decimal"""
        normalized = value_str.replace(',', '.')
        return Decimal(normalized)

    def parse_message(self, message: str) -> UtilityBill:
        """Парсит сообщение и возвращает объект UtilityBill"""

        # Очистка сообщения от лишних символов
        cleaned_message = re.sub(r'\s+', ' ', message.strip())

        # Извлечение данных
        data = {}

        # Парсинг холодной воды
        cold_match = re.search(self.patterns['cold_water'], cleaned_message, re.IGNORECASE)
        if cold_match:
            previous, current, consumption, rate, amount = [self._normalize_decimal(x) for x in cold_match.groups()]
            data['cold_water'] = UtilityReading(
                previous=previous,
                current=current,
                consumption=consumption,
                rate=rate,
                amount=amount
            )

        # Парсинг горячей воды
        hot_match = re.search(self.patterns['hot_water'], cleaned_message, re.IGNORECASE)
        if hot_match:
            previous, current, consumption, rate, amount = [self._normalize_decimal(x) for x in hot_match.groups()]
            data['hot_water'] = UtilityReading(
                previous=previous,
                current=current,
                consumption=consumption,
                rate=rate,
                amount=amount
            )

        # Парсинг водоотведения
        disposal_match = re.search(self.patterns['water_disposal'], cleaned_message, re.IGNORECASE)
        if disposal_match:
            consumption, rate, amount = [self._normalize_decimal(x) for x in disposal_match.groups()]
            # Для водоотведения берем сумму потребления холодной и горячей воды
            total_water_consumption = Decimal('0')
            if data.get('cold_water'):
                total_water_consumption += data['cold_water'].consumption
            if data.get('hot_water'):
                total_water_consumption += data['hot_water'].consumption

            data['water_disposal'] = UtilityReading(
                previous=Decimal('0'),  # Для водоотведения показания не ведутся
                current=total_water_consumption,
                consumption=consumption,
                rate=rate,
                amount=amount
            )

        # Парсинг электроэнергии
        elec_match = re.search(self.patterns['electricity'], cleaned_message, re.IGNORECASE)
        if elec_match:
            previous, current, consumption, rate, amount = [self._normalize_decimal(x) for x in elec_match.groups()]
            data['electricity'] = UtilityReading(
                previous=previous,
                current=current,
                consumption=consumption,
                rate=rate,
                amount=amount
            )

        # Парсинг общей суммы
        total_match = re.search(self.patterns['total'], cleaned_message, re.IGNORECASE)
        if not total_match:
            raise ValueError("Не найдена общая сумма в сообщении")
        data['total'] = self._normalize_decimal(total_match.group(1))

        # Парсинг даты
        date_match = re.search(self.patterns['date'], cleaned_message, re.IGNORECASE)
        if not date_match:
            raise ValueError("Не найдена дата в сообщении")

        date_str = date_match.group(1)
        data['date'] = datetime.strptime(date_str, '%d.%m.%Y')

        return UtilityBill(**data)


# Пример использования
# if __name__ == "__main__":
#     test_message_comma = """
#     Хол. вода:
#     Было - 579
#     Стало - 587
#
#     8 * 59,8 = 478
#
#     Гор. вода:
#     Было - 47
#     Стало - 49
#
#     2 * 272,14 = 544,28
#
#     Водоотведение:
#     10 * 45,91 = 459,1
#
#     Электроэнергия:
#     Было - 7984
#     Стало - 8108
#
#     124 * 6,99 = 866,76
#
#     Итого: 2348,14
#
#     #счетчики 22.06.2025
#     """
#
#     parser = TelegramBillParser()
#
#     # Тестируем с запятой как разделителем
#     try:
#         bill = parser.parse_message(test_message_comma)
#         from pprint import pprint
#         print("Парсинг прошел успешно!")
#         pprint(bill)
#
#         if bill.cold_water:
#             print(f"Холодная вода: {bill.cold_water.consumption} м³ × {bill.cold_water.rate} = {bill.cold_water.amount} руб.")
#
#         if bill.hot_water:
#             print(f"Горячая вода: {bill.hot_water.consumption} м³ × {bill.hot_water.rate} = {bill.hot_water.amount} руб.")
#
#         if bill.water_disposal:
#             print(f"Водоотведение: {bill.water_disposal.consumption} м³ × {bill.water_disposal.rate} = {bill.water_disposal.amount} руб.")
#
#         if bill.electricity:
#             print(f"Электроэнергия: {bill.electricity.consumption} кВт⋅ч × {bill.electricity.rate} = {bill.electricity.amount} руб.")
#
#     except Exception as e:
#         print(f"Ошибка парсинга: {e}")
