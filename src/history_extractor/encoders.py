import json
from datetime import datetime


class TelegramObjectEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for Telegram objects.

    This encoder handles the serialization of `datetime` objects and objects
    that have a `to_dict()` method.
    """

    def default(self, obj):
        """
        Overrides the default JSONEncoder to handle custom types.

        Args:
            obj: The object to encode.

        Returns:
            A serializable representation of the object.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return super().default(obj)
