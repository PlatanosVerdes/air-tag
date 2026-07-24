"""Background loop: periodically fetch reports and persist decrypted points."""

from __future__ import annotations

import asyncio
import logging

from . import config, tracker
from .db import Store

logger = logging.getLogger(__name__)


class Poller:
    def __init__(self, store: Store) -> None:
        self._store = store
        self._task: asyncio.Task | None = None
        self.last_ok: float | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="airtag-poller")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def poll_once(self) -> int:
        """One fetch cycle. Returns number of new points stored."""
        device = tracker.load_device()
        account = tracker.restore_account()
        try:
            reports = await tracker.fetch_reports(account, device)
            rows = [tracker.report_to_row(r) for r in reports]
            new = await self._store.insert_many(rows)
            logger.info("Fetched %d reports, %d new", len(reports), new)
            return new
        finally:
            await account.close()
            # Persist refreshed session + any learned device alignment.
            account.to_json(config.ACCOUNT_PATH)
            tracker.persist_device(device)

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            if config.is_configured():
                try:
                    await self.poll_once()
                    self.last_ok = loop.time()
                    self.last_error = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 — keep the loop alive
                    self.last_error = str(exc)
                    logger.exception("Poll failed")
            else:
                logger.warning("Not configured yet (missing account.json/accessory.json)")
            await asyncio.sleep(config.POLL_INTERVAL)
