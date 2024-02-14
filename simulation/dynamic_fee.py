from math import exp

from custom_types import PriceFeed, Token


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
        sum([(prices[i + window] - twma[i]) ** 2 for i in range(window)]) / window
    ]
    for i in range(len(prices) - window * 2 - 1):
        next_volatility = (
            volatility[i]
            + (
                (prices[i + window * 2] - twma[i + window]) ** 2
                - (prices[i + window] - twma[i]) ** 2
            )
            / window
        )
        volatility.append(next_volatility)

    return volatility


def custom_sigmoid(x, alpha, gamma, beta):
    if gamma * abs(beta - x) > 700:
        return alpha / (1 + exp(700))

    return alpha / (1 + exp(gamma * abs(beta - x)))


def calculate_dynamic_fee(volatility: float) -> float:
    """
    Calculate the dynamic fee for the pool based on the volatility of the price.

    Args:
        volatility (float): The volatility of the price of the pool.

    Returns:
        float: The dynamic fee for the pool.
    """
    initial_min_fee = 0.01 / 100
    alpha1 = 3000 / 1000000
    alpha2 = (15000 - 3000) / 1000000
    beta1 = 360
    beta2 = 60000
    gamma1 = 1 / 59
    gamma2 = 1 / 8500
    # volume_beta = 0
    # volume_gamma = 0

    dynamic_fee = custom_sigmoid(volatility, alpha1, gamma1, beta1) + custom_sigmoid(
        volatility, alpha2, gamma2, beta2
    )

    # volume_per_liquidity =

    # dynamic_fee_with_regulator = custom_sigmoid(volume_per_liquidity, dynamic_fee, VOLUME_GAMMA, VOLUME_BETA)

    return initial_min_fee + dynamic_fee


def calculate_dynamic_beta(volatility: float) -> float:
    """
    Calculate the dynamic fee for the pool based on the volatility of the price.

    Args:
        volatility (float): The volatility of the price of the pool.

    Returns:
        float: The dynamic beta for the pool.
    """
    initial_min_beta = 0.01 / 100
    alpha1 = 3000 / 1000000
    alpha2 = (15000 - 3000) / 1000000
    beta1 = 360
    beta2 = 60000
    gamma1 = 1 / 59
    gamma2 = 1 / 8500
    # volume_beta = 0
    # volume_gamma = 0

    dynamic_beta = custom_sigmoid(volatility, alpha1, gamma1, beta1) + custom_sigmoid(
        volatility, alpha2, gamma2, beta2
    )

    # volume_per_liquidity =

    # dynamic_beta_with_regulator = custom_sigmoid(volume_per_liquidity, dynamic_fee, VOLUME_GAMMA, VOLUME_BETA)

    # print(min((initial_min_beta + dynamic_beta) * 7000, 1))

    return min((initial_min_beta + dynamic_beta) * 7000, 1)
