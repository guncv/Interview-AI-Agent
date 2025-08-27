from fastapi import APIRouter

from internal.api.v1 import interview, websocket

api_router_v1 = APIRouter()

api_router_v1.include_router(interview.router, prefix="/interview", tags=["Interview"])
api_router_v1.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])