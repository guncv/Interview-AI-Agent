import jwt
from internal.config.config import nested_config as config
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.utils.exception import InterviewSimulationException
from internal.infra.log.logger import logger
from jwt.exceptions import InvalidTokenError

class JWTToken:
    def __init__(self, algorithm: str = "HS256"):
        self.secret_key = config["session"]["query_param_secret_key"]
        if not self.secret_key:
            logger.error(f"[JWTToken: __init__] session query param secret key not found in configuration")
            raise ValueError("session query param secret key not found in configuration")
        self.algorithm = algorithm

    def verify_token(self, token: str):
        try:
            if not token:
                logger.error(f"[JWTToken: verify_token] Token is empty or None")
                raise InterviewSimulationException(error_code=InterviewSimulationErrorCodes.TOKEN_EXPIRED)
            
            logger.info(f"[JWTToken: verify_token] Verifying token: {token}")
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            logger.info(f"[JWTToken: verify_token] Token verified: {payload}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.error(f"[JWTToken: verify_token] Token expired")
            raise InterviewSimulationException(error_code=InterviewSimulationErrorCodes.TOKEN_EXPIRED)
        except InvalidTokenError as e:
            logger.error(f"[JWTToken: verify_token] Invalid token: {e}")
            raise InterviewSimulationException(error_code=InterviewSimulationErrorCodes.TOKEN_EXPIRED)
        except Exception as e:
            logger.error(f"[JWTToken: verify_token] Unexpected error: {e}")
            raise InterviewSimulationException(error_code=InterviewSimulationErrorCodes.TOKEN_EXPIRED)

  