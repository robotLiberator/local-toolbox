import json
import unittest
from pathlib import Path
from unittest.mock import patch

from terminology import correct_terms

DATA = json.loads((Path(__file__).resolve().parent.parent / 'terminology.json').read_text(encoding='utf-8'))


class TerminologyTests(unittest.TestCase):
    def fix(self, text):
        return correct_terms(text, DATA)

    def test_github_in_technical_context(self):
        self.assertEqual(self.fix('把源码上传到 get up。'), '把源码上传到 GitHub。')
        self.assertEqual(self.fix('get up 上的开源模型。'), 'GitHub 上的开源模型。')
        self.assertEqual(self.fix('不要上传到 GET UP 仓库。'), '不要上传到 GitHub 仓库。')

    def test_regular_english_unchanged(self):
        for text in ('I get up at 8.', 'You should get up early.', 'get up', '这个衣服的 getup 不错。', '上传代码。I get up at 8.', '模型例句是 I get up at 8.'):
            self.assertEqual(self.fix(text), text)

    def test_common_computer_terms(self):
        self.assertEqual(self.fix('用 chat g p t 和 a p i，g p u 跑 python。'), '用 ChatGPT 和 API，GPU 跑 Python。')
        self.assertEqual(self.fix('github、git hub、huggingface 和 v s code。'), 'GitHub、GitHub、Hugging Face 和 VS Code。')

    def test_boundaries(self):
        self.assertEqual(self.fix('chair fair xgithub githubber apical my_python'), 'chair fair xgithub githubber apical my_python')

    def test_negation_numbers_and_mixed_language(self):
        self.assertEqual(self.fix('不要改 3 个 API，I get up at 8. 明天见。'), '不要改 3 个 API，I get up at 8. 明天见。')

    def test_malformed_dictionary_fails_open(self):
        for data in ({}, {'terms': [None], 'technical_context': []}, {'terms': [{'canonical':'X', 'aliases':'github'}], 'technical_context': []}):
            self.assertEqual(correct_terms('github', data), 'github')
        with patch('terminology.dictionary_file', side_effect=OSError('missing')):
            self.assertEqual(correct_terms('github'), 'github')

    def test_no_cascade(self):
        data = {'technical_context': [], 'terms': [{'canonical':'B', 'aliases':['a']}, {'canonical':'C', 'aliases':['B']}]}
        self.assertEqual(correct_terms('a', data), 'B')


if __name__ == '__main__':
    unittest.main()
