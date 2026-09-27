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


class PricingPolicyError(EstimatorError, ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class UnknownCategoryError(EstimatorError, ValueError):
    pass


class CatalogValidationError(EstimatorError, ValueError):
    def __init__(self, code: str, message: str, attr: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.attr = attr


class BudgetExceededError(EstimatorError):
    def __init__(self, cap: int, used: int, requested: int) -> None:
        super().__init__(
            f"daily budget exceeded: used {used} + requested {requested} > cap {cap}"
        )
        self.code = "DAILY_BUDGET_EXCEEDED"
        self.cap = cap
        self.used = used
        self.requested = requested
