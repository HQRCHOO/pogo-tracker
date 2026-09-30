"""Read and overwrite dashboard.json in Google Drive (or a local file for testing)."""
import io
import json
import os

_drive = None


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
    raw = _svc().files().get_media(fileId=os.environ["GDRIVE_FILE_ID"]).execute()
    return json.loads(raw or b"{}")


def write_dashboard(data):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if _local():
        with open(_local(), "wb") as f:
            f.write(body)
        return len(body)
    from googleapiclient.http import MediaIoBaseUpload
    media = MediaIoBaseUpload(io.BytesIO(body), mimetype="application/json", resumable=False)
    _svc().files().update(fileId=os.environ["GDRIVE_FILE_ID"], media_body=media).execute()
    return len(body)
