from math import sqrt

from custom_types import PriceFeed
from pool import LiquidityPool, DiamondPool
from strategy import compute_profit_maximizing_trade


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

    # Compute the profit-maximizing trade
    x_to_y, arb_amount = compute_profit_maximizing_trade(
        price_feed[token_x], price_feed[token_y], pool
    )

    if x_to_y:
        delta_x = arb_amount
        delta_y = -pool.get_amount_out(token_x, arb_amount)
        swap_fee = arb_amount * price_feed[token_x] * pool.fee
    else:
        delta_x = -pool.get_amount_out(token_y, arb_amount)
        delta_y = arb_amount
        swap_fee = arb_amount * price_feed[token_y] * pool.fee

    target_reserve_x = pool.reserve_x + delta_x
    target_reserve_y = pool.reserve_y + delta_y

    lp_loss_vs_cex = (
        -1
        * (1 - beta)
        * (delta_x * price_feed[token_x] + delta_y * price_feed[token_y])
    ) + swap_fee
    arbitrageur_profit = lp_loss_vs_cex - swap_fee - tx_fee

    if arbitrageur_profit > 0:
        if x_to_y:  # arbitrageur sells token_x and buys token_y
            # take beta portion of the swap taken from the arbitrageur to the vault
            pool.vault.reserve[token_y] += abs(delta_y) * beta
            # pool reserve of token_x is increased by the delta_x * (1 - beta)
            pool.reserve[token_x] += delta_x * (1 - beta)
            # pool reserve of token_y is set with the target_price
            pool.reserve[token_y] = pool.reserve_x * target_price
            # excess token_y is moved to the vault
            pool.vault.reserve[token_y] += target_reserve_y - pool.reserve_y

            pool.volume_arbitrage += abs(delta_y) * price_feed[token_y]
        else:  # arbitrageur buys token_x and sells token_y
            pool.vault.reserve[token_x] += abs(delta_x) * beta
            pool.reserve[token_y] += delta_y * (1 - beta)
            pool.reserve[token_x] = pool.reserve_y / target_price
            pool.vault.reserve[token_x] += target_reserve_x - pool.reserve_x

            pool.volume_arbitrage += abs(delta_x) * price_feed[token_x]

        pool.lvr += lp_loss_vs_cex  # account without swap fees and tx fees
        pool.collected_fees_arbitrage += swap_fee


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
