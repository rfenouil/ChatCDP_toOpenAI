import click
import uvicorn

from chat2openai import __version__
from chat2openai.config import Settings
from chat2openai.server import create_app


@click.group()
@click.version_option(version=__version__, prog_name="chat2openai")
def main():
    pass


@main.command()
@click.option("--host", envvar="CHAT2OPENAI_HOST", default=None, help="Adresse d'ecoute (defaut 127.0.0.1)")
@click.option("--port", envvar="CHAT2OPENAI_PORT", default=None, type=int, help="Port HTTP (defaut 8080)")
@click.option("--chat-url", envvar="CHAT2OPENAI_CHAT_URL", default=None, help="URL du chat pilote par CDP")
@click.option("--token", envvar="CHAT2OPENAI_API_TOKEN", default=None, help="Bearer token requis (genere sinon)")
def serve(host, port, chat_url, token):
    settings = Settings()
    if host:
        settings.host = host
    if port:
        settings.port = port
    if chat_url:
        settings.chat_url = chat_url
    if token:
        settings.api_token = token
    app = create_app(settings)
    click.echo(f"chat2openai {__version__} sur http://{settings.host}:{settings.port}")
    click.echo(f"Bearer token: {app.state.token}")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
