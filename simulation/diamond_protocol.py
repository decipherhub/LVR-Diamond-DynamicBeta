from math import sqrt

from custom_types import PriceFeed
from pool import LiquidityPool, DiamondPool


def core_protocol(pool: DiamondPool, price_feed: PriceFeed, tx_fee_per_eth: float):
    """
    Perform the core protocol for a diamond pool.
    Arbitrageurs are incentivized to perform swaps that move the price of the pool towards the price specified by the price feed.
    The arbitrageur receives a portion of the swap fee, and the remainder is added to the pool's vault.

    Args:
        pool (LiquidityPool): The liquidity pool to adjust.
        price_feed (PriceFeed): The price feed for the pool.
        tx_fee_per_gas (float): The transaction fee per eth.
    """
    beta = pool.beta
    token_x, token_y = pool.token_x, pool.token_y
    target_price = price_feed[token_x] / price_feed[token_y]
    tx_fee = tx_fee_per_eth * target_price

    target_reserve_x = pool.liquidity / sqrt(target_price)
    target_reserve_y = pool.liquidity * sqrt(target_price)

    delta_x = target_reserve_x - pool.reserve_x
    delta_y = target_reserve_y - pool.reserve_y

    lp_loss_vs_cex = (
        -1
        * (1 - beta)
        * (delta_x * price_feed[token_x] + delta_y * price_feed[token_y])
    )
    arbitrageur_profit = lp_loss_vs_cex - tx_fee

    if arbitrageur_profit > 0:
        if delta_x < 0:  # arbitrageur buys token_x and sells token_y
            # take beta portion of the swap taken from the arbitrageur to the vault
            pool.vault.reserve[token_x] += abs(delta_x) * beta
            # pool reserve of token_y is increased by the delta_y * (1 - beta)
            pool.reserve[token_y] += delta_y * (1 - beta)
            # pool reserve of token_x is set with the target_price
            pool.reserve[token_x] = pool.reserve_y / target_price
            # excess token_x is moved to the vault
            pool.vault.reserve[token_x] += target_reserve_x - pool.reserve_x

            pool.volume_arbitrage += abs(delta_x) * price_feed[token_x]
        elif delta_y < 0:  # arbitrageur buys token_y and sells token_x
            pool.vault.reserve[token_y] += abs(delta_y) * beta
            pool.reserve[token_x] += delta_x * (1 - beta)
            pool.reserve[token_y] = pool.reserve_x * target_price
            pool.vault.reserve[token_y] += target_reserve_y - pool.reserve_y

            pool.volume_arbitrage += abs(delta_y) * price_feed[token_y]

        pool.lvr += lp_loss_vs_cex  # account without swap fees and tx fees


def vault_rebalancing(pool: LiquidityPool, price_feed: PriceFeed):
    """
    Adjust the reserve ratio of the liquidity pool to match the ratio specified by the price feed.
    Utilize the tokens in the pool's vault to balance the pool's reserves if necessary.
    Excess tokens are moved to or from the vault as required to achieve the desired ratio.

    Args:
        pool (LiquidityPool): The liquidity pool to adjust.
        price_feed (PriceFeed): The price feed for the pool.
    """
    token_x, token_y = pool.token_x, pool.token_y
    target_price = price_feed[token_x] / price_feed[token_y]

    if (
        pool.vault.reserve_y < pool.vault.reserve_x * target_price
    ):  # Adjust Token X in the pool using the vault
        adjust_x = pool.vault.reserve_y / target_price
        pool.add_liquidity(token_y, pool.vault.reserve_y)
        pool.add_liquidity(token_x, adjust_x)
        pool.vault.reserve[token_y] -= pool.vault.reserve_y
        pool.vault.reserve[token_x] -= adjust_x
    elif (
        pool.vault.reserve_x < pool.vault.reserve_y / target_price
    ):  # Adjust Token Y in the pool using the vault
        adjust_y = pool.vault.reserve_x * target_price
        pool.add_liquidity(token_x, pool.vault.reserve_x)
        pool.add_liquidity(token_y, adjust_y)
        pool.vault.reserve[token_x] -= pool.vault.reserve_x
        pool.vault.reserve[token_y] -= adjust_y


def vault_conversion(pool: LiquidityPool, price_feed: PriceFeed):
    """
    Convert the tokens in the pool's vault to balance the pool's reserves.
    If one of the reserves in the pool is empty, convert the other token in the pool to fill the empty reserve.

    Args:
        pool (LiquidityPool): The liquidity pool to adjust.
        price_feed (PriceFeed): The price feed for the pool.
    """
    token_x, token_y = pool.token_x, pool.token_y
    target_price = price_feed[token_x] / price_feed[token_y]

    if (
        pool.vault.reserve_x == 0 and pool.vault.reserve_y != 0
    ):  # Convert half of Token Y in the vault to Token X and add it to the pool
        half_vault_reserve_y = pool.vault.reserve_y / 2
        pool.add_liquidity(token_x, half_vault_reserve_y / target_price)
        pool.add_liquidity(token_y, half_vault_reserve_y)
        pool.vault.reserve[token_y] -= pool.vault.reserve_y
    elif (
        pool.vault.reserve_y == 0 and pool.vault.reserve_x != 0
    ):  # Convert Token X in the vault to Token Y and add it to the pool
        half_vault_reserve_x = pool.vault.reserve_x / 2
        pool.add_liquidity(token_y, half_vault_reserve_x * target_price)
        pool.add_liquidity(token_x, half_vault_reserve_x)
        pool.vault.reserve[token_x] -= pool.vault.reserve_x
