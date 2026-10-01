import asyncio
import threading
import unittest
from unittest.mock import patch

import main
from myUtils import postVideo as post_video


class PublishProgressTest(unittest.TestCase):
    def tearDown(self):
        with main.PUBLISH_TASKS_LOCK:
            main.PUBLISH_TASKS.clear()
            main.PUBLISH_TASK_CANCEL_EVENTS.clear()

    def test_platform_progress_is_stored_in_task_state(self):
        task_id = main._create_publish_task_state(
            [{"type": 3}, {"type": 5}],
            dry_run=False,
        )

        main._update_publish_platform(task_id, 3, {
            "status": "running",
            "stage": "uploading",
            "progress": 37,
            "uploadPercent": 49,
            "message": "视频上传中 49%",
        })

        task = main._get_publish_task_state(task_id)
        douyin = next(item for item in task["platforms"] if item["type"] == 3)
        self.assertEqual(task["status"], "running")
        self.assertEqual(douyin["stage"], "uploading")
        self.assertEqual(douyin["progress"], 37)
        self.assertEqual(douyin["uploadPercent"], 49)
        self.assertIsNotNone(douyin["startedAt"])

    def test_worker_keeps_platform_failures_independent(self):
        task_id = main._create_publish_task_state(
            [{"type": 3}, {"type": 5}],
            dry_run=False,
        )

        def fake_publish(_data_list, dry_run, progress_callback, cancel_event):
            self.assertFalse(dry_run)
            self.assertFalse(cancel_event.is_set())
            progress_callback(3, {
                "status": "success",
                "stage": "success",
                "progress": 100,
                "message": "平台发布成功",
            })
            progress_callback(5, {
                "status": "failed",
                "stage": "failed",
                "progress": 62,
                "message": "封面入口未找到",
            })
            return [
                {"type": 3, "ok": True, "message": None},
                {"type": 5, "ok": False, "message": "封面入口未找到"},
            ]

        with patch.object(main, "post_video_batch_tabs", side_effect=fake_publish):
            main._run_publish_task(task_id, [{"type": 3}, {"type": 5}], False)

        task = main._get_publish_task_state(task_id)
        self.assertEqual(task["status"], "partial_failure")
        self.assertIsNotNone(task["finishedAt"])
        states = {item["type"]: item["status"] for item in task["platforms"]}
        self.assertEqual(states, {3: "success", 5: "failed"})

    def test_cancel_endpoint_marks_task_as_cancelling_and_sets_event(self):
        task_id = main._create_publish_task_state([{"type": 3}], dry_run=False)
        client = main.app.test_client()

        response = client.post(f"/publishTasks/{task_id}/cancel")

        body = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["data"]["status"], "cancelling")
        self.assertEqual(body["data"]["platforms"][0]["status"], "cancelling")
        self.assertTrue(main._get_publish_task_cancel_event(task_id).is_set())

    def test_cancelled_worker_finishes_as_cancelled_not_failed(self):
        task_id = main._create_publish_task_state([{"type": 3}], dry_run=False)

        def fake_publish(_data_list, dry_run, progress_callback, cancel_event):
            progress_callback(3, {
                "status": "running",
                "stage": "uploading",
                "progress": 32,
                "message": "正在上传视频",
            })
            cancel_event.set()
            raise main.PublishTaskCancelled()

        with patch.object(main, "post_video_batch_tabs", side_effect=fake_publish):
            main._run_publish_task(task_id, [{"type": 3}], False)

        task = main._get_publish_task_state(task_id)
        self.assertEqual(task["status"], "cancelled")
        self.assertEqual(task["platforms"][0]["status"], "cancelled")
        self.assertEqual(task["platforms"][0]["lastStage"], "uploading")

    def test_create_task_endpoint_returns_before_worker_finishes(self):
        client = main.app.test_client()
        payload = [{"type": 3, "fileList": ["video.mp4"], "accountList": ["account.json"]}]

        with patch.object(main, "_validate_publish_payload", return_value=[]), \
             patch.object(main, "_validate_publish_accounts_before_run", return_value=[]), \
             patch.object(main.threading, "Thread") as thread_class:
            response = client.post("/publishTasks", json=payload)

        body = response.get_json()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(body["code"], 202)
        self.assertEqual(body["data"]["status"], "queued")
        thread_class.return_value.start.assert_called_once_with()

    def test_cancel_interrupts_platform_loop_that_catches_browser_errors(self):
        class FakePlaywrightManager:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakeBrowser:
            connected = True

            def is_connected(self):
                return self.connected

            async def close(self):
                self.connected = False

        class FakeContext:
            async def close(self):
                return None

        class RetryForeverApp:
            async def upload(self, _playwright):
                while True:
                    try:
                        await asyncio.sleep(10)
                    except BaseException:
                        await asyncio.sleep(10)

        async def run_case():
            cancel_event = threading.Event()
            browser = FakeBrowser()
            context = FakeContext()

            async def fake_launch(_playwright):
                return browser

            async def fake_new_context(_browser, storage_state):
                return context

            async def fake_set_init_script(current_context):
                return current_context

            async def fake_prepare_pages(_context, _jobs, progress_callback=None, cancel_event=None):
                return [object()]

            with patch.object(post_video, "async_playwright", return_value=FakePlaywrightManager()), \
                 patch.object(post_video, "launch_publish_browser", side_effect=fake_launch), \
                 patch.object(post_video, "new_publish_context", side_effect=fake_new_context), \
                 patch.object(post_video, "set_init_script", side_effect=fake_set_init_script), \
                 patch.object(post_video, "_prepare_batch_pages", side_effect=fake_prepare_pages), \
                 patch.object(post_video, "_make_platform_app", return_value=RetryForeverApp()):
                running = asyncio.create_task(post_video._post_video_batch_tabs_async(
                    [{"type": 3, "fileList": ["video.mp4"], "accountList": ["account.json"]}],
                    dry_run=False,
                    cancel_event=cancel_event,
                ))
                await asyncio.sleep(0.05)
                cancel_event.set()
                with self.assertRaises(post_video.PublishTaskCancelled):
                    await asyncio.wait_for(running, timeout=2)

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
