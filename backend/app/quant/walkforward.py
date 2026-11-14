"""Walk-forward (rolling out-of-sample) window generation."""

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    train_start: int
    train_end: int  # exclusive
    test_start: int  # == train_end: test data always strictly follows training data
    test_end: int  # exclusive


def walk_forward_windows(
    n_periods: int,
    train_size: int,
    test_size: int,
    step: int | None = None,
    expanding: bool = False,
) -> Iterator[WalkForwardWindow]:
    """Yield non-leaking train/test windows (test windows are disjoint if step == test_size)."""
    if train_size < 1 or test_size < 1:
        raise ValueError("train_size and test_size must be >= 1")
    stride = step if step is not None else test_size
    if stride < 1:
        raise ValueError("step must be >= 1")
    train_end = train_size
    while train_end + test_size <= n_periods:
        yield WalkForwardWindow(
            train_start=0 if expanding else train_end - train_size,
            train_end=train_end,
            test_start=train_end,
            test_end=train_end + test_size,
        )
        train_end += stride
