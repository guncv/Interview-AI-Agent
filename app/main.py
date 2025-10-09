from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware
from internal.config.config import api_config
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from prometheus_fastapi_instrumentator import Instrumentator
from internal.shared.except_handler import validation_exception_handler, response_validation_exception_handler
from internal.shared.exception import InterviewSimulationException
from internal.api.routes.route import api_router_v1
from internal.adapters.log.logger import logger
from internal.adapters.queue.comsumer import TaskConsumer
import asyncio

app = FastAPI(
    title=api_config.get("API_TITLE", "Interview Simulation API"),
    version=api_config.get("API_VERSION", "1.0.0"),
    docs_url=api_config.get("API_PREFIX", "/api/v1")+'/docs',
    openapi_url=api_config.get("API_PREFIX", "/api/v1")+'/openapi.json'
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router_v1, prefix=api_config.get("API_PREFIX", "/api/v1"))

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ResponseValidationError, response_validation_exception_handler)
app.add_exception_handler(InterviewSimulationException, lambda request, exc: exc.convert_to_JSONResponse())

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

consumer_instance = None

@app.on_event("startup")
async def startup_event():
    global consumer_instance
    consumer_instance = TaskConsumer()
    asyncio.create_task(consumer_instance.consume_tasks())