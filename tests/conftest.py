import pytest


class FakeClock:
    def __init__(self, t: int | float = 0) -> None:
        self.t = t

    def __call__(self) -> int | float:
        return self.t

    def advance(self, dt: int | float) -> None:
        self.t += dt


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()
