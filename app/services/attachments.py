from pathlib import PurePosixPath

from app.models import AttachmentKind

_CONTENT_TYPE_KIND = {
    "application/pdf": AttachmentKind.pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": AttachmentKind.docx,
    "application/msword": AttachmentKind.docx,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": AttachmentKind.xlsx,
    "application/vnd.ms-excel": AttachmentKind.xlsx,
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": AttachmentKind.pptx,
    "application/vnd.ms-powerpoint": AttachmentKind.pptx,
    "text/plain": AttachmentKind.txt,
    "image/png": AttachmentKind.png,
    "image/jpeg": AttachmentKind.jpeg,
    "image/jpg": AttachmentKind.jpeg,
    "video/mp4": AttachmentKind.mp4,
}

_EXT_KIND = {
    ".pdf": AttachmentKind.pdf,
    ".docx": AttachmentKind.docx,
    ".doc": AttachmentKind.docx,
    ".xlsx": AttachmentKind.xlsx,
    ".xls": AttachmentKind.xlsx,
    ".pptx": AttachmentKind.pptx,
    ".ppt": AttachmentKind.pptx,
    ".txt": AttachmentKind.txt,
    ".png": AttachmentKind.png,
    ".jpeg": AttachmentKind.jpeg,
    ".jpg": AttachmentKind.jpeg,
    ".mp4": AttachmentKind.mp4,
}


def classify_attachment_kind(file_name: str, content_type: str | None) -> AttachmentKind:
    if content_type:
        mapped = _CONTENT_TYPE_KIND.get(content_type.split(";")[0].strip().lower())
        if mapped:
            return mapped
    ext = PurePosixPath(file_name).suffix.lower()
    return _EXT_KIND.get(ext, AttachmentKind.other)
