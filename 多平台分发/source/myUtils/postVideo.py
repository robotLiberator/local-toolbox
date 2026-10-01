import asyncio
import json
from pathlib import Path

from conf import BASE_DIR
from PIL import Image
from playwright.async_api import async_playwright
from uploader.douyin_uploader.main import DouYinVideo
from uploader.ks_uploader.main import KSVideo
from uploader.tencent_uploader.main import TencentVideo
from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo
from uploader.bilibili_uploader.playwright_main import BilibiliVideo
from utils.base_social_media import launch_publish_browser, new_publish_context, reveal_page_window, set_init_script
from utils.constant import TencentZoneTypes
from utils.files_times import generate_schedule_time_next_day
from utils.publish_limits import KUAISHOU_TAG_COUNT, get_publish_tag_limit, normalize_publish_tags


class PublishTaskCancelled(Exception):
    """Raised when a running multi-platform publish task is stopped by the user."""


def _raise_if_publish_cancelled(cancel_event):
    if cancel_event and cancel_event.is_set():
        raise PublishTaskCancelled("发布任务已由用户停止")


def _resolve_video_file_path(file_name):
    return str(Path(BASE_DIR / "videoFile" / file_name)) if file_name else None


def _prepare_cover_upload_path(path):
    if not path:
        return None
    source = Path(path)
    if source.suffix.lower() in {".jpg", ".jpeg"}:
        return str(source)

    output_dir = Path(BASE_DIR / "videoFile" / ".prepared_covers")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{source.stem}.jpg"
    if output.exists() and output.stat().st_mtime >= source.stat().st_mtime:
        return str(output)

    with Image.open(source) as image:
        if image.mode in ("RGBA", "LA"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.getchannel("A"))
            background.save(output, "JPEG", quality=95)
        else:
            image.convert("RGB").save(output, "JPEG", quality=95)
    return str(output)


def _resolve_cover_file_path(file_name, prepare=False):
    path = _resolve_video_file_path(file_name)
    return _prepare_cover_upload_path(path) if prepare and path else path


def _resolve_cover_paths(cover_paths, prepare=False):
    if not isinstance(cover_paths, dict):
        return {}
    return {
        str(ratio): _resolve_cover_file_path(file_name, prepare=prepare)
        for ratio, file_name in cover_paths.items()
        if file_name
    }


def _merge_storage_states(account_files):
    merged_cookies = {}
    merged_origins = {}
    for account_file in account_files:
        storage_path = Path(account_file)
        if not storage_path.is_absolute():
            storage_path = Path(BASE_DIR / "cookiesFile" / storage_path)
        if not storage_path.exists():
            continue
        try:
            state = json.loads(storage_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"read account state failed file={account_file} err={e}")
            continue
        for cookie in state.get("cookies", []):
            cookie_key = (cookie.get("name"), cookie.get("domain"), cookie.get("path"))
            merged_cookies[cookie_key] = cookie
        for origin_state in state.get("origins", []):
            origin = origin_state.get("origin")
            if origin:
                merged_origins[origin] = origin_state
    return {
        "cookies": list(merged_cookies.values()),
        "origins": list(merged_origins.values()),
    }


def _build_publish_datetimes(file_count, enable_timer, videos_per_day, daily_times, start_days, jitter_minutes, schedule_time=None):
    if enable_timer and schedule_time:
        return [schedule_time for _ in range(file_count)]
    if enable_timer:
        videos_per_day = int(videos_per_day or 1)
        start_days = int(start_days or 0)
        jitter_minutes = int(jitter_minutes or 0)
        schedules = generate_schedule_time_next_day(
            file_count,
            videos_per_day,
            daily_times,
            start_days=start_days,
            jitter_minutes=jitter_minutes,
        )
        print(
            "[schedule] generated:",
            [schedule.strftime("%Y-%m-%d %H:%M") for schedule in schedules],
            f"videos_per_day={videos_per_day}",
            f"daily_times={daily_times}",
            f"start_days={start_days}",
            f"jitter={jitter_minutes}",
        )
        return schedules
    return [0 for _ in range(file_count)]


def _emit_publish_progress(progress_callback, platform_type, **event):
    if not progress_callback:
        return
    try:
        progress_callback(int(platform_type), event)
    except Exception as e:
        print(f"publish progress callback failed type={platform_type}: {e}")


def _make_platform_app(data, file_path, publish_datetime, cookie_path, dry_run=True, progress_callback=None):
    platform_type = int(data.get("type"))
    title = data.get("title") or data.get("biliTitle") or ""
    description = data.get("description")
    content_text = title if description is None else description
    tags = normalize_publish_tags(data.get("tags"), max_count=get_publish_tag_limit(platform_type))
    category = data.get("category")
    if category == 0:
        category = None
    cover_path = data.get("coverPath")
    cover_paths = data.get("coverPaths") if isinstance(data.get("coverPaths"), dict) else {}

    if platform_type == 1:
        thumbs = _resolve_cover_paths(cover_paths)
        # 小红书固定使用 4:3 横版封面，不再回退到 3:4 竖版或未知比例封面。
        thumb = thumbs.get("4:3")
        app = XiaoHongShuVideo(title, file_path, tags, publish_datetime, cookie_path, thumbnail_path=thumb, thumbnail_paths=thumbs, dry_run=dry_run, description=description)
        app.progress_callback = progress_callback
        return app
    if platform_type == 2:
        thumb = _resolve_video_file_path(cover_path)
        thumbs = _resolve_cover_paths(cover_paths)
        app = TencentVideo(content_text, file_path, tags, publish_datetime, cookie_path, category, thumbnail_path=thumb, thumbnail_paths=thumbs, dry_run=dry_run)
        app.progress_callback = progress_callback
        return app
    if platform_type == 3:
        thumb = _resolve_cover_file_path(cover_path, prepare=True)
        thumbs = _resolve_cover_paths(cover_paths, prepare=True)
        app = DouYinVideo(title, file_path, tags, publish_datetime, cookie_path, category=category, thumbnail_path=thumb, thumbnail_paths=thumbs, dry_run=dry_run, description=description)
        app.progress_callback = progress_callback
        return app
    if platform_type == 4:
        thumbs = _resolve_cover_paths(cover_paths)
        thumb = thumbs.get("3:4") or thumbs.get("4:3") or _resolve_video_file_path(cover_path)
        app = KSVideo(content_text, file_path, tags, publish_datetime, cookie_path, thumbnail_path=thumb, thumbnail_paths=thumbs, dry_run=dry_run)
        app.progress_callback = progress_callback
        return app
    if platform_type == 5:
        thumbs = _resolve_cover_paths(cover_paths)
        bili_cover_path = thumbs.get("16:9") or thumbs.get("4:3") or _resolve_video_file_path(cover_path)
        app = BilibiliVideo(
            title,
            file_path,
            tags,
            publish_datetime,
            cookie_path,
            thumbnail_path=bili_cover_path,
            thumbnail_paths=thumbs,
            desc=data.get("biliDesc") or description,
            bili_type=data.get("biliType"),
            partition=data.get("biliPartition"),
            dry_run=dry_run,
        )
        app.progress_callback = progress_callback
        return app
    raise ValueError(f"unsupported platform: {platform_type}")


def _platform_publish_url(platform_type):
    return {
        1: "https://creator.xiaohongshu.com/publish/publish?from=homepage&target=video",
        2: "https://channels.weixin.qq.com/platform/post/create",
        3: "https://creator.douyin.com/creator-micro/content/post/video?enter_from=publish_page",
        4: "https://cp.kuaishou.com/article/publish/video",
        5: "https://member.bilibili.com/platform/upload/video/frame?page_from=creative_home_top_upload",
    }.get(platform_type)


async def _prepare_batch_pages(context, jobs, progress_callback=None, cancel_event=None):
    pages = []
    for job in jobs:
        _raise_if_publish_cancelled(cancel_event)
        page = await context.new_page()
        pages.append(page)
        url = _platform_publish_url(job["platform_type"])
        if not url:
            continue
        _emit_publish_progress(
            progress_callback,
            job["platform_type"],
            stage="opening",
            status="running",
            progress=5,
            message="正在打开平台发布页",
        )
        try:
            await page.goto(url, wait_until="commit", timeout=30000)
            await page.wait_for_timeout(300)
        except Exception as e:
            _raise_if_publish_cancelled(cancel_event)
            print(f"[postVideoBatch] preload page failed type={job['platform_type']}: {e}")
    return pages


async def _post_video_batch_tabs_async(data_list, dry_run=True, progress_callback=None, cancel_event=None):
    async with async_playwright() as playwright:
        _raise_if_publish_cancelled(cancel_event)
        browser = await launch_publish_browser(playwright)
        jobs = []
        results = []
        context = None
        pages = []
        cancel_watcher = None
        publish_task = asyncio.current_task()

        async def watch_for_cancel():
            while not cancel_event.is_set():
                await asyncio.sleep(0.2)
            if browser.is_connected():
                try:
                    await browser.close()
                except Exception:
                    pass
            # Some platform upload loops catch browser-closed errors and retry.
            # Repeatedly cancelling the owner task also interrupts those retry sleeps.
            for _ in range(3):
                if publish_task.done():
                    break
                publish_task.cancel()
                await asyncio.sleep(0.05)

        if cancel_event:
            cancel_watcher = asyncio.create_task(watch_for_cancel())

        try:
            _raise_if_publish_cancelled(cancel_event)
            for data in data_list:
                platform_type = int(data.get("type"))
                files = [str(Path(BASE_DIR / "videoFile" / file)) for file in data.get("fileList", [])]
                cookies = [Path(BASE_DIR / "cookiesFile" / file) for file in data.get("accountList", [])]
                publish_datetimes = _build_publish_datetimes(
                    len(files),
                    data.get("enableTimer"),
                    data.get("videosPerDay"),
                    data.get("dailyTimes"),
                    data.get("startDays"),
                    data.get("timeJitterMinutes", 0),
                    schedule_time=data.get("scheduleTime"),
                )

                for index, file_path in enumerate(files):
                    for cookie_path in cookies:
                        jobs.append({
                            "data": data,
                            "platform_type": platform_type,
                            "file_path": file_path,
                            "cookie_path": cookie_path,
                            "publish_datetime": publish_datetimes[index],
                        })

            # Keep one browser window with multiple tabs. Put video account states last
            # so their stricter local/origin state wins when origins overlap.
            merged_cookie_paths = [
                job["cookie_path"]
                for job in sorted(jobs, key=lambda item: 1 if item["platform_type"] == 2 else 0)
            ]
            context = await new_publish_context(
                browser,
                storage_state=_merge_storage_states(merged_cookie_paths),
            )
            context = await set_init_script(context)

            pages = await _prepare_batch_pages(
                context,
                jobs,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
            )
            failed_platforms = set()
            for job, page in zip(jobs, pages):
                _raise_if_publish_cancelled(cancel_event)
                platform_type = job["platform_type"]
                if platform_type in failed_platforms:
                    continue

                app = _make_platform_app(
                    job["data"],
                    job["file_path"],
                    job["publish_datetime"],
                    job["cookie_path"],
                    dry_run=dry_run,
                    progress_callback=lambda event, pt=platform_type: _emit_publish_progress(
                        progress_callback, pt, **event
                    ),
                )
                app.external_page = page
                app.external_context = context
                app.external_browser = browser
                try:
                    await app.upload(playwright)
                    _raise_if_publish_cancelled(cancel_event)
                    _emit_publish_progress(
                        progress_callback,
                        platform_type,
                        stage="review" if dry_run else "success",
                        status="review" if dry_run else "success",
                        progress=100,
                        message="已停在最终发布前，等待检查" if dry_run else "平台发布成功",
                    )
                    results.append({
                        "type": platform_type,
                        "ok": True,
                        "message": None,
                    })
                except Exception as e:
                    _raise_if_publish_cancelled(cancel_event)
                    _emit_publish_progress(
                        progress_callback,
                        platform_type,
                        stage="failed",
                        status="failed",
                        message=str(e),
                    )
                    print(f"[postVideoBatch] platform {'dry-run' if dry_run else 'publish'} failed type={platform_type}: {e}")
                    results.append({
                        "type": platform_type,
                        "ok": False,
                        "message": str(e),
                    })
                    failed_platforms.add(platform_type)

            if dry_run and pages:
                await reveal_page_window(pages[0])
                for platform_type in {job["platform_type"] for job in jobs} - failed_platforms:
                    _emit_publish_progress(
                        progress_callback,
                        platform_type,
                        stage="review",
                        status="review",
                        progress=100,
                        message="预发布内容已填写，关闭浏览器后结束任务",
                    )
                print("[postVideoBatch] dry-run tabs ready, waiting for manual browser close...")
                while browser.is_connected():
                    _raise_if_publish_cancelled(cancel_event)
                    if pages and all(page.is_closed() for page in pages):
                        break
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            if cancel_event and cancel_event.is_set():
                raise PublishTaskCancelled("发布任务已由用户停止") from None
            raise
        finally:
            if cancel_watcher:
                cancel_watcher.cancel()
                try:
                    await cancel_watcher
                except asyncio.CancelledError:
                    pass
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            try:
                await browser.close()
            except Exception:
                pass
        return results


def post_video_batch_dry_run_tabs(data_list, progress_callback=None, cancel_event=None):
    return asyncio.run(
        _post_video_batch_tabs_async(
            data_list,
            dry_run=True,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        ),
        debug=False,
    )


def post_video_batch_tabs(data_list, dry_run=False, progress_callback=None, cancel_event=None):
    return asyncio.run(
        _post_video_batch_tabs_async(
            data_list,
            dry_run=dry_run,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        ),
        debug=False,
    )


def post_video_tencent(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, cover_path: str | None = None, cover_paths: dict | None = None, jitter_minutes=0, dry_run=False, dry_run_hold_browser=True):
    tags = normalize_publish_tags(tags)
    # 生成文件的完整路径
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times, start_days=start_days, jitter_minutes=jitter_minutes)
    else:
        publish_datetimes = [0 for i in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            thumb = _resolve_video_file_path(cover_path)
            thumbs = _resolve_cover_paths(cover_paths)
            app = TencentVideo(title, str(file), tags, publish_datetimes[index], cookie, category,
                               thumbnail_path=thumb, thumbnail_paths=thumbs, dry_run=dry_run,
                               dry_run_hold_browser=dry_run_hold_browser)
            asyncio.run(app.main(), debug=False)


def post_video_DouYin(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, cover_path: str | None = None, cover_paths: dict | None = None, jitter_minutes=0, dry_run=False, dry_run_hold_browser=True, description: str | None = None):
    tags = normalize_publish_tags(tags)
    # 生成文件的完整路径
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times, start_days=start_days, jitter_minutes=jitter_minutes)
    else:
        publish_datetimes = [0 for i in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            thumb = _resolve_cover_file_path(cover_path, prepare=True)
            thumbs = _resolve_cover_paths(cover_paths, prepare=True)
            app = DouYinVideo(title, str(file), tags, publish_datetimes[index], cookie, category=category,
                              thumbnail_path=thumb, thumbnail_paths=thumbs, dry_run=dry_run,
                              dry_run_hold_browser=dry_run_hold_browser, description=description)
            asyncio.run(app.main(), debug=False)


def post_video_ks(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, cover_path: str | None = None, cover_paths: dict | None = None, jitter_minutes=0, dry_run=False, dry_run_hold_browser=True):
    tags = normalize_publish_tags(tags, max_count=KUAISHOU_TAG_COUNT)
    # 生成文件的完整路径
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times, start_days=start_days, jitter_minutes=jitter_minutes)
    else:
        publish_datetimes = [0 for i in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            thumbs = _resolve_cover_paths(cover_paths)
            thumb = thumbs.get("3:4") or thumbs.get("4:3") or _resolve_video_file_path(cover_path)
            app = KSVideo(
                title,
                str(file),
                tags,
                publish_datetimes[index],
                cookie,
                thumbnail_path=thumb,
                thumbnail_paths=thumbs,
                dry_run=dry_run,
                dry_run_hold_browser=dry_run_hold_browser,
            )
            asyncio.run(app.main(), debug=False)

def post_video_xhs(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, cover_path: str | None = None, cover_paths: dict | None = None, jitter_minutes=0, dry_run=False, dry_run_hold_browser=True, description: str | None = None):
    tags = normalize_publish_tags(tags)
    # 生成文件的完整路径
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    file_num = len(files)
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(file_num, videos_per_day, daily_times, start_days=start_days, jitter_minutes=jitter_minutes)
    else:
        publish_datetimes = [0 for _ in range(file_num)]
    for index, file in enumerate(files):
        for cookie in account_file:
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            thumbs = _resolve_cover_paths(cover_paths)
            thumb = thumbs.get("4:3")
            app = XiaoHongShuVideo(title, file, tags, publish_datetimes[index], cookie, thumbnail_path=thumb, thumbnail_paths=thumbs, dry_run=dry_run, dry_run_hold_browser=dry_run_hold_browser, description=description)
            asyncio.run(app.main(), debug=False)


def post_video_bilibili(title, files, tags, account_file, category=None, enableTimer=False, videos_per_day=1, daily_times=None, start_days=0,
                        desc: str | None = None, bili_type: str | None = None, bili_partition: str | None = None,
                        cover_path: str | None = None, cover_paths: dict | None = None,
                        schedule_time: str | None = None, jitter_minutes=0, dry_run=False, dry_run_hold_browser=True):
    tags = normalize_publish_tags(tags)
    account_file = [Path(BASE_DIR / "cookiesFile" / file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    if enableTimer and schedule_time:
        publish_datetimes = [schedule_time for _ in range(len(files))]
    elif enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times, start_days=start_days, jitter_minutes=jitter_minutes)
    else:
        publish_datetimes = [0 for _ in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            print(f"标题：{title}")
            print(f"Hashtag：{tags}")
            thumbs = _resolve_cover_paths(cover_paths)
            bili_cover_path = thumbs.get("16:9") or thumbs.get("4:3") or _resolve_video_file_path(cover_path)
            app = BilibiliVideo(title, str(file), tags, publish_datetimes[index], cookie,
                                thumbnail_path=bili_cover_path, thumbnail_paths=thumbs,
                                desc=desc, bili_type=bili_type, partition=bili_partition, dry_run=dry_run,
                                dry_run_hold_browser=dry_run_hold_browser)
            asyncio.run(app.main(), debug=False)



# post_video("333",["demo.mp4"],"d","d")
# post_video_DouYin("333",["demo.mp4"],"d","d")
