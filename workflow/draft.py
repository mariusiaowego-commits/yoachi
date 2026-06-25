"""Badge draft 草稿持久化 — 从 dizical badge_draft.py 适配.

文件契约: workflow/draft.py 管理 data/badge_data/*.json
状态机: draft_created → draft_awaiting_confirm → confirmed → committed / discarded
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
VALID_STATUSES = frozenset(
    ["draft_created", "draft_awaiting_confirm", "confirmed", "committed", "discarded"]
)
ID_RE = re.compile(r"^[a-zA-Z0-9_]+$")
DRAFT_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-zA-Z0-9_-]+_[a-z0-9]{6,}$")


def _badge_data_dir() -> Path:
    """data/badge_data/ 根目录."""
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / "badge_data"


def _tmp_dir() -> Path:
    """生图临时目录."""
    return _badge_data_dir() / ".tmp"


# ─── 数据类 ───────────────────────────────────────────────────

@dataclass
class BadgeDraft:
    schema_version: int
    draft_id: str
    created_at: str
    version: int
    meta: dict[str, Any]
    image: dict[str, Any] | None
    status: str
    updated_at: str
    history: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BadgeDraft":
        return cls(
            schema_version=d.get("schema_version", 1),
            draft_id=d["draft_id"],
            created_at=d["created_at"],
            version=d.get("version", 1),
            meta=d.get("meta", {}),
            image=d.get("image"),
            status=d.get("status", "draft_created"),
            updated_at=d.get("updated_at", d["created_at"]),
            history=d.get("history", []),
        )


# ─── CRUD ─────────────────────────────────────────────────────

def create_draft(meta: dict[str, Any]) -> BadgeDraft:
    """创建新 draft, 写入 JSON 文件."""
    badge_id = meta.get("id", "")
    if not ID_RE.match(badge_id):
        raise ValueError(f"Invalid badge id: {badge_id}")

    now = datetime.now()
    draft_id = f"{now.strftime('%Y-%m-%d')}_{badge_id}_{uuid.uuid4().hex[:6]}"
    ts = now.isoformat()

    draft = BadgeDraft(
        schema_version=SCHEMA_VERSION,
        draft_id=draft_id,
        created_at=ts,
        version=1,
        meta=meta,
        image=None,
        status="draft_created",
        updated_at=ts,
        history=[{"at": ts, "from": "", "to": "draft_created", "by": "user", "event": "created"}],
    )

    draft_path = _badge_data_dir() / f"{draft_id}.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2))
    return draft


def load_draft(draft_id: str) -> BadgeDraft | None:
    """读取 draft JSON."""
    draft_path = _badge_data_dir() / f"{draft_id}.json"
    if not draft_path.exists():
        return None
    return BadgeDraft.from_dict(json.loads(draft_path.read_text()))


def save_draft(draft: BadgeDraft) -> None:
    """写回 draft JSON."""
    draft_path = _badge_data_dir() / f"{draft.draft_id}.json"
    draft_path.write_text(json.dumps(draft.to_dict(), ensure_ascii=False, indent=2))


def list_drafts(status: str | None = None) -> list[BadgeDraft]:
    """列出所有 draft, 可选按 status 过滤."""
    drafts = []
    for f in sorted(_badge_data_dir().glob("*.json")):
        if f.name.startswith("."):
            continue
        try:
            d = BadgeDraft.from_dict(json.loads(f.read_text()))
            if status is None or d.status == status:
                drafts.append(d)
        except (json.JSONDecodeError, KeyError):
            continue
    return drafts


def update_draft_status(draft: BadgeDraft, new_status: str, by: str = "system") -> BadgeDraft:
    """更新 draft 状态 + 追加 history."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    now = datetime.now().isoformat()
    draft.history.append({
        "at": now, "from": draft.status, "to": new_status, "by": by, "event": "status_change"
    })
    draft.status = new_status
    draft.updated_at = now
    save_draft(draft)
    return draft


def update_draft_image(draft: BadgeDraft, image_info: dict[str, Any]) -> BadgeDraft:
    """写入图片信息 + 状态推到 draft_awaiting_confirm."""
    now = datetime.now().isoformat()
    draft.image = image_info
    draft.history.append({
        "at": now, "from": draft.status, "to": "draft_awaiting_confirm",
        "by": "skill", "event": "image_generated"
    })
    draft.status = "draft_awaiting_confirm"
    draft.updated_at = now
    save_draft(draft)
    return draft


def discard_draft(draft_id: str) -> bool:
    """丢弃 draft (标记 discarded)."""
    draft = load_draft(draft_id)
    if not draft:
        return False
    update_draft_status(draft, "discarded", by="user")
    return True
