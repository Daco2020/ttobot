from app.config import settings
from slack_bolt.async_app import AsyncApp


app = AsyncApp(token=settings.BOT_TOKEN)
