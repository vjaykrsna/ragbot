"""
Optimization module for knowledge synthesis.

This module provides pre-filtering, deduplication, and quality assessment
to reduce API calls while maintaining synthesis quality.
"""

import hashlib
import re
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)


class ConversationOptimizer:
    """Optimizes conversations before synthesis to reduce API costs."""

    def __init__(self):
        # Technical keywords that indicate valuable conversations
        self.technical_keywords = {
            "error",
            "problem",
            "solution",
            "config",
            "setup",
            "help",
            "issue",
            "fix",
            "debug",
            "troubleshoot",
            "install",
            "configure",
            "deploy",
            "build",
            "test",
            "api",
            "database",
            "server",
            "client",
            "auth",
            "token",
            "key",
            "secret",
            "port",
            "host",
            "url",
            "endpoint",
            "docker",
            "kubernetes",
            "container",
            "image",
            "volume",
            "network",
            "service",
            "pod",
            "node",
            "cluster",
            "deployment",
            "ingress",
            "loadbalancer",
            "certificate",
            "ssl",
            "tls",
            "security",
        }

        # Social/greetings to filter out
        self.social_patterns = [
            r"^(hi|hello|hey|good morning|good afternoon|good evening)",
            r"^(thanks|thank you|thx|ty)",
            r"^(bye|goodbye|see you|later)",
            r"^(yes|no|ok|okay|sure|maybe)$",
            r"^(lol|haha|nice|cool|awesome|great)$",
        ]

    def filter_conversations(
        self, conversations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter out low-quality conversations before synthesis.

        Returns: List of conversations that should be processed.
        """
        filtered = []
        total_count = len(conversations)
        kept_count = 0

        for conv in conversations:
            if self._should_process_conversation(conv):
                filtered.append(conv)
                kept_count += 1
            else:
                logger.debug(
                    f"Filtered out conversation: {conv.get('ingestion_hash', 'unknown')}"
                )

        logger.info(
            f"Conversation filtering: {kept_count}/{total_count} conversations kept ({kept_count / total_count * 100:.1f}%)"
        )
        return filtered

    def deduplicate_conversations(
        self, conversations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate conversations based on content similarity.

        Returns: List of unique conversations.
        """
        seen_hashes = set()
        unique_conversations = []

        for conv in conversations:
            content_hash = self._generate_content_hash(conv)

            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_conversations.append(conv)
            else:
                logger.debug(
                    f"Removed duplicate conversation: {conv.get('ingestion_hash', 'unknown')}"
                )

        removed_count = len(conversations) - len(unique_conversations)
        if removed_count > 0:
            logger.info(
                f"Deduplication: Removed {removed_count} duplicate conversations"
            )

        return unique_conversations

    def optimize_batch(
        self, conversations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply all optimizations: filtering + deduplication.

        Returns: Optimized list of conversations ready for synthesis.
        """
        logger.info(
            f"Starting batch optimization with {len(conversations)} conversations"
        )

        # Step 1: Filter low-quality conversations
        filtered = self.filter_conversations(conversations)

        # Step 2: Remove duplicates
        optimized = self.deduplicate_conversations(filtered)

        # Step 3: Sort by quality (highest quality first)
        optimized.sort(key=self._calculate_quality_score, reverse=True)

        logger.info(
            f"Batch optimization complete: {len(optimized)} conversations ready for synthesis"
        )
        return optimized

    def _should_process_conversation(self, conv: Dict[str, Any]) -> bool:
        """Determine if a conversation is worth processing."""
        messages = conv.get("messages", [])

        # Must have at least 2 messages
        if len(messages) < 2:
            return False

        # Check for meaningful content
        all_content = []
        for msg in messages:
            content = msg.get("content", "").strip()
            if content:
                all_content.append(content)

        if not all_content:
            return False

        # Combine all content for analysis
        full_content = " ".join(all_content).lower()

        # Skip if too short
        word_count = len(full_content.split())
        if word_count < 10:
            return False

        # Skip pure social conversations
        if self._is_social_conversation(full_content):
            return False

        # Must contain technical keywords
        has_technical_content = any(
            keyword in full_content for keyword in self.technical_keywords
        )

        # Must have at least 2 messages with substantial content
        substantial_messages = [msg for msg in all_content if len(msg.split()) > 3]
        has_substantial_exchange = len(substantial_messages) >= 2

        return has_technical_content and has_substantial_exchange

    def _is_social_conversation(self, content: str) -> bool:
        """Check if conversation is purely social/greetings."""
        # Remove punctuation for pattern matching
        clean_content = re.sub(r"[^\w\s]", "", content)

        for pattern in self.social_patterns:
            if re.search(pattern, clean_content, re.IGNORECASE):
                # If the entire content matches social patterns
                if len(clean_content.split()) <= 5:
                    return True

        return False

    def _generate_content_hash(self, conv: Dict[str, Any]) -> str:
        """Generate a hash representing the conversation content."""
        messages = conv.get("messages", [])
        content_parts = []

        for msg in messages:
            content = msg.get("content", "").strip()
            if content:
                content_parts.append(content)

        # Create normalized content for hashing
        normalized_content = " ".join(sorted(content_parts))
        return hashlib.md5(normalized_content.encode()).hexdigest()[:12]

    def _calculate_quality_score(self, conv: Dict[str, Any]) -> float:
        """Calculate a quality score for conversation prioritization."""
        messages = conv.get("messages", [])
        if not messages:
            return 0.0

        # Base score from message count and length
        message_count = len(messages)
        avg_length = (
            sum(len(msg.get("content", "").split()) for msg in messages) / message_count
        )

        base_score = min(message_count / 5.0, 2.0) + min(avg_length / 20.0, 1.0)

        # Bonus for technical content
        full_content = " ".join(msg.get("content", "") for msg in messages).lower()
        technical_terms = sum(
            1 for keyword in self.technical_keywords if keyword in full_content
        )
        technical_bonus = min(technical_terms / 3.0, 1.5)

        return base_score + technical_bonus
