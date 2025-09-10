from fastapi import APIRouter

from internal.api import interview, websocket, feedback_and_score

api_router_v1 = APIRouter()

api_router_v1.include_router(interview.router, prefix="/interview", tags=["Interview"])
api_router_v1.include_router(feedback_and_score.router, prefix="/feedback-and-score", tags=["Feedback and Score"])
api_router_v1.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])