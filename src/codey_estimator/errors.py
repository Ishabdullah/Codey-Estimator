class EstimatorError(Exception):
    pass


class UnknownUnitError(EstimatorError, ValueError):
    pass


class IncompatibleUnitsError(EstimatorError, ValueError):
    pass


class EstimateValidationError(EstimatorError, ValueError):
    def __init__(self, code: str, message: str, line_key: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.line_key = line_key


class CustomerViewError(EstimatorError, ValueError):
    def __init__(self, code: str, message: str, line_key: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.line_key = line_key
