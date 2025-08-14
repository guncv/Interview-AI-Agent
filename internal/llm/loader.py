from internal.config.config import nested_config as config
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from internal.infra.log.logger import logger
from internal.llm.state_store import getMemory

def loadLLM():
    if config["llm"]["provider"] == "openai":
        from langchain_openai import ChatOpenAI
        logger.info(f"[loadLLM: Called]: {config['llm']['model']}")
        return ChatOpenAI(
            openai_api_key=config["llm"]["api_key"],
            model=config["llm"]["model"],
            temperature=config["llm"]["temperature"],
            max_tokens=config["llm"]["max_tokens"],
        )
    elif config["llm"]["provider"] == "deepseek":
        from langchain_deepseek import ChatDeepSeek
        logger.info(f"[loadLLM: Called]: {config['llm']['model']}")
        return ChatDeepSeek(
            api_key=config["llm"]["api_key"],
            model=config["llm"]["model"],
            temperature=config["llm"]["temperature"],
            max_tokens=config["llm"]["max_tokens"],
        )
    elif config["llm"]["provider"] == "anthropic":
        from langchain_anthropic import ChatAnthropic
        logger.info(f"[loadLLM: Called]: {config['llm']['model']}")
        return ChatAnthropic(
            anthropic_api_key=config["llm"]["api_key"],
            model=config["llm"]["model"],
            temperature=config["llm"]["temperature"],
            max_tokens=config["llm"]["max_tokens"],
        )
    else:
        raise ValueError("Unsupported LLM provider")

llm = loadLLM()

prompt = ChatPromptTemplate.from_messages([
    ("system", "{task_prompt}"),
    MessagesPlaceholder("history"),
    ("human", "{input}"),
])

def getChatHistory(session_id: str) -> ChatMessageHistory:
    logger.info(f"[getChatHistory: Called]: {session_id}")
    memory: ChatMessageHistory = getMemory(session_id)
    return memory