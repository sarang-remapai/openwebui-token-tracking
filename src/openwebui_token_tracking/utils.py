"""
Utility functions for openwebui-token-tracking.
"""

from typing import List, Tuple, Any, Optional


def pop_system_message(messages: List[dict]) -> Tuple[Optional[str], List[dict]]:
    """
    Extract system message from a list of messages.
    
    This function separates system messages from regular messages, as some APIs
    require system messages to be passed separately. It extracts the first system
    message found and removes all system messages from the remaining list.
    
    :param messages: List of message dictionaries with 'role' and 'content' keys
    :type messages: List[dict]
    :return: Tuple of (system_message, remaining_messages)
    :rtype: Tuple[Optional[str], List[dict]]
    """
    system_message = None
    remaining_messages = []
    system_found = False
    
    for message in messages:
        if message.get("role") == "system" and not system_found:
            # Extract the first system message
            content = message.get("content", "")
            if isinstance(content, str):
                system_message = content
            elif isinstance(content, list):
                # Handle multimodal content - extract text parts
                text_parts = []
                for item in content:
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                system_message = " ".join(text_parts) if text_parts else None
            system_found = True
            # Skip adding this system message to remaining_messages
        else:
            remaining_messages.append(message)
    
    return system_message, remaining_messages
