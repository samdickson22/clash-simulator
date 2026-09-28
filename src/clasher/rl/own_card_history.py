"""Optional public control history, separate from visual card guesses."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AcceptedOwnPlay:
    """Last confirmed ordinary card play in the current battle.

    A command submission alone is not confirmation. Live controllers must only
    supply this after observing acceptance, and clear it at battle boundaries
    or when later accepted plays may have been missed. None means unknown.
    Mirror and Champion abilities preserve the previous ordinary card.
    """

    card_name: str
    elixir_cost: int

    def __post_init__(self) -> None:
        if not isinstance(self.card_name, str) or not self.card_name.strip():
            raise ValueError("accepted card name must be nonempty")
        if type(self.elixir_cost) is not int or not 0 <= self.elixir_cost <= 10:
            raise ValueError("accepted card cost must be an integer from 0 to 10")
