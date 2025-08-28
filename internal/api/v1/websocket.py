from fastapi import APIRouter, WebSocket, Depends, HTTPException, Query
from internal.infra.websocket.server import ws_server
from internal.infra.log.logger import logger
from internal.utils.jwt_token import JWTToken

router = APIRouter()
jwt_token = JWTToken()

async def get_websocket_params(
    token: str = Query(..., description="Token for encrypt session and user"),
) -> dict:
    logger.info(f"[Websocket: get_websocket_params] Token: {token}")
    if not token:
        logger.error(f"[Websocket: get_websocket_params] Missing required parameters")
        raise HTTPException(status_code=400, detail="Missing required parameters")

    logger.info(f"[Websocket: get_websocket_params] Verifying token")
    payload = jwt_token.verify_token(token)
    logger.info(f"[Websocket: get_websocket_params] Payload: {payload}")

    return {
        "user_id": payload["user_id"],
        "session_id": payload["session_id"],
    }

@router.websocket("/connect")
async def websocket_endpoint(websocket: WebSocket, params: dict = Depends(get_websocket_params)):
    logger.info(f"[Websocket: connect] Starting connection with params: {params}")

    try:
        client = await ws_server.connect(websocket, params["user_id"], params["session_id"])
        await ws_server.serve(client)
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass