import json
from redis.asyncio import Redis
from core.log.logger import logger
from core.config.config import nested_config as config
from domain.enums.queue import QueueName


class TaskPublisher:
    def __init__(self):
        self.redis = Redis.from_url(config["redis"]["url"])

    async def publish(self, queue_name: QueueName, task_type: str, payload: dict):
        try:
            task_data = {
                "type": task_type,
                "payload": payload
            }
            await self.redis.rpush(queue_name, json.dumps(task_data))
            
        except Exception as e:
            logger.exception(f"[PUBLISHER] Error publishing task: {e}")
            raise

