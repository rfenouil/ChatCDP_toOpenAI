import os
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHAT2OPENAI_")

    host: str = "127.0.0.1"
    port: int = 8080
    api_token: str = ""
    chrome_path: str = os.path.expanduser(
        "~/.cache/ms-playwright/chromium-1254/chrome-linux64/chrome"
    )
    chat_url: str = "file://" + os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chat.html"
    )
    debug_port: int = 9333
    chrome_ld_library_path: str = "/tmp/libs/usr/lib/x86_64-linux-gnu:/tmp/libs/usr/lib"
    chrome_fontconfig_file: str = "/tmp/fontconfig/fonts.conf"

    def effective_token(self) -> str:
        if self.api_token:
            return self.api_token
        return secrets.token_urlsafe(24)
