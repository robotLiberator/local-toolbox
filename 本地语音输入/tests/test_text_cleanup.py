import unittest

from text_cleanup import clean_stutters


class CleanupTests(unittest.TestCase):
    def test_stutters(self):
        examples = {
            "我我我想试一下。": "我想试一下。",
            "这个这个功能够用了。": "这个功能够用了。",
            "然后，然后，然后再复制。": "然后再复制。",
            "我们我们先试试那个那个模型。": "我们先试试那个模型。",
            "我，我想用这个，这个功能。": "我想用这个功能。",
        }
        for original, expected in examples.items():
            with self.subTest(original=original):
                self.assertEqual(clean_stutters(original), expected)
                self.assertEqual(clean_stutters(expected), expected)

    def test_preserve_meaning(self):
        examples = (
            "看看这个，慢慢来，想想再说。",
            "结结巴巴、开开心心、人人有份。",
            "非常非常好，真的真的很好。",
            "不不不，不要改。",
            "把那个文件给我。",
            "我。我明白了。这个！这个很重要。",
            "先复制，再复制。先复制，再复制。",
            "code code，123123，哈哈哈。",
            "", "   ",
        )
        for original in examples:
            with self.subTest(original=original):
                self.assertEqual(clean_stutters(original), original)


if __name__ == "__main__":
    unittest.main()
