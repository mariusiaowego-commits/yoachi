"""Badge 图片生成器 — 从 dizical badge_generator.py 适配.

流程: prompt → hermes image_gen → PIL 去白底 → rembg 兜底 → 落盘
"""
from __future__ import annotations

import logging
import re
import subprocess
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

# Badge PNG 落盘目录
_BADGES_DIR = Path(__file__).resolve().parent.parent / "static" / "badges"

# 生图超时
_GEN_TIMEOUT = 180

# enamel pin prompt 模板 (V2.3 2026-06-16)
UNLOCKED_TPL = (
    "An emoji-adjacent 3D enamel pin of {PLACEHOLDER}. "
    "Polished gold metal borders enclose flat, glossy enamel fills. "
    "The design is a centered, iconic illustration with a smooth, friendly silhouette "
    "and vibrant colors, matching a child's achievement badge style. "
    "Studio lighting reflects off the reflective enamel and raised gold metal edges. "
    "Orthographic, straight-on view, high quality, isolated object, transparent PNG background."
)


# ─── 去白底 ──────────────────────────────────────────────────

def _dedupe_to_rgba(src: Path) -> tuple[bool, float]:
    """把 RGB/RGBA PNG 的近白像素 → 透明.

    Returns: (success, transparency_pct)
    """
    img = Image.open(src)
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    THRESHOLD = 245
    pixels = img.load()
    w, h = img.size

    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r > THRESHOLD and g > THRESHOLD and b > THRESHOLD:
                pixels[x, y] = (r, g, b, 0)

    img.save(src, optimize=True)

    alpha = img.split()[-1]
    trans_count = sum(1 for px in alpha.getdata() if px < 128)
    trans_pct = trans_count / (w * h) * 100
    return True, trans_pct


def _rembg_fallback(src: Path) -> tuple[bool, float]:
    """rembg U2-Net 兜底: 透明像素 < 28% 时触发."""
    try:
        from rembg import remove
        from io import BytesIO

        with open(src, "rb") as f:
            raw = f.read()
        out_bytes = remove(raw)
        img = Image.open(BytesIO(out_bytes))
        img.save(src, optimize=True)

        if img.mode == "RGBA":
            alpha = img.split()[-1]
            w, h = img.size
            trans = sum(1 for px in alpha.getdata() if px < 128)
            trans_pct = trans / (w * h) * 100
            return True, trans_pct
        return True, 0.0
    except ImportError:
        logger.warning("rembg 未安装, 跳过兜底")
        return False, 0.0
    except Exception as e:
        logger.warning(f"rembg 兜底失败: {e}")
        return False, 0.0


def remove_background(src: Path) -> tuple[bool, float]:
    """双保险去白底: PIL 阈值 + rembg 兜底.

    Returns: (success, transparency_pct)
    """
    ok, pct = _dedupe_to_rgba(src)
    logger.info(f"PIL 阈值去白底: 透明像素 {pct:.0f}%")

    if pct < 28:
        logger.info(f"透明像素 {pct:.0f}% < 28%, 触发 rembg 兜底")
        rembg_ok, rembg_pct = _rembg_fallback(src)
        if rembg_ok:
            logger.info(f"rembg 处理后透明像素 {rembg_pct:.0f}%")
            return True, rembg_pct
        logger.warning("rembg 兜底失败, 保持 PIL 结果")

    return ok, pct


# ─── 生图 ────────────────────────────────────────────────────

def _find_hermes() -> str:
    """找到 hermes CLI 路径."""
    hermes = shutil.which("hermes")
    if hermes:
        return hermes
    # fallback paths
    for p in ["/opt/homebrew/bin/hermes", "/usr/local/bin/hermes"]:
        if Path(p).exists():
            return p
    raise FileNotFoundError("hermes CLI not found")


def generate_image(placeholder: str, badge_id: str, version: int = 1) -> dict[str, Any]:
    """调 hermes image_gen 生图 + 去白底 + 落盘.

    Returns: image_info dict (path, model, prompt_used, alpha_verified, version)
    """
    prompt = UNLOCKED_TPL.replace("{PLACEHOLDER}", placeholder)
    hermes = _find_hermes()

    # 调 hermes image_gen
    logger.info(f"Calling hermes image_gen for badge '{badge_id}'...")
    try:
        result = subprocess.run(
            [hermes, "chat", "-q", prompt, "-t", "image_gen", "--profile", "coder", "-Q", "--yolo"],
            capture_output=True, text=True, timeout=_GEN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"hermes image_gen timeout ({_GEN_TIMEOUT}s)")

    if result.returncode != 0:
        raise RuntimeError(f"hermes failed: {result.stderr}")

    # 解析输出拿图路径
    output = result.stdout
    img_path = None

    # 尝试从 MEDIA: 解析
    media_match = re.search(r"MEDIA:(\S+)", output)
    if media_match:
        img_path = Path(media_match.group(1))

    # 尝试从 "Image saved to:" 解析
    if not img_path:
        saved_match = re.search(r"Image saved to:\s*(\S+)", output)
        if saved_match:
            img_path = Path(saved_match.group(1))

    if not img_path or not img_path.exists():
        raise RuntimeError(f"未找到生成的图片. hermes output:\n{output}")

    # 落盘到 static/badges/
    _BADGES_DIR.mkdir(parents=True, exist_ok=True)
    dest = _BADGES_DIR / f"{badge_id}_v{version}.png"
    shutil.copy2(img_path, dest)

    # 去白底
    ok, pct = remove_background(dest)

    return {
        "path": str(dest),
        "url": f"/static/badges/{badge_id}_v{version}.png",
        "model": "gpt-image-2",
        "prompt_used": prompt,
        "alpha_verified": ok,
        "transparency_pct": round(pct, 1),
        "version": version,
    }


def _validate_uploaded_image(path: Path) -> tuple[bool, float]:
    """校验上传图片: 必须是 PNG/RGBA + 透明像素 > 28%.

    用户上传的图不强制去白底 (有的人本来就传好 PNG),
    但必须满足最低透明度阈值, 否则不算合格 badge.
    """
    try:
        img = Image.open(path)
    except Exception as e:
        logger.warning(f"上传图片无法打开: {e}")
        return False, 0.0

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    alpha = img.split()[-1]
    w, h = img.size
    trans = sum(1 for px in alpha.getdata() if px < 128)
    trans_pct = trans / (w * h) * 100

    if trans_pct < 28:
        logger.warning(f"上传图片透明度 {trans_pct:.0f}% < 28%, 不合格")
        return False, trans_pct

    return True, trans_pct


def save_uploaded_image(
    source: Path,
    badge_id: str,
    version: int = 1,
    auto_remove_bg: bool = True,
) -> dict[str, Any]:
    """把上传图片落盘到 static/badges/, 可选去白底.

    Returns: image_info dict (与 generate_image 同 schema)
    Raises: ValueError 当图片不合格.
    """
    import uuid as _uuid

    _BADGES_DIR.mkdir(parents=True, exist_ok=True)

    # 用 UUID 后缀避免 name 冲突, 但保留 badge_id 可读
    suffix = source.suffix.lower() or ".png"
    dest_name = f"{badge_id}_v{version}_{_uuid.uuid4().hex[:4]}{suffix}"
    dest = _BADGES_DIR / dest_name

    shutil.copy2(source, dest)

    # 如果不是 RGBA 或透明不够, 尝试去白底
    img = Image.open(dest)
    needs_dedup = False
    if img.mode != "RGBA":
        img = img.convert("RGBA")
        needs_dedup = True

    alpha = img.split()[-1]
    w, h = img.size
    trans = sum(1 for px in alpha.getdata() if px < 128)
    trans_pct = trans / (w * h) * 100

    if trans_pct < 28 and auto_remove_bg:
        logger.info(f"上传图透明度 {trans_pct:.0f}% < 28%, 尝试去白底")
        needs_dedup = True

    if needs_dedup:
        img.save(dest, optimize=True)
        ok, pct = remove_background(dest)
        if not ok:
            raise ValueError(f"上传图片不合格且去白底失败, 透明度 {pct:.0f}%")
        trans_pct = pct

    return {
        "path": str(dest),
        "url": f"/static/badges/{dest_name}",
        "model": "user_upload",
        "prompt_used": "(uploaded)",
        "alpha_verified": trans_pct >= 28,
        "transparency_pct": round(trans_pct, 1),
        "version": version,
    }


# ─── Commit to DB ────────────────────────────────────────────

def commit_draft_to_db(draft_meta: dict[str, Any], image_info: dict[str, Any] | None) -> str:
    """把 draft 写入 yoachi.db 三表 (achievements + achievement_stats + achievement_badges).

    Returns: badge_id
    """
    import sqlite3
    from config import Config

    badge_id = draft_meta["id"]
    conn = sqlite3.connect(Config.DATABASE_PATH)
    try:
        # Check if already exists
        existing = conn.execute("SELECT id FROM achievements WHERE id = ?", (badge_id,)).fetchone()
        if existing:
            # Update existing
            conn.execute("""
                UPDATE achievements SET
                    name=?, type=?, category=?, description=?, cond_text=?,
                    unlock_strategy=?, threshold=?, display_format=?, rarity=?,
                    sort_order=?, updated_at=datetime('now')
                WHERE id=?
            """, (
                draft_meta.get("name", ""), draft_meta.get("type", "突破"),
                draft_meta.get("category", "li"), draft_meta.get("description", ""),
                draft_meta.get("cond_text", ""), draft_meta.get("unlock_strategy", "calc"),
                draft_meta.get("threshold"), draft_meta.get("display_format", "count"),
                draft_meta.get("rarity", "N"), draft_meta.get("sort_order", 0),
                badge_id,
            ))
        else:
            # Insert new
            conn.execute("""
                INSERT INTO achievements (id, name, type, category, description, cond_text,
                    unlock_strategy, threshold, display_format, rarity, sort_order,
                    stat_logic, placeholder, locked_template, unlocked_template)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                badge_id, draft_meta.get("name", ""), draft_meta.get("type", "突破"),
                draft_meta.get("category", "li"), draft_meta.get("description", ""),
                draft_meta.get("cond_text", ""), draft_meta.get("unlock_strategy", "calc"),
                draft_meta.get("threshold"), draft_meta.get("display_format", "count"),
                draft_meta.get("rarity", "N"), draft_meta.get("sort_order", 0),
                "", "", "", "",
            ))

        # Stats
        conn.execute(
            "INSERT OR IGNORE INTO achievement_stats (achievement_id, achieved) VALUES (?, 'N')",
            (badge_id,)
        )

        # Badge image
        if image_info:
            # Mark old images as not current
            conn.execute(
                "UPDATE achievement_badges SET is_current = 0 WHERE achievement_id = ?",
                (badge_id,)
            )
            conn.execute("""
                INSERT INTO achievement_badges (achievement_id, url, version, is_current)
                VALUES (?, ?, ?, 1)
            """, (badge_id, image_info.get("url", ""), image_info.get("version", 1)))

        conn.commit()
        logger.info(f"Badge '{badge_id}' committed to DB")
    finally:
        conn.close()

    return badge_id
