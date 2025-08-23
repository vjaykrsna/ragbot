"""
Memory monitoring utilities for dynamic batch sizing.
"""

import resource


def get_memory_usage():
    """
    Get current memory usage in bytes.

    Returns:
        int: Current memory usage in bytes
    """
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_maxrss * 1024  # Convert KB to bytes on Linux


def get_memory_usage_mb():
    """
    Get current memory usage in megabytes.

    Returns:
        float: Current memory usage in MB
    """
    return get_memory_usage() / (1024 * 1024)


def estimate_message_size(message_dict):
    """
    Estimate the memory size of a message dictionary.

    Args:
        message_dict (dict): Message dictionary

    Returns:
        int: Estimated size in bytes
    """
    # Rough estimation: sum of string lengths + some overhead
    size = 0
    for key, value in message_dict.items():
        size += len(key) if isinstance(key, str) else 8
        if isinstance(value, str):
            size += len(value)
        elif isinstance(value, (int, float)):
            size += 8
        elif isinstance(value, dict):
            size += len(str(value))  # Rough estimate for nested dicts
        else:
            size += len(str(value)) if value else 0
    # Add some overhead for dictionary structure
    return size + 100


def calculate_dynamic_batch_size(
    base_batch_size, message_size_estimate, max_memory_mb=500
):
    """
    Calculate a dynamic batch size based on memory constraints.

    Args:
        base_batch_size (int): Base batch size from configuration
        message_size_estimate (int): Estimated size of a single message in bytes
        max_memory_mb (int): Maximum memory to use for batching (default: 500MB)

    Returns:
        int: Adjusted batch size
    """
    current_memory_mb = get_memory_usage_mb()
    available_memory_mb = max_memory_mb - current_memory_mb

    # If we're already using too much memory, reduce batch size significantly
    if available_memory_mb <= 50:
        return max(10, base_batch_size // 10)

    # Calculate how many messages we can fit in available memory
    if message_size_estimate > 0:
        max_messages = int((available_memory_mb * 1024 * 1024) / message_size_estimate)
        # Return the smaller of the calculated max or base batch size, with a minimum of 10
        return max(10, min(base_batch_size, max_messages))

    # If we can't estimate message size, return base batch size
    return base_batch_size
