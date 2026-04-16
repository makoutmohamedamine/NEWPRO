from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_emails():
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret_526147678586-xxxx.json', SCOPES
    )
    creds = flow.run_local_server(port=0)
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])

    print(messages)

if __name__ == "__main__":
    get_emails()