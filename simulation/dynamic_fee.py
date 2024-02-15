from math import exp

from custom_types import PriceFeed, Token

INITIAL_MIN_FEES = 0.01 / 100
ALPHA1 = 3000 / 1000000
ALPHA2 = (15000 - 3000) / 1000000
BETA1 = 360
BETA2 = 60000
GAMMA1 = 1 / 59
GAMMA2 = 1 / 8500
VOLUME_BETA = 0
VOLUME_GAMMA = 0


def time_weighted_moving_average(prices: list[float], window: int) -> list[float]:
    """
    Calculate the time-weighted moving average of the price of the pool over a window of blocks.

    Args:
        prices (list[float]): The price of the pool over time.
        window (int): The number of blocks to consider in the moving average.

    Returns:
        list[float]:
    """

    twma = [sum(prices[:window]) / window]
    for i in range(len(prices) - window - 1):
        next_twma = twma[i] + (prices[i + window] - prices[i]) / window
        twma.append(next_twma)
    return twma


def calculate_volatility(
    token_x: Token, token_y: Token, oracle: list[PriceFeed], window: int
) -> list[float]:
    """
    Calculate the volatility of the price of the pool over a window of blocks.

    Args:
        token_x (Token): The first token in the pool.
        token_y (Token): The second token in the pool.
        oracle (list[PriceFeed]): The price feed for the pool.
        window (int): The number of blocks to consider in the volatility calculation.

    Returns:
        list[float]:
    """
    prices = [oracle[i][token_x] / oracle[i][token_y] for i in range(len(oracle))]
    twma = time_weighted_moving_average(
        prices, window
    )  # [0~window-1 : len(oracle)-window ~ len(oracle)-1]
    volatility = [
        sum([(prices[i + window] - twma[i]) ** 2 for i in range(window)])
        / (window * 12)
    ]
    for i in range(len(prices) - window * 2 - 1):
        next_volatility = volatility[i] + (
            (prices[i + window * 2] - twma[i + window]) ** 2
            - (prices[i + window] - twma[i]) ** 2
        ) / (window * 12)
        volatility.append(next_volatility)

    return volatility


def custom_sigmoid(x, alpha, gamma, beta):
    if gamma * (beta - x) > 700:
        return alpha / (1 + exp(700))

    return alpha / (1 + exp(gamma * (beta - x)))


# def calculate_dynamic_fee(volatility: float) -> float:
#     """
#     Calculate the dynamic fee for the pool based on the volatility of the price.

#     Args:
#         volatility (float): The volatility of the price of the pool.

#     Returns:
#         float: The dynamic fee for the pool.
#     """
#     initial_min_fee = 0.01 / 100
#     alpha1 = 3000 / 1000000
#     alpha2 = (15000 - 3000) / 1000000
#     beta1 = 360
#     beta2 = 60000
#     gamma1 = 1 / 59
#     gamma2 = 1 / 8500
#     # volume_beta = 0
#     # volume_gamma = 0

#     dynamic_fee = custom_sigmoid(volatility, alpha1, gamma1, beta1) + custom_sigmoid(
#         volatility, alpha2, gamma2, beta2
#     )

#     # volume_per_liquidity =

#     # dynamic_fee_with_regulator = custom_sigmoid(volume_per_liquidity, dynamic_fee, VOLUME_GAMMA, VOLUME_BETA)

#     return initial_min_fee + dynamic_fee


def calculate_dynamic_beta(
    volatility: float,
    initial_min_beta: float = INITIAL_MIN_FEES,
    alpha1: float = ALPHA1,
    alpha2: float = ALPHA2,
    beta1: float = BETA1,
    beta2: float = BETA2,
    gamma1: float = GAMMA1,
    gamma2: float = GAMMA2,
) -> float:
    """
    Calculate the dynamic fee for the pool based on the volatility of the price.

    Args:
        volatility (float): The volatility of the price of the pool.
        initial_min_beta (float): The initial minimum beta for the pool.
        alpha1 (float): The alpha parameter for the first sigmoid function.
        alpha2 (float): The alpha parameter for the second sigmoid function.
        beta1 (float): The beta parameter for the first sigmoid function.
        beta2 (float): The beta parameter for the second sigmoid function.
        gamma1 (float): The gamma parameter for the first sigmoid function.
        gamma2 (float): The gamma parameter for the second sigmoid function.

    Returns:
        float: The dynamic beta for the pool.
    """

    dynamic_beta = custom_sigmoid(volatility, alpha1, gamma1, beta1) + custom_sigmoid(
        volatility, alpha2, gamma2, beta2
    )

    return min(initial_min_beta + dynamic_beta, 0.99)
