import json
from pathlib import Path

from app.schemas.ingest import EmailIngestRequest


def test_logic_app_example_parses():
    path = Path(__file__).resolve().parents[2] / "docs" / "contracts" / "logic-app-ingest.example.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    model = EmailIngestRequest.model_validate(payload)
    assert model.schema_version == "1.0"
    assert model.conversation_id.startswith("AAQk")
    assert model.sender.email == "broker@agency.example"
    assert len(model.attachments) == 2
    assert model.attachments[0].file_name == "police-report.pdf"
