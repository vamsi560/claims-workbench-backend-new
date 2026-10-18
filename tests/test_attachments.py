from app.models import AttachmentKind
from app.services.attachments import classify_attachment_kind


def test_classify_by_extension():
    assert classify_attachment_kind("report.PDF", None) is AttachmentKind.pdf
    assert classify_attachment_kind("notes.txt", "text/plain") is AttachmentKind.txt
    assert classify_attachment_kind("clip.mp4", "video/mp4") is AttachmentKind.mp4
    assert classify_attachment_kind("unknown.bin", None) is AttachmentKind.other


def test_classify_prefers_content_type():
    assert classify_attachment_kind("file.bin", "application/pdf") is AttachmentKind.pdf
    assert classify_attachment_kind("pic.jpg", "image/jpeg") is AttachmentKind.jpeg
