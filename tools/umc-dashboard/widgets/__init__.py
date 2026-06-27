"""Dashboard widgets."""
from .agent_grid import AgentGrid
from .backlog_board import BacklogBoard
from .inbox_timeline import InboxTimeline
from .candidate_queue import CandidateQueue
from .worker_console import WorkerConsole
from .resource_strip import ResourceStrip

__all__ = ["AgentGrid", "BacklogBoard", "InboxTimeline", "CandidateQueue",
           "WorkerConsole", "ResourceStrip"]
