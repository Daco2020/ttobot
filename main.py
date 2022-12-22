import datetime
import re
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from sheet import write_worksheet

BOT_TOKEN = "BOT_TOKEN"
APP_TOKEN = "APP_TOKEN"
app = App(token=BOT_TOKEN)


@app.message("!제출")
def say_hello(message, say, client, body, ack, shortcut):
    user = message["user"]
    # say(f"Hi there, <@{user}>!")

    say(
        blocks=[
            {
                "type": "section",
                "text": {"type": "plain_text", "text": "내가 도와줄게 제출 버튼을 눌러줘:wave:"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "제출"},
                    "action_id": "button_click",
                },
            }
        ]
    )


@app.message("!패스")
def say_hello(message, say, client, body, ack, shortcut):
    user = message["user"]
    # say(f"Hi there, <@{user}>!")

    say(
        blocks=[
            {
                "type": "section",
                "text": {"type": "plain_text", "text": "정말로 패스 한다면 버튼을 눌러줘:wave:"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "패스"},
                    "action_id": "button_click",
                },
            }
        ]
    )


@app.event("app_mention")  # 앱을 언급했을 때
def who_am_i(event, client, message, say):
    say(
        blocks=[
            {
                "type": "section",
                "text": {"type": "plain_text", "text": "내가 도와줄게 제출 버튼을 눌러줘:wave:"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "제출"},
                    "action_id": "button_click",
                },
            },
            {
                "type": "section",
                "text": {"type": "plain_text", "text": "정말로 패스 한다면 버튼을 눌러줘:wave:"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "패스"},
                    "action_id": "button_click",
                },
            },
        ],
    )


@app.action("button_click")
def action_button_click(body, ack, client):
    # Acknowledge the action
    ack()
    # Call views_open with the built-in client
    res = client.views_open(
        # Pass a valid trigger_id within 3 seconds of receiving it
        trigger_id=body["trigger_id"],
        # View payload
        view={
            "type": "modal",
            "private_metadata": body["channel"]["id"],
            # View identifier
            "callback_id": "view_1",
            "title": {"type": "plain_text", "text": "글똥이"},
            "submit": {"type": "plain_text", "text": "제출"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "section678",
                    "text": {
                        "type": "mrkdwn",
                        "text": "글 쓰느라 고생 많았어~!",
                    },
                },
                {
                    "type": "input",
                    "block_id": "input_c",
                    "label": {
                        "type": "plain_text",
                        "text": "글 링크",
                    },
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "dreamy_input",
                        "multiline": False,
                    },
                },
            ],
        },
    )


@app.view("view_1")
def handle_submission(ack, body, client, view, logger, say):
    # Assume there's an input block with `input_c` as the block_id and `dreamy_input`
    hopes_and_dreams = view["state"]["values"]["input_c"]["dreamy_input"]["value"]
    # channal = view["state"]["values"]["section678"]["text1234"]["selected_channel"]
    channal = view["private_metadata"]
    user = body["user"]["id"]

    # Validate the inputs
    errors = {}
    if hopes_and_dreams is not None and len(hopes_and_dreams) <= 5:
        errors["input_c"] = "The value must be longer than 5 characters"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return
    # Acknowledge the view_submission request and close the modal
    ack()
    # Do whatever you want with the input data - here we're saving it to a DB
    # then sending the user a verification of their submission

    # Message to send user
    msg = ""
    try:
        # TODO: 스프레드 시트에 저장하기
        # TODO: 문구 수정하기 (유저 본인 호출 포함)
        now_dt = datetime.datetime.now()
        dt = datetime.datetime.strftime(now_dt, "%Y-%m-%d %H:%M:%S")
        write_worksheet(hopes_and_dreams, "임시카테고리", dt)
        msg = f"글 제출 완료!\n{hopes_and_dreams}"
    except Exception as e:
        # Handle error
        raise ValueError(str(e))

    # Message the user
    try:
        client.chat_postMessage(channel=channal, text=msg)
    except e:
        logger.exception(f"Failed to post a message {e}")


# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, APP_TOKEN).start()
