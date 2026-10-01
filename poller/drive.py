"""Read and overwrite dashboard.json in Google Drive (or a local file for testing)."""
import io
import json
import os

_drive = None
RETRY_WAITS = (5, 15, 30)   # seconds between attempts: Google's 5xx pages say "try again in 30 seconds"


def _retry(fn, what):
    """Run fn(); on a temporary Google / network error, wait and try again (4 attempts in all)."""
    import time
    for i, wait in enumerate(RETRY_WAITS + (None,)):
        try:
            return fn()
        except Exception as e:
            status = getattr(getattr(e, "resp", None), "status", None)
            temporary = (status is not None and int(status) in (429, 500, 502, 503, 504)) or \
                type(e).__name__ in ("TimeoutError", "ConnectionError", "ConnectionResetError", "socket.timeout",
                                     "timeout", "ServerNotFoundError", "SSLError", "RemoteDisconnected", "BrokenPipeError")
            if not temporary or wait is None:
                raise
            print(f"drive: {what} failed ({status or type(e).__name__}); retrying in {wait}s ({i + 1}/{len(RETRY_WAITS)})")
            time.sleep(wait)


def _local():
    return os.environ.get("LOCAL_DASHBOARD")  # a file path: skip Drive (testing)


def _svc():
    global _drive
    if _drive is None:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["GDRIVE_SA_JSON"]),
            scopes=["https://www.googleapis.com/auth/drive"])
        _drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _drive


def read_dashboard():
    if _local():
        try:
            with open(_local(), encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
    raw = _retry(lambda: _svc().files().get_media(fileId=os.environ["GDRIVE_FILE_ID"]).execute(), "read")
    return json.loads(raw or b"{}")


def write_dashboard(data):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if _local():
        with open(_local(), "wb") as f:
            f.write(body)
        return len(body)
    from googleapiclient.http import MediaIoBaseUpload
    def upload():
        media = MediaIoBaseUpload(io.BytesIO(body), mimetype="application/json", resumable=False)
        return _svc().files().update(fileId=os.environ["GDRIVE_FILE_ID"], media_body=media).execute()
    _retry(upload, "save")
    return len(body)
