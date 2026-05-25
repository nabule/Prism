import base64
import json
import urllib.parse
import zlib
import pytest
from fastapi.testclient import TestClient

from memosima.core.attachments import parse_drawio, parse_mind_elixir, AttachmentResource
from memosima.api.app import create_app


def _compress_drawio(xml_str: str) -> str:
    # Deflate raw -> base64
    compressor = zlib.compressobj(wbits=-15)
    deflated = compressor.compress(xml_str.encode("utf-8")) + compressor.flush()
    return base64.b64encode(deflated).decode("utf-8")


def test_parse_drawio_plain():
    plain_xml = """<mxGraphModel>
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="2" value="&lt;b&gt;Hello World&lt;/b&gt;" vertex="1" parent="1"/>
        <mxCell id="3" value="Normal Cell" vertex="1" parent="1"/>
      </root>
    </mxGraphModel>"""
    
    resource = AttachmentResource(name="res1", filename="diagram.drawio", content_type="application/octet-stream", size=len(plain_xml))
    result = parse_drawio(plain_xml.encode("utf-8"))
    
    assert "Hello World" in result
    assert "Normal Cell" in result
    assert "1. Hello World" in result
    assert "2. Normal Cell" in result


def test_parse_drawio_compressed():
    diagram_xml = """<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/><mxCell id="2" value="Compressed Element" vertex="1" parent="1"/></root></mxGraphModel>"""
    compressed_str = _compress_drawio(diagram_xml)
    
    mxfile_xml = f"""<mxfile>
      <diagram id="d1" name="Page-1">{compressed_str}</diagram>
    </mxfile>"""
    
    result = parse_drawio(mxfile_xml.encode("utf-8"))
    assert "Compressed Element" in result
    assert "1. Compressed Element" in result


def test_parse_mind_elixir():
    mind_data = {
        "nodeData": {
            "topic": "Root Mindmap",
            "children": [
                {
                    "topic": "Level 1 Child A",
                    "children": [
                        {"topic": "Level 2 Sub A"}
                    ]
                },
                {
                    "topic": "Level 1 Child B"
                }
            ]
        }
    }
    
    raw_json = json.dumps(mind_data).encode("utf-8")
    result = parse_mind_elixir(raw_json)
    
    assert "Root Mindmap" in result
    assert "Level 1 Child A" in result
    assert "Level 2 Sub A" in result
    assert "Level 1 Child B" in result
    assert "- Root Mindmap" in result
    assert "  - Level 1 Child A" in result
    assert "    - Level 2 Sub A" in result


@pytest.fixture
def client():
    app = create_app()
    app.state.admin_token = "testtoken"
    return TestClient(app)


def test_generate_prompt_route_error(client):
    # Without authorization header, it should return 401
    response = client.post("/admin/qa/generate-prompt", json={
        "tags": ["#项目/个人AI知识库"],
        "system_prompt": "You are a helpful assistant.",
        "query": "What is the deployment process?"
    })
    assert response.status_code == 401


def test_generate_prompt_logical_relations(client, monkeypatch):
    # Mock MemosClient to return specific memos when filtered
    class MockMemosClient:
        def __init__(self, *args, **kwargs):
            pass

        async def list_memos(self, page_size, page_token=None, filter_text=None):
            # If no filter, return all
            # If filter is '#tag1', return memo1 and memo2
            # If filter is '#tag2', return memo1
            memos = [
                {
                    "name": "memos/memo1",
                    "content": "This is memo 1 with #tag1 and #tag2",
                    "tags": ["tag1", "tag2"],
                    "createTime": "2026-05-25T12:00:00Z"
                },
                {
                    "name": "memos/memo2",
                    "content": "This is memo 2 with #tag1 only",
                    "tags": ["tag1"],
                    "createTime": "2026-05-25T12:05:00Z"
                }
            ]
            if filter_text:
                if "tag1" in filter_text:
                    return {"memos": memos}
                elif "tag2" in filter_text:
                    return {"memos": [memos[0]]}
            return {"memos": memos}

    import memosima.api.app as app_module
    monkeypatch.setattr(app_module, "MemosClient", MockMemosClient)
    
    # Configure memos_base_url and api_token so validation passes
    object.__setattr__(client.app.state.config, "memos_base_url", "http://memos.local")
    object.__setattr__(client.app.state.config, "memos_api_token", "some-token")

    # Test OR relationship (default)
    response = client.post("/admin/qa/generate-prompt", 
        headers={"Authorization": "Bearer testtoken"},
        json={
            "tags": ["#tag1", "#tag2"],
            "relation": "OR",
            "system_prompt": "You are a helpful assistant.",
            "query": "Hello"
        }
    )
    assert response.status_code == 200
    data = response.json()
    # OR relation should retrieve both memo1 and memo2
    assert data["retrieved_count"] == 2
    assert "memo1" in [s["memos_uid"] for s in data["sources"]]
    assert "memo2" in [s["memos_uid"] for s in data["sources"]]

    # Test AND relationship
    response = client.post("/admin/qa/generate-prompt", 
        headers={"Authorization": "Bearer testtoken"},
        json={
            "tags": ["#tag1", "#tag2"],
            "relation": "AND",
            "system_prompt": "You are a helpful assistant.",
            "query": "Hello"
        }
    )
    assert response.status_code == 200
    data = response.json()
    # AND relation should only retrieve memo1 (since memo2 only has tag1)
    assert data["retrieved_count"] == 1
    assert data["sources"][0]["memos_uid"] == "memo1"
