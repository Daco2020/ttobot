import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

json_file_name = "json_file_name"

credentials = ServiceAccountCredentials.from_json_keyfile_name(json_file_name, scope)
gc = gspread.authorize(credentials)

spreadsheet_url = "spreadsheet_url"

doc = gc.open_by_url(spreadsheet_url)
worksheet = doc.worksheet("시트1")


def write_worksheet(link, category, dt):
    values_list = worksheet.get_all_values()
    i = len(values_list) + 1
    worksheet.update(f"A{i}", [[link, category, dt]])
