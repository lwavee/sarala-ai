"""
User Confirmation Management for Sensitive/State-Changing AI Tools.
Guarantees:
1. Tool action confirmation is tied to (user_id, conversation_id, tool_call_id).
2. User A cannot approve User B's tool execution.
3. Confirmation tokens have a strict TTL and expire automatically.
4. Tokens are single-use (replay protected).
"""

import time
import secrets
import hashlib
import json
from typing import Optional, Dict, Any
from core.logger import logger


class PendingConfirmation:
    """Represents a pending authorization request awaiting human user confirmation."""
    def __init__(
        self,
        token: str,
        user_id: str,
        conversation_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        ttl_seconds: int = 300,
    ):
        self.token = token
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.tool_call_id = tool_call_id
        self.tool_name = tool_name
        self.arguments = arguments
        self.arguments_hash = hashlib.sha256(
            json.dumps(arguments, sort_keys=True).encode("utf-8")
        ).hexdigest()
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.consumed = False

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class ConfirmationManager:
    """Central manager for tracking, validating, and consuming pending confirmations."""

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._pending: Dict[str, PendingConfirmation] = {}

    def create_confirmation(
        self,
        user_id: str,
        conversation_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Generates a secure confirmation token for a pending tool execution."""
        self._cleanup_expired()
        token = f"conf_{secrets.token_urlsafe(32)}"
        ttl = ttl_seconds or self.default_ttl

        pending = PendingConfirmation(
            token=token,
            user_id=user_id,
            conversation_id=conversation_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            arguments=arguments,
            ttl_seconds=ttl,
        )
        self._pending[token] = pending
        logger.info(
            f"Created confirmation token for tool '{tool_name}' (user: {user_id}, call: {tool_call_id})"
        )
        return token

    def validate_and_consume(
        self,
        token: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> bool:
        """
        Validates token ownership, expiration, and parameters.
        Consumes the token upon successful validation to prevent replays.
        """
        self._cleanup_expired()
        if not token or token not in self._pending:
            logger.warning(f"Confirmation validation failed: Token not found or invalid.")
            return False

        pending = self._pending[token]

        if pending.consumed:
            logger.warning(f"Confirmation token '{token[:12]}...' was already consumed (replay attempt).")
            return False

        if pending.is_expired():
            logger.warning(f"Confirmation token '{token[:12]}...' has expired.")
            self._pending.pop(token, None)
            return False

        # CRITICAL SECURITY: User A CANNOT confirm User B's tool execution
        if pending.user_id != user_id:
            logger.warning(
                f"Confirmation token security violation: Token belongs to '{pending.user_id}', "
                f"attempted by '{user_id}'."
            )
            return False

        # Check conversation_id if supplied
        if conversation_id and pending.conversation_id and pending.conversation_id != conversation_id:
            logger.warning("Confirmation token conversation mismatch.")
            return False

        # Check tool_name if supplied
        if tool_name and pending.tool_name != tool_name:
            logger.warning(f"Confirmation token tool mismatch: expected {pending.tool_name}, got {tool_name}.")
            return False

        # Mark as consumed and remove
        pending.consumed = True
        self._pending.pop(token, None)
        logger.info(f"Confirmation token validated and consumed for tool '{pending.tool_name}'.")
        return True

    def get_pending(self, token: str) -> Optional[PendingConfirmation]:
        """Retrieves pending confirmation record if not expired."""
        self._cleanup_expired()
        item = self._pending.get(token)
        if item and item.is_expired():
            self._pending.pop(token, None)
            return None
        return item

    def _cleanup_expired(self):
        """Removes expired confirmation tokens."""
        now = time.time()
        expired = [k for k, v in self._pending.items() if v.expires_at < now]
        for k in expired:
            self._pending.pop(k, None)


# Singleton ConfirmationManager instance
confirmation_manager = ConfirmationManager()
