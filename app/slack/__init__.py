from app.config import PASS_VIEW, SUBMIT_VIEW, settings
from slack_bolt.async_app import AsyncApp

from app.slack import contents, core, community


app = AsyncApp(token=settings.BOT_TOKEN)


@app.middleware
async def middleware(req, resp, next):
    await next()


@app.event("message")
async def handle_message_event(ack, body) -> None:
    await ack()


# community
app.command("/모코숲")(community.guide_command)
app.event("member_joined_channel")(community.send_welcome_message)

# contents
app.command("/제출")(contents.submit_command)
app.view(SUBMIT_VIEW)(contents.submit_view)
app.action("intro_modal")(contents.open_intro_modal)
app.action("contents_modal")(contents.contents_modal)
app.action("bookmark_modal")(contents.bookmark_modal)
app.view("bookmark_view")(contents.bookmark_view)
app.command("/패스")(contents.pass_command)
app.view(PASS_VIEW)(contents.pass_view)
app.command("/검색")(contents.search_command)
app.view("submit_search")(contents.submit_search)
app.view("back_to_search_view")(contents.back_to_search_view)
app.command("/북마크")(contents.bookmark_command)
app.view("bookmark_search_view")(contents.bookmark_search_view)
app.action("bookmark_overflow_action")(contents.open_overflow_action)
app.view("bookmark_submit_search_view")(contents.bookmark_submit_search_view)

# core
app.command("/예치금")(core.get_deposit)
app.command("/제출내역")(core.history_command)
app.command("/관리자")(core.admin_command)
