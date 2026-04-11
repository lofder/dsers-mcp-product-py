"""
File-based Job Store — Lightweight persistence for import jobs.
基于文件的任务存储 —— 导入任务的轻量级持久化方案

Each import job is stored as a standalone JSON file under a configurable
root directory. This avoids any database dependency while still allowing
the MCP server to survive restarts. A UUID is generated for each job,
making it safe for concurrent access across separate requests.

每个导入任务作为独立 JSON 文件存储在可配置的根目录下。此方案避免了对
数据库的依赖，同时允许 MCP 服务器在重启后仍能恢复任务状态。每个任务
使用 UUID 标识，可安全地在并发请求间使用。
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict

from .security import validate_job_id


class FileJobStore:
    """
    Persist import job state as JSON files on disk.
    将导入任务状态以 JSON 文件形式持久化到磁盘。
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def create(self, payload: Dict[str, Any]) -> str:
        """
        Create a new job with a unique ID and persist the initial state.
        创建一个带唯一 ID 的新任务并持久化初始状态。
        """
        job_id = str(uuid.uuid4())
        self.save(job_id, payload)
        return job_id

    def save(self, job_id: str, payload: Dict[str, Any]) -> None:
        """
        Overwrite the stored state for an existing job.
        覆盖已有任务的存储状态。
        """
        self._job_path(job_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, job_id: str) -> Dict[str, Any]:
        """
        Load the stored state for a job. Raises KeyError if not found.
        加载任务的存储状态。如果未找到则抛出 KeyError。
        """
        path = self._job_path(job_id)
        if not path.exists():
            raise KeyError(f"Unknown job_id: {job_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _job_path(self, job_id: str) -> Path:
        safe_id = validate_job_id(job_id)
        return self._root / f"{safe_id}.json"
