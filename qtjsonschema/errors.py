class UnsupportedSchemaError(Exception):
    """Error raised when schema cannot be handled"""


class ValidationError(Exception):
    """Error raised when validation fails"""

    def __init__(self, message: str):
        super().__init__(message)

        self.message = message
