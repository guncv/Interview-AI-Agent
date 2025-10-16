import asyncio
import json
from redis.asyncio import Redis
from core.log.logger import logger
from core.config.config import nested_config as config
from domain.models.interview import InterviewTaskType
from services.interview import InterviewService
from domain.enums.queue import QueueName

class TaskConsumer:
    def __init__(self):
        self.service = InterviewService()
        self.redis = Redis.from_url(config["redis"]["url"])

    async def consume_tasks(self):
        while True:
            try:
                result = await self.redis.blpop(QueueName.AI_AGENT, timeout=5)

                if result is None:
                    continue

                _, raw = result
                task_data = json.loads(raw)

                task_type = task_data.get("type")
                payload = task_data.get("payload")

                if task_type == InterviewTaskType.EXTRACT_BIAS_PROMPT_AND_RESUME_CONTEXT:
                    await self.service.generate_bias_prompt_and_context(payload)
                else:
                    logger.warning(f"[CONSUMER] Unknown task type: {task_type}")
                    continue


            except Exception as e:
                logger.exception(f"[CONSUMER] Error processing task: {e}")
                await asyncio.sleep(1)
