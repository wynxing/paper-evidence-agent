"""Domain failure raised by module ports. No I/O and no recovery policy."""

from .enums import ErrorCode


class ContractError(Exception):
    """A boundary failure carrying a glossary error code.

    error_code is None only for an unclassified execution failure that must
    not be forced into a nearby code.
    """

    def __init__(self, error_code: ErrorCode | None, message: str = "") -> None:
        self.error_code = error_code
        super().__init__(message)
