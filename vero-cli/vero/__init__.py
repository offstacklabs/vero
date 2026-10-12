"""
Vero: Open-Source Headless Analytics Agent Framework & AI Data Workspace
"""

__version__ = "0.1.0"

from vero.agent import VeroAgent
from vero.config import VeroConfig
from vero.context import ContextEngine
from vero.db import DatabaseManager
from vero.auth import AuthManager, User
from vero.server import app

__all__ = [
    "VeroAgent",
    "VeroConfig",
    "ContextEngine",
    "DatabaseManager",
    "AuthManager",
    "User",
    "app",
    "__version__",
]
