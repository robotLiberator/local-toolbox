import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import ANY, AsyncMock, patch

from playwright.async_api import async_playwright

from uploader.bilibili_uploader.playwright_main import BilibiliVideo
from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo
from myUtils.postVideo import _make_platform_app


class CoverEditorSelectorTest(unittest.TestCase):
    def test_bilibili_opens_current_add_cover_entry(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    """
                    <div class="cover-slot">
                      <div class="cover-empty" onclick="document.querySelector('.cover-editor').style.display='block'">
                        <div class="cover-empty-pill"><span>添加封面</span></div>
                      </div>
                    </div>
                    <div class="cover-editor bcc-dialog__wrap-mask" style="display:none">封面制作</div>
                    """
                )
                uploader = BilibiliVideo(
                    title="测试",
                    file_path="dummy.mp4",
                    tags=[],
                    publish_date=datetime.now(),
                    account_file=Path("dummy.json"),
                )
                await uploader._open_cover_dialog(page)
                visible = await page.locator(".cover-editor").is_visible()
                await browser.close()
                self.assertTrue(visible)

        asyncio.run(run_case())

    def test_bilibili_reselects_same_cover_file_for_second_ratio(self):
        async def run_case():
            with tempfile.TemporaryDirectory() as temp_dir:
                cover_path = Path(temp_dir) / "same-cover.png"
                cover_path.write_bytes(b"same cover bytes")

                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.set_content(
                        """
                        <div class="cover-editor bcc-dialog__wrap-mask">
                          <input type="file" accept="image/png,image/jpeg">
                        </div>
                        <script>
                          window.coverChanges = [];
                          document.querySelector('input').addEventListener('change', event => {
                            window.coverChanges.push(event.target.files[0]?.name || '');
                          });
                        </script>
                        """
                    )
                    uploader = BilibiliVideo(
                        title="测试",
                        file_path="dummy.mp4",
                        tags=[],
                        publish_date=datetime.now(),
                        account_file=Path("dummy.json"),
                    )

                    await uploader._upload_cover_file(page, str(cover_path))
                    await uploader._upload_cover_file(page, str(cover_path))
                    changes = await page.evaluate("window.coverChanges")
                    await browser.close()

                self.assertEqual(changes.count("same-cover.png"), 2)
                self.assertIn("", changes)

        asyncio.run(run_case())

    def test_bilibili_selects_sixteen_by_nine_cover_editor(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    """
                    <div class="cover-editor bcc-dialog__wrap-mask">
                      <div class="cover-editor-panel-canvas">
                        <div class="cover-editor-panel-canvas-title"
                             onclick="window.selectedRatio='4:3'">首页推荐封面（4:3）</div>
                        <div class="cover-editor-panel-canvas-title"
                             onclick="window.selectedRatio='16:9'">个人空间封面（16:9）</div>
                      </div>
                    </div>
                    """
                )
                uploader = BilibiliVideo(
                    title="测试",
                    file_path="dummy.mp4",
                    tags=[],
                    publish_date=datetime.now(),
                    account_file=Path("dummy.json"),
                )

                await uploader._select_cover_ratio(page, "16:9")
                selected_ratio = await page.evaluate("window.selectedRatio")
                await browser.close()

                self.assertEqual(selected_ratio, "16:9")

        asyncio.run(run_case())

    def test_bilibili_platform_app_receives_both_cover_ratios(self):
        app = _make_platform_app(
            {
                "type": 5,
                "title": "测试",
                "coverPaths": {
                    "4:3": "four-three.png",
                    "16:9": "sixteen-nine.png",
                },
            },
            "dummy.mp4",
            0,
            "dummy.json",
        )

        self.assertTrue(str(app.thumbnail_paths["4:3"]).endswith("four-three.png"))
        self.assertTrue(str(app.thumbnail_paths["16:9"]).endswith("sixteen-nine.png"))

    def test_xhs_opens_current_column_cover_operator(self):
        async def run_case():
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(
                    """
                    <div class="cover-plugin-preview">
                      <div class="default column">设置封面</div>
                      <div class="operator pointer" style="pointer-events:none;opacity:0"
                           ><span class="cover-edit-entry-text"
                           onclick="document.querySelector('.d-modal').style.display='block'">编辑封面</span></div>
                    </div>
                    <div class="d-modal" role="dialog" style="display:none">
                      <div>设置封面</div><button>裁剪</button><button>上传</button>
                      <input type="file" accept="image/png,image/jpeg">
                    </div>
                    """
                )
                uploader = XiaoHongShuVideo(
                    title="测试",
                    file_path="dummy.mp4",
                    tags=[],
                    publish_date=0,
                    account_file="dummy.json",
                )
                card = await uploader.find_xhs_cover_card(page)
                opened = await uploader.open_xhs_cover_editor(page, card)
                await browser.close()
                self.assertTrue(opened)

        asyncio.run(run_case())

    def test_xhs_always_selects_horizontal_four_by_three_cover(self):
        async def run_case():
            uploader = XiaoHongShuVideo(
                title="测试",
                file_path="dummy.mp4",
                tags=[],
                publish_date=0,
                account_file="dummy.json",
            )
            with patch.object(
                uploader,
                "read_xhs_cover_editor_ratio",
                new=AsyncMock(return_value="3:4"),
            ), patch.object(
                uploader,
                "select_xhs_cover_editor_ratio",
                new=AsyncMock(return_value="4:3"),
            ) as select_ratio:
                selected = await uploader.choose_xhs_cover_path_for_editor(
                    object(),
                    "vertical.jpg",
                    {"3:4": "vertical.jpg", "4:3": "horizontal.jpg"},
                )

            self.assertEqual(selected, "horizontal.jpg")
            select_ratio.assert_awaited_once_with(ANY, "4:3")

        asyncio.run(run_case())

    def test_xhs_platform_app_receives_only_four_by_three_primary_cover(self):
        app = _make_platform_app(
            {
                "type": 1,
                "title": "测试",
                "coverPath": "vertical.jpg",
                "coverPaths": {
                    "3:4": "vertical.jpg",
                    "4:3": "horizontal.jpg",
                },
            },
            "dummy.mp4",
            0,
            "dummy.json",
        )

        self.assertTrue(str(app.thumbnail_path).endswith("horizontal.jpg"))


if __name__ == "__main__":
    unittest.main()
