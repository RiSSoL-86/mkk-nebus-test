class IdempotencyConflictError(Exception):
    """The key has already been used for a different request."""

    def __init__(self) -> None:
        super().__init__("Idempotency key already used")
