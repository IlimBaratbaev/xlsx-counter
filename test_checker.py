import unittest
from collections import Counter
from io import BytesIO

from checker import Result, analyze, campaign_values


class CheckerTests(unittest.TestCase):
    def test_project_totals_and_campaign_list(self):
        result = Result(counts=Counter({
            "Айкол локации": 44, "AIKOL_sale": 3, "Айколь планировки": 2,
            "Арча школы": 17, "archa-banks": 5,
            "enesai_as_archa_july23_07_leads": 8, "НеАйкол": 2,
            "Aikology": 1, "Арчабанк": 1,
        }), total=86, missing=1, ambiguous=2)
        text = result.text()
        self.assertIn("Айкол локации: 44", text)
        self.assertIn("• Айкол / Aikol: 49", text)
        self.assertIn("• Арча / Archa: 22", text)
        self.assertIn("Итого: 71 лидов Айкол / Арча.", text)
        self.assertIn("• Пересечений: 0", text)
        self.assertIn("Остальные 15 лидов:", text)
        self.assertIn("• enesai_as_archa_july23_07_leads: 8", text)
        self.assertIn("• Без utm_campaign: 1", text)
        self.assertIn("• Несколько разных кампаний: 2", text)
        self.assertLess(text.index("Айкол локации: 44"), text.index("Итого: 71"))

    def test_project_totals_empty_and_no_other(self):
        self.assertIn("Остальные 0 лидов:\n• Нет", Result().text())
        text = Result(counts=Counter({"Aikol": 1, "Арча": 1}), total=2).text()
        self.assertIn("Итого: 2 лидов Айкол / Арча.", text)
        self.assertIn("Остальные 0 лидов:\n• Нет", text)

    def test_extract(self):
        self.assertEqual(campaign_values("utm_campaign:\n enesai_leads utm_content: video"), {"enesai_leads"})
        self.assertEqual(campaign_values("?utm_campaign=summer%20sale&utm_source=fb"), {"summer sale"})
        self.assertEqual(campaign_values("utm_campaign: utm_content: video"), set())
        self.assertEqual(campaign_values("utm_campaign: a utm_campaign: a"), {"a"})

    def test_bitrix_html(self):
        data = '''<meta charset="utf-8"><table><tr><th>ID</th><th>Комментарий</th></tr>
        <tr><td>1</td><td>utm_campaign: a utm_content: v</td></tr>
        <tr><td>2</td><td>utm_campaign: a</td></tr>
        <tr><td>3</td><td></td></tr>
        <tr><td>4</td><td>utm_campaign: a utm_campaign: b</td></tr></table>'''.encode()
        result = analyze(data)
        self.assertEqual(dict(result.counts), {"a": 2})
        self.assertEqual((result.total, result.missing, result.ambiguous), (4, 1, 1))
        self.assertIn("Всего строк: 4", result.text())

    def test_xlsx_multiple_sheets(self):
        from openpyxl import Workbook
        book = Workbook()
        book.active.append(["Описание"])
        sheet = book.create_sheet("Лиды")
        sheet.append(["ID", "Комментарии"])
        sheet.append([1, "utm_campaign: abc utm_source: fb"])
        sheet.append([2, None])
        sheet.append([None, None])
        output = BytesIO()
        book.save(output)
        result = analyze(output.getvalue())
        self.assertEqual((result.total, result.missing), (2, 1))
        self.assertEqual(dict(result.counts), {"abc": 1})

    def test_missing_header(self):
        with self.assertRaisesRegex(ValueError, "не найден"):
            analyze(b"<table><tr><th>ID</th></tr><tr><td>1</td></tr></table>")

    def test_fallback_and_priority(self):
        data = '''<meta charset="utf-8"><table>
        <tr><th>ID</th><th>Комментарий</th><th>UTM Campaign</th><th>Другое</th></tr>
        <tr><td>1</td><td>utm_campaign: comment</td><td>column</td><td>utm_campaign: other</td></tr>
        <tr><td>2</td><td></td><td>Кампания с пробелами</td><td>utm_campaign: other</td></tr>
        <tr><td>3</td><td></td><td></td><td>utm_campaign: other</td></tr>
        <tr><td>4</td><td>utm_campaign: a utm_campaign: b</td><td></td><td></td></tr>
        <tr><td>5</td><td>utm_campaign: comment</td><td></td><td>utm_campaign: other</td></tr>
        </table>'''.encode()
        result = analyze(data)
        self.assertEqual(dict(result.counts), {"column": 1, "Кампания с пробелами": 1, "other": 1, "comment": 1})
        self.assertEqual(dict(result.sources), {"column": 2, "other": 1, "comment": 1})
        self.assertEqual((result.total, result.missing, result.ambiguous), (5, 0, 1))

    def test_campaign_column_without_comment(self):
        result = analyze('<meta charset="utf-8"><table><tr><th>UTM Campaign</th></tr><tr><td>abc</td></tr></table>'.encode())
        self.assertEqual(dict(result.counts), {"abc": 1})


if __name__ == "__main__":
    unittest.main()
