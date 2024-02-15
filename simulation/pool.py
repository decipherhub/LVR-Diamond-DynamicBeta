from dataclasses import dataclass, field
from math import sqrt
from copy import deepcopy
from typing import Optional, Callable

from custom_types import Token, PriceFeed


@dataclass
class Vault:
    def __init__(self, token_x: Token, token_y: Token):
        self.token_x: Token = token_x
        self.token_y: Token = token_y
        self.reserve: dict[Token, float] = {self.token_x: 0, self.token_y: 0}

    @property
    def reserve_x(self) -> float:
        return self.reserve[self.token_x]

    @property
    def reserve_y(self) -> float:
        return self.reserve[self.token_y]


@dataclass
class LiquidityPool:
    def __init__(
        self,
        token_x,
        token_y,
        fee,
    ):
        self.token_x: Token = token_x
        self.token_y: Token = token_y
        self.fee: float = fee
        self.reserve: dict[Token, float] = {self.token_x: 0, self.token_y: 0}
        self.lvr: float = 0
        self.collected_fees_retail: float = 0
        self.collected_fees_arbitrage: float = 0
        self.volume_retail: float = 0
        self.volume_arbitrage: float = 0

    def copy(self):
        return deepcopy(self)

    @property
    def reserve_x(self) -> float:
        return self.reserve[self.token_x]

    @property
    def reserve_y(self) -> float:
        return self.reserve[self.token_y]

    @property
    def price(self) -> float:
        return self.reserve_y / self.reserve_x

    @property
    def liquidity(self) -> float:
        return sqrt(self.reserve_x * self.reserve_y)

    def total_value_locked(self, price_feed: PriceFeed) -> float:
        return (
            self.reserve[self.token_x] * price_feed[self.token_x]
            + self.reserve[self.token_y] * price_feed[self.token_y]
        )

    def other_token(self, token: Token) -> Token:
        return self.token_x if token == self.token_y else self.token_y

    def get_amount_out(self, token_in: Token, amount_in: float) -> float:
        amount_in_with_fee = amount_in * (1 - self.fee)
        reserve_in = self.reserve[token_in]
        reserve_out = self.reserve[self.other_token(token_in)]
        amount_out = (
            amount_in_with_fee * reserve_out / (reserve_in + amount_in_with_fee)
        )
        return amount_out

    def add_liquidity(self, token: Token, amount: float):
        """
        Add amount of token to the pool.

        Args:
            token (Token): The token being added.
            amount (float): The amount of token being added.

        Returns:
            float: The amount of liquidity tokens minted.
        """
        # Update the reserves based on which token is being added
        self.reserve[token] += amount

        # Calculate the amount of liquidity tokens to mint and return it
        # return amount * self.total_supply / self.total_value_locked

    def remove_liquidity(self, token: Token, amount: float):
        self.reserve[token] -= amount

    def swap(self, token_in: Token, amount_in: float) -> float:
        """
        Swap amount_in of token_in for the other token in the pool.

        Args:
            token_in (Token): The token being swapped in.
            amount_in (float): The amount of token_in being swapped.

        Returns:
            float: The amount of the other token that is swapped out.
        """
        # Calculate the amount out using the get_amount_out method
        amount_out = self.get_amount_out(token_in, amount_in)

        # Update the reserves based on which token is being swapped in
        self.reserve[token_in] += amount_in
        self.reserve[self.other_token(token_in)] -= amount_out

        # Return the amount of the other token that was swapped out
        return amount_out


@dataclass
class DiamondPool(LiquidityPool):
    def __init__(
        self,
        token_x,
        token_y,
        fee,
        before_swap: Optional[Callable],
        after_swap: Optional[Callable],
        beta,
    ):
        super().__init__(token_x, token_y, fee)
        self.before_swap = before_swap
        self.after_swap = after_swap
        self.beta: float = beta
        self.vault = Vault(token_x, token_y)

    # override total_value_locked
    def total_value_locked(self, price_feed: PriceFeed) -> float:
        return (
            self.reserve[self.token_x] + self.vault.reserve[self.token_x]
        ) * price_feed[self.token_x] + (
            self.reserve[self.token_y] + self.vault.reserve[self.token_y]
        ) * price_feed[
            self.token_y
        ]
