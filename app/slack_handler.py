import asyncio
import threading
from app.config import settings
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler


class SlackSocketModeHandler:
    def __init__(self, app: AsyncApp):
        self._thread = None
        self._handler = None
        self._loop = asyncio.new_event_loop()
        self._app = app

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread is not None:
            close_thread = threading.Thread(target=self._close, daemon=True)
            close_thread.start()
            close_thread.join()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._handler = AsyncSocketModeHandler(self._app, settings.APP_TOKEN)
        self._loop.run_until_complete(self._handler.start_async())

    def _close(self):
        self._loop.call_soon_threadsafe(
            self._loop.create_task, self._handler.close_async()
        )
