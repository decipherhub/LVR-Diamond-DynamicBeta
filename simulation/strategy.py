import numpy as np
from math import sqrt

from custom_types import PriceFeed
from pool import LiquidityPool


def generate_uninformed_transactions(num_transactions, retail_size):
    """
    Generate a list of uninformed transactions, each with a random swap size and direction.

    Args:
    - num_transactions (int): The number of transactions to generate.
    - retail_size (float): The scale parameter for the exponential distribution to determine swap sizes.

    Returns:
    - transactions (list of tuples): Each tuple represents a transaction with (swap_size, direction),
      where direction is either 1 (A to B) or -1 (B to A).
    """
    # Generate random swap sizes for each transaction
    swap_sizes = np.random.exponential(scale=retail_size, size=num_transactions)

    # Generate random directions for each transaction (1 for A to B, -1 for B to A)
    directions = np.random.choice([1, -1], size=num_transactions)

    # Combine swap sizes and directions into transactions
    transactions = list(zip(swap_sizes, directions))

    return transactions


def multi_pool_random_swap(pools: list[LiquidityPool], price_feed: PriceFeed):
    """
    Perform a random swap in the pool that offers the best price among multiple pools.

    Args:
        pools (list[LiquidityPool]): A list of liquidity pools to consider for the swap.
        price_feed (PriceFeed): The price feed for the pools.
    """
    if not pools:
        return  # No pools available

    token_x, token_y = pools[0].token_x, pools[0].token_y
    target_price = price_feed[token_x] / price_feed[token_y]

    # Generate Transactions
    transactions = generate_uninformed_transactions(
        max(round(np.random.normal(1.2546, 0.5909)), 0),
        max(
            np.random.normal(1743, 6331), 0
        ),  # Its a mean and std deviation of number of transactions and retail size of Uniswap V2 ETH/USDT pool in 2023/02~2024/02
    )
    pending_swaps = []

    for transaction in transactions:
        swap_size, direction = transaction
        # Find the pool with the best price for the swap
        best_pools = []
        best_amount_out = 0
        for pool in pools:
            amount_out = (
                pool.get_amount_out(token_x, swap_size / target_price)
                if direction == 1
                else pool.get_amount_out(token_y, swap_size)
            )
            # Save the pool with the best price for the swap
            if amount_out > best_amount_out:
                best_amount_out = amount_out
                best_pools = [pool]
            # If the pool has the same price as the best price, add it to the list
            elif amount_out == best_amount_out:
                best_pools.append(pool)

        # Split the swap size among the best pools
        if best_pools:
            split_swap_size = swap_size / len(best_pools)
            for best_pool in best_pools:
                pending_swaps.append((best_pool, split_swap_size, direction))

    # # Print the swap details of the pending swaps in the liquidity pools
    # print(
    #     "Sum of Pending Swap Size in Liquidity Pools: ",
    #     sum([swap[1] for swap in pending_swaps if isinstance(swap[0], LiquidityPool)]),
    # )
    # print(
    #     "Sum of Pending Swap Size in Diamond Pools: ",
    #     sum([swap[1] for swap in pending_swaps if isinstance(swap[0], DiamondPool)]),
    # )

    for swap in pending_swaps:
        pool, swap_size, direction = swap

        if direction == 1:
            pool.swap(token_x, swap_size / target_price)
        else:
            pool.swap(token_y, swap_size)

        swap_fee = swap_size * price_feed[token_y] * pool.fee
        pool.collected_fees_retail.append(swap_fee)
        pool.volume_retail.append(swap_size * price_feed[token_y])


def compute_profit_maximizing_trade(
    true_price_token_a, true_price_token_b, pool
) -> tuple:
    """
    Compute the profit-maximizing trade for an arbitrageur in a liquidity pool.

    Args:
        true_price_token_a (float): The true price of token A in terms of token B.
        true_price_token_b (float): The true price of token B in terms of token A.
        pool (LiquidityPool): The liquidity pool to consider for the trade.

    Returns:
        x_to_y (bool): True if the trade is from token A to token B, False if from token B to token A.
        amount_in (float): The amount that must be sent to move the price to the profit-maximizing price.
    """
    reserve_a, reserve_b = pool.reserve_x, pool.reserve_y
    fee = pool.fee

    x_to_y = (reserve_a * true_price_token_a) / reserve_b < true_price_token_b

    invariant = reserve_a * reserve_b

    left_side = sqrt(
        invariant
        * (true_price_token_b if x_to_y else true_price_token_a)
        / ((true_price_token_a if x_to_y else true_price_token_b) * (1 - fee))
    )
    right_side = (reserve_a if x_to_y else reserve_b) / (1 - fee)

    if left_side < right_side:
        return False, 0

    # Compute the amount that must be sent to move the price to the profit-maximizing price
    amount_in = left_side - right_side

    return x_to_y, amount_in


def perform_arbitrage(
    pool: LiquidityPool,
    price_feed: PriceFeed,
    tx_fee_per_eth: float,
):
    """
    Perform an arbitrage trade in the given liquidity pool.

    Args:
        pool (LiquidityPool): The liquidity pool to perform the arbitrage trade in.
        price_feed (PriceFeed): The price feed for the pool.
        tx_fee_per_eth (float): The transaction fee per eth.

    """

    token_x, token_y = pool.token_x, pool.token_y

    target_price = price_feed[token_x] / price_feed[token_y]
    tx_fee = tx_fee_per_eth * target_price

    # Compute the profit-maximizing trade
    x_to_y, arb_amount = compute_profit_maximizing_trade(
        price_feed[token_x], price_feed[token_y], pool
    )

    if x_to_y:  # Arbitrageur sell token_x and buys token_y
        swap_fee = arb_amount * price_feed[token_x] * pool.fee
        lp_loss_vs_cex = (
            pool.get_amount_out(token_x, arb_amount) * price_feed[token_y]
            - arb_amount * price_feed[token_x]
        ) + swap_fee
        arbitrageur_profit = lp_loss_vs_cex - swap_fee - tx_fee
        if arbitrageur_profit > 0:
            pool.swap(token_x, arb_amount)
            pool.lvr.append(lp_loss_vs_cex)  # account without swap fees and tx fees
            pool.collected_fees_arbitrage.append(swap_fee)
            pool.volume_arbitrage.append(arb_amount * price_feed[token_x])
    else:  # Arbitrageur sell token_y and buy token_x
        swap_fee = arb_amount * price_feed[token_y] * pool.fee
        lp_loss_vs_cex = (
            pool.get_amount_out(token_y, arb_amount) * price_feed[token_x]
            - arb_amount * price_feed[token_y]
        ) + swap_fee
        arbitrageur_profit = lp_loss_vs_cex - swap_fee - tx_fee
        if arbitrageur_profit > 0:
            pool.swap(token_y, arb_amount)
            pool.lvr.append(lp_loss_vs_cex)
            pool.collected_fees_arbitrage.append(swap_fee)
            pool.volume_arbitrage.append(arb_amount * price_feed[token_y])
