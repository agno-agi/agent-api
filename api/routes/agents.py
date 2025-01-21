from typing import Generator, Optional, List, Dict, Any

from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from agno.agent import Agent
from agno.storage.agent.session import AgentSession

from api.routes.endpoints import endpoints
from agents.example import get_example_agent, agent_storage
from utils.log import logger

######################################################
## Router for Serving Agents
######################################################

agents_router = APIRouter(prefix=endpoints.AGENTS, tags=["Agents"])


def get_agent(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
):
    """Return the agent"""

    return get_example_agent(session_id=session_id, user_id=user_id)


class LoadKnowledgeBaseRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None


@agents_router.post("/load-knowledge-base")
def load_knowledge_base(body: LoadKnowledgeBaseRequest):
    """Loads the knowledge base for an Agent"""

    agent = get_agent(session_id=body.session_id, user_id=body.user_id)
    if agent.knowledge:
        agent.knowledge.load(recreate=False)
    return {"message": "Knowledge Base Loaded"}


def chat_response_streamer(agent: Agent, message: str) -> Generator:
    for chunk in agent.run(message, stream=True):
        # Ideally we would yield chunk
        yield chunk.content


class ChatRequest(BaseModel):
    message: str
    stream: bool = True
    session_id: Optional[str] = None
    user_id: Optional[str] = None


@agents_router.post("/chat")
def chat(body: ChatRequest):
    """Sends a message to an Agent and returns the response"""

    logger.debug(f"ChatRequest: {body}")
    agent: Agent = get_agent(session_id=body.session_id, user_id=body.user_id)

    if body.stream:
        return StreamingResponse(
            chat_response_streamer(agent, body.message),
            media_type="text/event-stream",
        )
    else:
        response = agent.run(body.message, stream=False)
        # Ideally we would return response
        return response.content


class ChatHistoryRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None


@agents_router.post("/history", response_model=List[Dict[str, Any]])
def get_chat_history(body: ChatHistoryRequest):
    """Return the chat history for an Agent run"""

    logger.debug(f"ChatHistoryRequest: {body}")
    agent: Agent = get_agent(session_id=body.session_id, user_id=body.user_id)
    # Load the agent from the database
    agent.read_from_storage()

    return agent.memory.get_messages()


class GetAgentRunRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None


@agents_router.post("/get", response_model=Optional[AgentSession])
def get_agent_run(body: GetAgentRunRequest):
    """Returns the Agent run"""

    logger.debug(f"GetAgentRunRequest: {body}")
    agent: Agent = get_agent(session_id=body.session_id, user_id=body.user_id)

    return agent.read_from_storage()


class GetAllAgentSessionsRequest(BaseModel):
    user_id: str


@agents_router.post("/get-all", response_model=List[AgentSession])
def get_agents(body: GetAllAgentSessionsRequest):
    """Return all Agent sessions for a user"""

    logger.debug(f"GetAllAgentSessionsRequest: {body}")
    return agent_storage.get_all_sessions(user_id=body.user_id)


class GetAllAgentSessionIdsRequest(BaseModel):
    user_id: str


@agents_router.post("/get-all-ids", response_model=List[str])
def get_session_ids(body: GetAllAgentSessionIdsRequest):
    """Return all session_ids for a user"""

    logger.debug(f"GetAllAgentSessionIdsRequest: {body}")
    return agent_storage.get_all_session_ids(user_id=body.user_id)


class RenameAgentRequest(BaseModel):
    session_id: str
    agent_name: str
    user_id: Optional[str] = None


class RenameAgentResponse(BaseModel):
    session_id: str
    agent_name: str


@agents_router.post("/rename_agent", response_model=RenameAgentResponse)
def rename_agent(body: RenameAgentRequest):
    """Rename an Agent"""

    logger.debug(f"RenameAgentRequest: {body}")
    agent: Agent = get_agent(session_id=body.session_id, user_id=body.user_id)
    agent.rename(name=body.agent_name)

    return RenameAgentResponse(
        session_id=agent.session_id,
        agent_name=agent.name,
    )


class RenameAgentSessionRequest(BaseModel):
    session_id: str
    session_name: str
    user_id: Optional[str] = None


class RenameAgentSessionResponse(BaseModel):
    session_id: str
    session_name: str


@agents_router.post("/rename_session", response_model=RenameAgentSessionResponse)
def rename_agent_session(body: RenameAgentSessionRequest):
    """Rename an Agent Session"""

    logger.debug(f"RenameAgentSessionRequest: {body}")
    agent: Agent = get_agent(session_id=body.session_id, user_id=body.user_id)
    agent.rename_session(session_name=body.session_name)

    return RenameAgentSessionResponse(
        session_id=agent.session_id,
        session_name=agent.session_name,
    )


class AutoRenameAgentSessionRequest(BaseModel):
    session_id: str
    user_id: Optional[str] = None


class AutoRenameAgentSessionResponse(BaseModel):
    session_id: str
    session_name: str


@agents_router.post("/auto_rename_session", response_model=AutoRenameAgentSessionResponse)
def auto_rename_agent_session(body: AutoRenameAgentSessionRequest):
    """Rename a agent session using the LLM"""

    logger.debug(f"AutoRenameAgentSessionRequest: {body}")
    agent: Agent = get_agent(session_id=body.session_id, user_id=body.user_id)
    agent.auto_rename_session()

    return AutoRenameAgentSessionResponse(
        session_id=agent.session_id,
        session_name=agent.session_name,
    )
