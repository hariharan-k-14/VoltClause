class LLMUnavailable(Exception):
    """The provider remained unavailable after its retry policy was exhausted."""

    def __init__(self, message: str, partial_output: bool = False) -> None:
        super().__init__(message)
        self.partial_output = partial_output


class LLMConfigurationError(Exception):
    """The request or provider configuration cannot succeed by retrying."""
