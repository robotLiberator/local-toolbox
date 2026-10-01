import asyncio
import unittest

from playwright.async_api import async_playwright

from uploader.bilibili_uploader.playwright_main import (
    BilibiliUploadNotStartedError,
    BilibiliVideo,
)


class BilibiliUploadStateTest(unittest.TestCase):
    def make_uploader(self):
        return BilibiliVideo(
            title="测试标题",
            file_path="dummy.mp4",
            tags=[],
            publish_date=0,
            account_file="dummy.json",
        )

    def test_waits_for_upload_complete_with_current_status_markup(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    """
                    <div id="video-up-app">
                      <div class="file-item-content-status-text">上传中 50% 当前速度：1MB/s</div>
                    </div>
                    <script>
                      setTimeout(() => {
                        document.querySelector('.file-item-content-status-text').textContent = '上传完成';
                      }, 100);
                    </script>
                    """
                )
                await self.make_uploader()._wait_upload_complete(
                    page,
                    startup_timeout_seconds=1,
                    complete_timeout_seconds=2,
                    poll_interval_seconds=0.05,
                    stable_ticks_required=2,
                )
                await browser.close()

        asyncio.run(run_case())

    def test_visible_uploading_status_wins_over_hidden_completed_text(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    """
                    <div id="video-up-app">
                      <div class="file-item-content-status-text">
                        已经上传：0.0MB/76.2MB 当前速度：0.0MB/s 剩余时间：&gt;1天 上传中...
                      </div>
                    </div>
                    <div style="display:none">上传完成</div>
                    """
                )
                state = await self.make_uploader()._read_upload_state(page)
                await browser.close()
                self.assertTrue(state["in_progress"])
                self.assertFalse(state["complete"])
                self.assertEqual(state["upload_percent"], 0)

        asyncio.run(run_case())

    def test_calculates_upload_percent_from_uploaded_megabytes(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    '<div class="file-item-content-status-text">已经上传：38.1MB/76.2MB 上传中...</div>'
                )
                state = await self.make_uploader()._read_upload_state(page)
                await browser.close()
                self.assertEqual(state["upload_percent"], 50)

        asyncio.run(run_case())

    def test_accepts_body_text_when_bilibili_removes_legacy_status_node(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    """
                    <div class="new-uploader-card">视频处理完成，上传完成</div>
                    <input placeholder="请输入稿件标题">
                    """
                )
                await self.make_uploader()._wait_upload_complete(
                    page,
                    startup_timeout_seconds=0.2,
                    complete_timeout_seconds=1,
                    poll_interval_seconds=0.05,
                    stable_ticks_required=2,
                )
                await browser.close()

        asyncio.run(run_case())

    def test_missing_upload_signal_raises_instead_of_continuing_to_cover(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content('<input type="file" accept=".mp4">')
                with self.assertRaises(BilibiliUploadNotStartedError):
                    await self.make_uploader()._wait_upload_complete(
                        page,
                        startup_timeout_seconds=0.12,
                        complete_timeout_seconds=1,
                        poll_interval_seconds=0.04,
                        stable_ticks_required=2,
                    )
                await browser.close()

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
