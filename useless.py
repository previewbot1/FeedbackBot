from aiohttp import web
import os
from dotenv import load_dotenv

load_dotenv('config.env')

routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    
    return web.json_response(os.getenv("WEB_RESPONSE", "nxmirror"))

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app

if __name__ == "__main__":

    port = int(os.getenv("PORT", 8008)) 
    web.run_app(web_server(), port=port)
