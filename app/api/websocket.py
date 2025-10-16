from fastapi import APIRouter, WebSocket, Depends, HTTPException, Query
from infrastructure.websocket.server import ws_server
from core.log.logger import logger
from core.utils.jwt_token import JWTToken

router = APIRouter()
jwt_token = JWTToken()

async def get_websocket_params(
    token: str = Query(..., description="Token for encrypt session and user"),
) -> dict:
    if not token:
        logger.error(f"[Websocket: get_websocket_params] Missing required parameters")
        raise HTTPException(status_code=400, detail="Missing required parameters")

    payload = jwt_token.verify_token(token)

    return {
        "user_id": payload["user_id"],
        "resume_id": payload["resume_id"],
        "session_id": payload["session_id"],
        "position": payload["position"],
        "selected_stages": payload["selected_stages"],
    }

@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket, params: dict = Depends(get_websocket_params)):

    try:
        if not params["user_id"] or not params["session_id"] or not params["resume_id"] or not params["position"]:
            logger.error(f"[Websocket: connect] Missing required parameters")
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        client = await ws_server.connect(websocket, params)
        await ws_server.serve(client)
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

