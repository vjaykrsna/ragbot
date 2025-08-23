"""
External sorting component for the data processing pipeline.

This module provides a class for sorting large streams of data that do not fit
into memory. It uses a chunking and k-way merge strategy.
"""

import gzip
import heapq
import json
import os
import tempfile
from typing import Any, Dict, Generator, List, Tuple

import structlog
from dateutil.parser import isoparse

from src.processing.data_source import DataSource

logger = structlog.get_logger(__name__)


class ExternalSorter:
    """
    Sorts a stream of messages from a DataSource using external sorting.
    """

    def __init__(self, chunk_size: int = 50_000, use_gzip: bool = True):
        """
        Initializes the ExternalSorter.
        """
        self.chunk_size = chunk_size
        self.use_gzip = use_gzip
        self.logger = structlog.get_logger(__name__)

    def sort(self, data_source: DataSource) -> Generator[Dict[str, Any], None, None]:
        """Sorts the data and yields messages in chronological order."""
        chunk_paths = self._write_sorted_chunks(data_source)
        if not chunk_paths:
            return

        yield from self._merge_sorted_chunks(chunk_paths)

    def _write_sorted_chunks(self, data_source: DataSource) -> List[str]:
        """
        Reads messages from the data source, sorts them into chunks, and writes
        them to temporary files.
        """
        chunk_paths: List[str] = []
        buf: List[Tuple[str, str]] = []  # (date_iso, json_line)
        total = 0

        def flush_chunk() -> None:
            nonlocal buf
            if not buf:
                return
            buf.sort(key=lambda x: x[0])
            fd, tmp_path = tempfile.mkstemp(suffix=self._temp_suffix(), prefix="chunk_")
            os.close(fd)
            with self._open_temp(tmp_path, "w") as w:
                for _, line in buf:
                    w.write(line)
                    if not line.endswith("\n"):
                        w.write("\n")
            chunk_paths.append(tmp_path)
            self.logger.info(f"Wrote sorted chunk with {len(buf)} msgs -> {tmp_path}")
            buf = []

        for rec in data_source:
            try:
                dt = isoparse(rec["date"])
                buf.append((dt.isoformat(), json.dumps(rec, ensure_ascii=False)))
                total += 1
                if len(buf) >= self.chunk_size:
                    flush_chunk()
            except (ValueError, TypeError):
                self.logger.warning(
                    f"Skipping record with invalid date: {rec.get('date')}"
                )

        flush_chunk()
        self.logger.info(
            f"Prepared {len(chunk_paths)} sorted chunk(s) from {total} messages."
        )
        return chunk_paths

    def _merge_sorted_chunks(
        self, chunk_paths: List[str]
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Performs a k-way merge of the sorted chunk files.
        """
        files = [(p, self._open_temp(p, "r")) for p in chunk_paths]
        heap = []

        def gen(fh):
            for line in fh:
                try:
                    rec = json.loads(line)
                    if rec.get("date"):
                        yield (rec["date"], rec)
                except json.JSONDecodeError:
                    pass

        generators = [gen(fh) for _, fh in files]

        for idx, g in enumerate(generators):
            try:
                date_str, rec = next(g)
                heap.append((date_str, idx, rec, g))
            except StopIteration:
                pass
        heapq.heapify(heap)

        try:
            while heap:
                date_str, idx, rec, g = heapq.heappop(heap)
                yield rec
                try:
                    next_date_str, next_rec = next(g)
                    heapq.heappush(heap, (next_date_str, idx, next_rec, g))
                except StopIteration:
                    pass
        finally:
            for _, fh in files:
                fh.close()
            for p, _ in files:
                try:
                    os.remove(p)
                except OSError as e:
                    self.logger.error(f"Error removing temp file {p}: {e}")

    def _open_temp(self, path: str, mode: str):
        if self.use_gzip:
            return gzip.open(path, mode + "t", encoding="utf-8")
        return open(path, mode, encoding="utf-8")

    def _temp_suffix(self) -> str:
        return ".jsonl.gz" if self.use_gzip else ".jsonl"
