from fastapi import APIRouter, WebSocket, Depends, HTTPException, Query
from internal.infra.websocket.server import ws_server
from internal.infra.log.logger import logger

router = APIRouter()

async def get_websocket_params(
    user_id: str = Query(..., description="User ID for authentication"),
    session_id: str = Query(..., description="Session ID for the interview"),
) -> dict:
    if not user_id or not session_id:
        raise HTTPException(status_code=400, detail="Missing required parameters")
    
    return {
        "user_id": user_id,
        "session_id": session_id,
    }

@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket, params: dict = Depends(get_websocket_params)):
    logger.info(f"[Websocket: connect] Starting connection with params: {params}")
    logger.info(f"[Websocket: connect] WebSocket object: {websocket}")

    try:
        client = await ws_server.connect(websocket, params["user_id"], params["session_id"])
        await ws_server.serve(client)
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass