import json
import unittest
from unittest.mock import patch

from local_cleanup import LocalCleaner, is_safe_edit


class LocalCleanupTests(unittest.TestCase):
    def test_guard(self):
        self.assertTrue(is_safe_edit('嗯，我我想试一下 Wispr Flow。', '我想试一下 Wispr Flow。'))
        self.assertFalse(is_safe_edit('不要删那个文件。', '删那个文件。'))
        self.assertFalse(is_safe_edit('明天 8 点见。', '明天 9 点见。'))
        self.assertFalse(is_safe_edit('试试 sherpa-onnx。', '试试 Whisper。'))
        self.assertFalse(is_safe_edit('请告诉我怎么部署软件。', '可以使用如下步骤部署软件：'))
        self.assertFalse(is_safe_edit('嗯，我想试一下。', ''))
        self.assertFalse(is_safe_edit('保持原文。', '<think>保持原文。</think>'))
        self.assertFalse(is_safe_edit('嗯，我同意。', '我同意。'))
        self.assertFalse(is_safe_edit('嗯，I want to try Wispr Flow，呃，先不要换模型。', "I want to try Wispr Flow, first don't change the model."))

    def test_fail_open(self):
        cleaner = LocalCleaner()
        try:
            with patch.object(cleaner, 'ready', side_effect=OSError('unavailable')):
                self.assertEqual(cleaner.clean('不要换模型。').text, '不要换模型。')
            with patch.object(cleaner, 'ready'), patch.object(cleaner, 'request', return_value={}):
                self.assertEqual(cleaner.clean('保持原文。').text, '保持原文。')
            for text, reason in [('删那个文件。', 'stop'), ('不要删那个文件。', 'length')]:
                response = {'choices': [{'finish_reason': reason,
                    'message': {'content': json.dumps({'text': text})}}]}
                with patch.object(cleaner, 'ready'), patch.object(cleaner, 'request', return_value=response):
                    self.assertEqual(cleaner.clean('不要删那个文件。').text, '不要删那个文件。')
        finally:
            cleaner.close()

    def test_long_text_not_truncated(self):
        cleaner = LocalCleaner()
        try:
            text = '很长的文字。' * 400
            with patch.object(cleaner, 'ready') as ready:
                self.assertEqual(cleaner.clean(text).text, text)
                ready.assert_not_called()
        finally:
            cleaner.close()


if __name__ == '__main__':
    unittest.main()
