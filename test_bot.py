import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import allowed_ids, handle_message, has_access, text_parts


def make_update(user_id=1001, chat_type="private", document=None):
    return SimpleNamespace(
        effective_chat=SimpleNamespace(type=chat_type),
        effective_user=SimpleNamespace(id=user_id),
        effective_message=SimpleNamespace(document=document, reply_text=AsyncMock()),
    )


class AccessTests(unittest.TestCase):
    def test_allowlist(self):
        ids = allowed_ids("1001, 1002")
        self.assertTrue(has_access(make_update(), ids))
        self.assertTrue(has_access(make_update(1002), ids))
        self.assertFalse(has_access(make_update(123), ids))
        self.assertFalse(has_access(make_update(chat_type="group"), ids))
        self.assertFalse(has_access(make_update(), allowed_ids("")))

    def test_text_split(self):
        text = "Кампания: 123\n" * 1000
        parts = list(text_parts(text))
        self.assertTrue(all(len(part) <= 1800 for part in parts))
        self.assertEqual("\n".join(parts).splitlines(), text.splitlines())


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_denied_before_download(self):
        document = SimpleNamespace(get_file=AsyncMock())
        update = make_update(123, document=document)
        context = SimpleNamespace(bot_data={"allowed_ids": allowed_ids("1001")})
        await handle_message(update, context)
        document.get_file.assert_not_called()

    async def test_file_to_text(self):
        data = '<meta charset="utf-8"><table><tr><th>UTM Campaign</th></tr><tr><td>test</td></tr></table>'.encode()
        remote = SimpleNamespace(download_as_bytearray=AsyncMock(return_value=bytearray(data)))
        document = SimpleNamespace(file_name="leads.xls", file_size=len(data), get_file=AsyncMock(return_value=remote))
        update = make_update(document=document)
        context = SimpleNamespace(bot_data={"allowed_ids": allowed_ids("1001")})
        await handle_message(update, context)
        result = update.effective_message.reply_text.call_args.args[0]
        self.assertIn("test: 1", result)
        self.assertIn("Всего строк: 1", result)


if __name__ == "__main__":
    unittest.main()
