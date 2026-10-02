"""Compare every public JSON object with TypeScript's resolved interface shapes."""

import json
import subprocess
from pathlib import Path

import pytest

from paper_evidence.api.app import app

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend/src/api/contracts.ts"
INSPECTOR = ROOT / "frontend/scripts/inspect-contracts.mjs"


def frontend_shapes(source: Path = SOURCE) -> dict:
    result = subprocess.run(["node", str(INSPECTOR), str(source)], text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def assert_shapes_match(frontend: dict) -> None:
    schemas = app.openapi()["components"]["schemas"]
    objects = {name: schema for name, schema in schemas.items() if schema.get("type") == "object"}
    assert set(frontend) == set(objects), (set(frontend) - set(objects), set(objects) - set(frontend))
    for name, schema in objects.items():
        expected = {}
        for field, value in schema["properties"].items():
            expected[field] = {
                "required": field in schema.get("required", []),
                "nullable": value.get("type") == "null" or any(part.get("type") == "null" for part in value.get("anyOf", [])),
            }
        assert frontend[name] == expected, (name, frontend[name], expected)


def test_frontend_object_shapes_match_openapi():
    shapes = frontend_shapes()
    assert_shapes_match(shapes)
    # Resolved inheritance/Omit and optional-versus-nullable are significant.
    assert shapes["RetryCreated"]["id"] == {"required": True, "nullable": False}
    assert "validation" not in shapes["EvidenceCandidate"]
    assert shapes["EvidenceCandidate"]["quote"] == {"required": True, "nullable": False}
    assert shapes["CheckCreateRequest"]["previous_id"] == {"required": False, "nullable": True}


@pytest.mark.parametrize("before,after", [
    ("export interface ApiError { error_code: ErrorCode | null; message: string }", "export interface ApiError { error_code: ErrorCode | null }"),
    ("export interface ApiError {", "export interface ApiError { unexpected: string;"),
    ("message: string }", "message?: string }"),
    ("error_code: ErrorCode | null; message", "error_code: ErrorCode; message"),
    ("export interface ConflictResponse {", "interface ConflictResponseRenamed {"),
])
def test_shape_comparison_detects_frontend_drift(before, after, tmp_path):
    source = SOURCE.read_text(encoding="utf-8")
    assert before in source
    changed = tmp_path / "contracts.ts"
    changed.write_text(source.replace(before, after, 1), encoding="utf-8")
    with pytest.raises(AssertionError):
        assert_shapes_match(frontend_shapes(changed))
