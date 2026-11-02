"""Run inside either runtime image, with no secret mount and no networking."""

import importlib
import os
from pathlib import Path
import tempfile

os.environ["AZURE_SPEECH_KEY"] = ""
os.environ["AZURE_API_KEY_1"] = ""
os.environ["AZURE_SPEECH_REGION"] = ""
os.environ.pop("AZURE_SPEECH_KEY_FILE", None)
container_app = importlib.import_module("container_app")
app = container_app.app
client = app.test_client()
assert client.get("/").status_code == 200
if Path("live_speech.py").exists():
    path = "/api/text-to-speech"
    assert client.get("/api/health").json == {"configured": False}
else:
    path = "/api/speech/speak"
    assert client.post("/api/calculate", json={"operator": "+", "operands": [3, 5]}).json == {"result": 8}
assert client.post(path, json={"text": "three"}).status_code == 503
assert client.post(path, json={"text": "three"}, headers={"Origin": "https://example.invalid"}).status_code == 403
os.environ["AZURE_SPEECH_KEY_FILE"] = "/missing-key"
try:
    container_app.load_speech_key()
except RuntimeError as error:
    assert str(error) == "Cannot read the mounted Azure Speech key."
else:
    raise AssertionError("Missing key file must fail safely")
with tempfile.TemporaryDirectory() as tmp:
    secret = Path(tmp) / "key"
    secret.write_text("test-only-key\n")
    os.environ["AZURE_SPEECH_KEY_FILE"] = str(secret)
    container_app.load_speech_key()
    assert os.environ["AZURE_SPEECH_KEY"] == os.environ["AZURE_API_KEY_1"] == "test-only-key"
    assert not Path("/app/.env").exists()
    try:
        Path("/app/should-not-be-writable").touch()
    except OSError:
        pass
    else:
        raise AssertionError("Application source must be read-only")
assert os.getuid() == 10001
print("PASS: no-key startup, safe 503, origin protection, secret loading and non-root/read-only filesystem")
