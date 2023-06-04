from __future__ import print_function
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import base64
import openai
import urllib.parse
import urllib.request
from dotenv import load_dotenv
load_dotenv()
os.getenv('OPENAI_API_KEY')

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
LINE_NOTIFY_API = "https://notify-api.line.me/api/notify"
LINE_ACCESS_TOKEN = os.environ["LINE_ACCESS_TOKEN"]
NO_SUMMARY_MSG = '本日のSummaryはありませんでした'

def handler(event, context):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # 認証されていない、認証の有効期限がきれている場合は、再度作成
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # 次回以降の実行のために認証情報を保存
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        today = datetime.today().date()
        # 直近1日の受信メールが取得対象
        day_ago = today - timedelta(days=1)
        start_date = day_ago.strftime("%Y/%m/%d")

        # メールの検索クエリを構築
        query = f'from:"TLDR WEB DEV" is:unread after:{start_date}'

        # メールを検索
        response = service.users().messages().list(userId='me', q=query).execute()
        messages = response.get('messages', [])

        # メッセージがない場合、そのことをLINE通知
        if (len(messages) == 0):
            notify_to_line()
            return

        for message in messages:
            message_id = message['id']
            msg = service.users().messages().get(
                userId='me', id=message_id, format='full').execute()

            if 'parts' in msg['payload']:
                parts = msg['payload']['parts']
                for part in parts:
                    if part['mimeType'] == 'text/plain':
                        data = part['body']['data']
                        # base64エンコードされた本文をデコードする
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        # 必要な文章を抽出
                        body = body.split('🧑‍💻')[1].split('🎁')[0]

            elif 'body' in msg['payload']:
                data = msg['payload']['body']['data']
                body = base64.urlsafe_b64decode(data).decode('utf-8')
        message = get_summary(body)
        notify_to_line(message)

    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')

# Summary生成
def get_summary(text):
    system = """与えられたテキストについて、各項目（'ARTICLES & TUTORIALS','OPINIONS & ADVICE','LAUNCHES & TOOLS'）、
    それぞれについて、100文字程度で要点して、以下のフォーマットで日本に訳して出力してください。
    各項目で取得できるURL情報も合わせて返してください。
    ・ARTICLES & TUTORIALSの内容
        ・まとめた内容[URL]
    ・OPINIONS & ADVICEの内容
        ・まとめた内容[URL]
    ・LAUNCHES & TOOLSの内容
        ・まとめた内容[URL]
    ```"""

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': text}
        ],
        temperature=0.01,
    )
    summary = response['choices'][0]['message']['content']
    # calc cost
    tokens = response["usage"]["total_tokens"]
    cost = (float(tokens)/1000*0.02)
    title, *body = summary.split('\n')
    body = '\n'.join(body)
    message = f"{title}\n{body}\n\nAPI Call Cost:{cost}"
    return message

# LINE通知
def notify_to_line(message:str=NO_SUMMARY_MSG):
    method = "POST"
    headers = {"Authorization": "Bearer " + LINE_ACCESS_TOKEN}
    contents = []
    # Summaryの有無で通知内容を切り替え
    if(message != NO_SUMMARY_MSG):
        # Topicごとに文章を分割
        articles_tutorials = '\n' + message.split('OPINIONS & ADVICE')[0]
        opinions_advice = '\nOPINIONS & ADVICE\n' + message.split('OPINIONS & ADVICE')[1].split('LAUNCHES & TOOLS')[0]
        launches_tools = '\nLAUNCHES & TOOLS\n' + message.split('OPINIONS & ADVICE')[1].split('LAUNCHES & TOOLS')[1].split('API Call Cost:')[0]
        # コスト通知
        cost = '\nAPI Call Cost : $' + message.split('API Call Cost:')[1]
        contents += [articles_tutorials, opinions_advice, launches_tools, cost]
    else:
        contents.append('\n' + message)

    try:
        for content in contents:
            payload = {"message": content}
            payload = urllib.parse.urlencode(payload).encode("utf-8")
            req = urllib.request.Request(
                LINE_NOTIFY_API, data=payload, method=method, headers=headers)
            urllib.request.urlopen(req)
        print('Success Notify')
        return message
    except Exception as e:
        return e
