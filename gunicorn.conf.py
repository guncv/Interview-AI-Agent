import logging

from gunicorn import glogging

class CustomGunicornLogger(glogging.Logger):
    def setup(self, cfg):
        super().setup(cfg)
        logger = logging.getLogger("uvicorn.access")
        logger.addFilter(PrometheusMetricsFilter())

# We need this to disable metrics logging in gunicorn console
class PrometheusMetricsFilter(logging.Filter):
    def filter(self, record):
        return 'GET /metrics' not in record.getMessage()

workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
bind = "0.0.0.0:8000"
forwarded_allow_ips = "*"
accesslog = "-"
logger_class = CustomGunicornLogger