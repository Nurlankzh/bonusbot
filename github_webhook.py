from aiohttp import web
import database as db
import config

async def handle_github_push(request):
    data = await request.json()
    repo_url = data.get('repository', {}).get('clone_url')
    # Бұл жерде repo_url бойынша базадан ботты тауып, 
    # git pull жасап, runner арқылы қайта deploy жасау логикасы болады.
    # Бұл нағыз CI/CD жүйесі.
    return web.Response(text="Webhook received")

def get_webhook_app():
    app = web.Application()
    app.router.add_post('/webhook/github', handle_github_push)
    return app

