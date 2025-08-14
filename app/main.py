from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from internal.config.config import api_config
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from prometheus_fastapi_instrumentator import Instrumentator
from internal.utils.except_handler import validation_exception_handler, response_validation_exception_handler
from internal.api.route import api_router_v1
from internal.infra.log.logger import logger

app = FastAPI(
    title=api_config.get("API_TITLE", "Interview Simulation API"),
    version=api_config.get("API_VERSION", "1.0.0"),
    docs_url=api_config.get("API_PREFIX", "/api/v1")+'/docs',
    openapi_url=api_config.get("API_PREFIX", "/api/v1")+'/openapi.json'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router_v1, prefix=api_config.get("API_PREFIX", "/api/v1"))

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ResponseValidationError, response_validation_exception_handler)

instrumentator = Instrumentator(
    should_group_status_codes = False,
    should_ignore_untemplated = True,
    should_respect_env_var = True,
    should_instrument_requests_inprogress = True,
    excluded_handlers = ["/metrics","/api/docs"],
    env_var_name = "ENABLE_METRICS",
    inprogress_name = "inprogress",
    inprogress_labels = True,
)

instrumentator.instrument(app).expose(app, include_in_schema=False)