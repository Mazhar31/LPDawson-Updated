from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import mimetypes
import io

def upload_file_to_drive(file_bytes: bytes, filename: str, mimetype: str, json_key_path: str, parent_folder_id: str = None):
    scopes = ['https://www.googleapis.com/auth/drive']
    credentials = Credentials.from_service_account_file(json_key_path, scopes=scopes)
    service = build('drive', 'v3', credentials=credentials)

    file_metadata = {'name': filename}
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    # Make file publicly viewable
    service.permissions().create(
        fileId=file['id'],
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return file.get('id'), file.get('webViewLink')