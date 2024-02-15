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

    np.random.seed(123)

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

    def dynamic_after_swap(pool, price_feed, volatility, block_num):
        pool.beta = calculate_dynamic_beta(volatility)
        diamond_after_swap(pool, price_feed, volatility, block_num)

    for i in range(10):
        start_time = time.time()
        print(f"Running simulation {i}")

        sim = create_simulation(dynamic_after_swap)
        sim.run(verbose=False)

        print(f"Simulation {i} took {time.time() - start_time} seconds")

    if not os.path.exists("results"):
        os.makedirs("results")

    result.to_csv("results/result_test.csv")
