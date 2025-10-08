from internal.config.config import nested_config as config
from langchain_core.prompts import ChatPromptTemplate
from internal.adapters.log.logger import logger
from internal.adapters.llm.state_store import getMemory
from langchain_community.chat_message_histories import ChatMessageHistory

class LLM:
    def __init__(self):
        self.model = None
        self.provider = None
        self.temperature = None
        self.api_key = None

    def loadLLM(self, type: str):
        self.model = config[type]["model"]
        self.provider = config[type]["api_provider"]
        self.temperature = config[type]["temperature"]
        self.api_key = config[type]["api_key"]

        if type == "transcribe":
            if self.provider == "openai":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    openai_api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
            elif self.provider == "deepseek":
                from langchain_deepseek import ChatDeepSeek
                return ChatDeepSeek(
                    api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
            elif self.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    anthropic_api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
        elif type == "extract_resume":
            if self.provider == "openai":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    openai_api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
        elif type == "interview":
            if self.provider == "openai":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    openai_api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
            elif self.provider == "deepseek":
                from langchain_deepseek import ChatDeepSeek
                return ChatDeepSeek(
                    api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
            elif self.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    anthropic_api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
        elif type == "example_question":
            if self.provider == "openai":
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    openai_api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
            elif self.provider == "deepseek":
                from langchain_deepseek import ChatDeepSeek
                return ChatDeepSeek(
                    api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
            elif self.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    anthropic_api_key=self.api_key,
                    model=self.model,
                    temperature=self.temperature,
                )
        else:
            raise ValueError("Unsupported LLM provider")
    
    def get_llm_model(self):
        return self.model

def getChatHistory(session_id: str) -> ChatMessageHistory:
    memory: ChatMessageHistory = getMemory(session_id)
    return memory

llm = LLM()
def loadLLM(type: str):
    return llm.loadLLM(type)

def getLLMModel():
    return llm.get_llm_model()

prompt = ChatPromptTemplate.from_messages([
    ("system", "{task_prompt}"),
    ("human", "{input}"),
])