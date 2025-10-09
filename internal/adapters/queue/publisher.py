import json
from redis.asyncio import Redis
from internal.adapters.log.logger import logger
from internal.config.config import nested_config as config
from internal.domain.enum import QueueName


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

