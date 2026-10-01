import asyncio
import unittest

from playwright.async_api import async_playwright

from uploader.douyin_uploader.main import DouYinVideo
from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo
from myUtils.postVideo import _make_platform_app


class PlatformTitleFieldsTest(unittest.TestCase):
    def test_bilibili_uses_shared_description(self):
        uploader = _make_platform_app(
            {
                "type": 5,
                "title": "统一标题",
                "description": "三个平台共用的作品文案",
                "tags": [],
            },
            "dummy.mp4",
            0,
            "dummy.json",
        )

        self.assertEqual(uploader.desc, "三个平台共用的作品文案")

    def test_douyin_title_and_description_are_filled_separately(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    """
                    <input type="text" placeholder="请输入作品标题">
                    <div class="zone-container" contenteditable="true"></div>
                    """
                )
                uploader = DouYinVideo(
                    title="统一标题",
                    description="独立作品文案",
                    file_path="dummy.mp4",
                    tags=[],
                    publish_date=0,
                    account_file="dummy.json",
                )

                await uploader.fill_platform_title(page)
                await uploader.fill_description_and_topics(page)

                title = await page.locator("input").input_value()
                description = await page.locator(".zone-container").inner_text()
                await browser.close()
                self.assertEqual(title, "统一标题")
                self.assertEqual(description, "独立作品文案")

        asyncio.run(run_case())

    def test_xiaohongshu_title_and_description_are_filled_separately(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    """
                    <input class="d-text" type="text" placeholder="填写标题会有更多赞哦">
                    <div class="tiptap ProseMirror" contenteditable="true"></div>
                    """
                )
                uploader = XiaoHongShuVideo(
                    title="统一标题",
                    description="独立作品文案",
                    file_path="dummy.mp4",
                    tags=[],
                    publish_date=0,
                    account_file="dummy.json",
                )

                await uploader.fill_platform_title(page)
                await uploader.fill_description(page)

                title = await page.locator("input").input_value()
                description = await page.locator(".tiptap").inner_text()
                await browser.close()
                self.assertEqual(title, "统一标题")
                self.assertEqual(description, "独立作品文案")

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
