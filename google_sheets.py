import gspread
from google.oauth2.service_account import Credentials

def get_gsheet_client(json_key_path: str):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(json_key_path, scopes=scopes)
    return gspread.authorize(credentials)

def write_rows_to_sheet(sheet_id: str, worksheet_name: str, rows: list, json_key_path: str):
    client = get_gsheet_client(json_key_path)
    sheet = client.open_by_key(sheet_id)

    try:
        worksheet = sheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=worksheet_name, rows="1000", cols="20")

    existing_data = worksheet.get_all_values()

    data_dict = {}
    for row in rows:
        if isinstance(row, list) and len(row) == 2:
            key, value = row
            key = key.strip() or "Unnamed"
            data_dict[key] = str(value).strip() if value else ""

    if not existing_data:
        # Priority columns for new worksheets
        priority_columns = ["Weigh Scale Load Slip #", "Date In", "Gross", "Tare", "Net", "Truck"]
        headers = [col for col in priority_columns if col in data_dict]
        remaining_cols = [col for col in data_dict.keys() if col not in priority_columns]
        headers.extend(remaining_cols)
        
        worksheet.append_row(headers)
        worksheet.append_row([data_dict.get(h, "") for h in headers])
    else:
        headers = existing_data[0]
        new_keys = [k for k in data_dict.keys() if k not in headers]
        if new_keys:
            headers.extend(new_keys)
            worksheet.update('A1', [headers])

        new_row = [data_dict.get(h, "") for h in headers]
        worksheet.append_row(new_row)