from enum import Enum


class Token(Enum):
    ETH = "ETH"
    USDC = "USDC"


PriceFeed = dict[Token, float]
Oracle = list[PriceFeed]
