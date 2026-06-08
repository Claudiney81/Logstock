from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/drive.file"
]

flow = InstalledAppFlow.from_client_secrets_file(
    "google_drive_oauth.json",
    SCOPES
)

creds = flow.run_local_server(
    port=0
)

with open("token_drive.json", "w") as token:
    token.write(creds.to_json())

print("Token gerado com sucesso: token_drive.json")