"""图片访问路由"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/images", tags=["images"])

ALLOWED_DIR = Path(__file__).parent.parent / "static" / "images"


@router.get("/{filename}")
def get_image(filename: str):
    """返回静态图片文件，防止路径逃逸。"""
    # 禁止 ../ 逃逸
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise HTTPException(400, "Invalid filename")

    file_path = ALLOWED_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "Image not found")
    if not file_path.is_file():
        raise HTTPException(400, "Not a file")
    # 严格检查真实路径在允许目录下
    if not file_path.resolve().is_relative_to(ALLOWED_DIR.resolve()):
        raise HTTPException(400, "Invalid path")

    # 推断 content-type
    suffix = file_path.suffix.lower()
    content_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    content_type = content_types.get(suffix, "application/octet-stream")
    return FileResponse(file_path, media_type=content_type)
