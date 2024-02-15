import os
import pandas as pd
import numpy as np
import time

from custom_types import Token
from simulator import Simulator
from diamond_protocol import core_protocol, vault_rebalancing, vault_conversion
from dynamic_fee import calculate_dynamic_beta

# assume 12 second blocks as in the mainnet
BLOCKS_PER_DAY = 86400 // 12
NUM_DAYS = 10
V0 = 1e8
INITIAL_PRICE = 2300
RESERVE_X = V0 / 2 / INITIAL_PRICE
RESERVE_Y = V0 / 2
TX_FEE_PER_ETH = 0.009
NEW_LIQUIDITY = V0 / 1000
NEW_LIQUIDITY_PERIOD = 0


def diamond_after_swap(pool, price_feed, volatility, block_num):
    core_protocol(pool, price_feed, TX_FEE_PER_ETH)

    vault_rebalancing(pool, price_feed)
    if block_num % 10 == 0:
        vault_conversion(pool, price_feed)


def create_simulation(dynamic_after_swap):
    sim = Simulator(
        BLOCKS_PER_DAY, NUM_DAYS, TX_FEE_PER_ETH, NEW_LIQUIDITY, NEW_LIQUIDITY_PERIOD
    )

    sim.create_liquidity_pool(Token.ETH, Token.USDC, RESERVE_X, RESERVE_Y, 0.003)
    sim.create_diamond_pool(
        Token.ETH,
        Token.USDC,
        RESERVE_X,
        RESERVE_Y,
        0.003,
        None,
        diamond_after_swap,
        0.9,
    )
    sim.create_diamond_pool(
        Token.ETH,
        Token.USDC,
        RESERVE_X,
        RESERVE_Y,
        0.003,
        None,
        dynamic_after_swap,
        0.9,
    )

    sim.create_oracle(INITIAL_PRICE, 0.05)
    return sim


if __name__ == "__main__":

    num_pools = 3

    INITIAL_MIN_FEES = 0.01 / 100
    ALPHA1 = 3000 / 1000000
    ALPHA2 = (15000 - 3000) / 1000000
    BETA1 = 360
    BETA2 = 60000
    GAMMA1 = 1 / 59
    GAMMA2 = 1 / 8500
    VOLUME_BETA = 0
    VOLUME_GAMMA = 0

    range_initial_min_fees = [0.0001, 0.01, 0.1]
    range_alpha1 = [0.003, 0.3, 3]
    range_alpha2 = [0.012, 0.12, 1.2]
    range_beta1 = [36, 360, 3600]
    range_beta2 = [600, 6000, 60000]
    range_gamma1 = [1 / 590, 1 / 59, 1 / 5.9]
    range_gamma2 = [1 / 85000, 1 / 8500, 1 / 850]

    # Make parameter set
    parameters = []
    for initial_min_fees in range_initial_min_fees:
        for alpha1 in range_alpha1:
            for alpha2 in range_alpha2:
                for beta1 in range_beta1:
                    for beta2 in range_beta2:
                        for gamma1 in range_gamma1:
                            for gamma2 in range_gamma2:
                                parameters.append(
                                    (
                                        initial_min_fees,
                                        alpha1,
                                        alpha2,
                                        beta1,
                                        beta2,
                                        gamma1,
                                        gamma2,
                                    )
                                )

    # Shuffle parameter set
    np.random.shuffle(parameters)

    results = pd.DataFrame(
        columns=[
            "initial_min_fees",
            "alpha1",
            "alpha2",
            "beta1",
            "beta2",
            "gamma1",
            "gamma2",
            "tvl_ratio",
        ]
    )

    while len(parameters) > 0:
        # Choose parameter set Randomly
        initial_min_fees, alpha1, alpha2, beta1, beta2, gamma1, gamma2 = parameters.pop(
            0
        )
        print(
            f"Running simulation with parameters: {initial_min_fees}, {alpha1}, {alpha2}, {beta1}, {beta2}, {gamma1}, {gamma2}"
        )
        start_time = time.time()

        def dynamic_after_swap(pool, price_feed, volatility, block_num):
            pool.beta = calculate_dynamic_beta(
                volatility,
                initial_min_fees,
                alpha1,
                alpha2,
                beta1,
                beta2,
                gamma1,
                gamma2,
            )
            diamond_after_swap(pool, price_feed, volatility, block_num)

        tvl_ratio = []
        for i in range(10):
            sim = create_simulation(dynamic_after_swap)
            sim.run(verbose=False)
            tvl_ratio.append(
                sim.liquidity_pools[2].total_value_locked(sim.oracle[-1])
                / sim.liquidity_pools[1].total_value_locked(sim.oracle[-1])
            )

        print(f"Simulation took {time.time() - start_time} seconds")
        print(f"TVL ratio: {np.mean(tvl_ratio)}")
        results = pd.concat(
            [
                results,
                pd.DataFrame(
                    [
                        [
                            initial_min_fees,
                            alpha1,
                            alpha2,
                            beta1,
                            beta2,
                            gamma1,
                            gamma2,
                            np.mean(tvl_ratio),
                        ]
                    ],
                    columns=[
                        "initial_min_fees",
                        "alpha1",
                        "alpha2",
                        "beta1",
                        "beta2",
                        "gamma1",
                        "gamma2",
                        "tvl_ratio",
                    ],
                ),
            ],
            ignore_index=True,
        )

    if not os.path.exists("results"):
        os.makedirs("results")

    # Sort results by tvl_ratio
    results = results.sort_values("tvl_ratio", ascending=False)
    results.to_csv("results/optimize.csv")
