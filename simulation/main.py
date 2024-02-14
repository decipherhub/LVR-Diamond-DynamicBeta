import os
import pandas as pd
import numpy as np
import time

from custom_types import Token
from simulator import Simulator
from diamond_protocol import core_protocol, vault_rebalancing, vault_conversion

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


def diamond_before_swap(pool, price_feed, block_num):
    pass


def diamond_after_swap(pool, price_feed, block_num):
    core_protocol(pool, price_feed, TX_FEE_PER_ETH)

    vault_rebalancing(pool, price_feed)
    if block_num % 10 == 0:
        vault_conversion(pool, price_feed)


def create_simulation():
    sim = Simulator(
        BLOCKS_PER_DAY, NUM_DAYS, TX_FEE_PER_ETH, NEW_LIQUIDITY, NEW_LIQUIDITY_PERIOD
    )

    sim.create_liquidity_pool(Token.ETH, Token.USDC, RESERVE_X, RESERVE_Y, 0.003, False)
    sim.create_diamond_pool(
        Token.ETH,
        Token.USDC,
        RESERVE_X,
        RESERVE_Y,
        0.003,
        False,
        0.9,
        False,
        None,
        diamond_after_swap,
    )
    sim.create_diamond_pool(
        Token.ETH,
        Token.USDC,
        RESERVE_X,
        RESERVE_Y,
        0.003,
        False,
        0.75,
        True,
        None,
        diamond_after_swap,
    )

    sim.create_oracle(INITIAL_PRICE, 0.05)
    return sim


if __name__ == "__main__":

    np.random.seed(123)

    num_pools = 3

    columns = (
        ["Price"]
        + [f"TVL_{i+1}" for i in range(num_pools)]
        + [f"LVR_{i+1}" for i in range(num_pools)]
        + [f"Collected_Fees_{i+1}" for i in range(num_pools)]
        + [f"Collected_Fees_Retail_{i+1}" for i in range(num_pools)]
        + [f"Collected_Fees_Arbitrage_{i+1}" for i in range(num_pools)]
        + [f"Volume_{i+1}" for i in range(num_pools)]
        + [f"Volume_Retail_{i+1}" for i in range(num_pools)]
        + [f"Volume_Arbitrage_{i+1}" for i in range(num_pools)]
        + ["Best Pool", "Best Pool TVL/CFMM"]
    )

    result = pd.DataFrame(columns=columns)

    for i in range(100):
        start_time = time.time()
        print(f"Running simulation {i}")

        sim = create_simulation()
        sim.run(verbose=False)

        new_row = {}
        new_row["Price"] = sim.oracle[-1][Token.ETH] / sim.oracle[-1][Token.USDC]
        for j, pool in enumerate(sim.liquidity_pools):
            new_row[f"TVL_{j+1}"] = pool.total_value_locked(sim.oracle[-1])
            new_row[f"LVR_{j+1}"] = sum(pool.lvr)
            new_row[f"Collected_Fees_{j+1}"] = sum(pool.collected_fees_retail) + sum(
                pool.collected_fees_arbitrage
            )
            new_row[f"Collected_Fees_Retail_{j+1}"] = sum(pool.collected_fees_retail)
            new_row[f"Collected_Fees_Arbitrage_{j+1}"] = sum(
                pool.collected_fees_arbitrage
            )
            new_row[f"Volume_{j+1}"] = sum(pool.volume_retail) + sum(
                pool.volume_arbitrage
            )
            new_row[f"Volume_Retail_{j+1}"] = sum(pool.volume_retail)
            new_row[f"Volume_Arbitrage_{j+1}"] = sum(pool.volume_arbitrage)
        tvls = [pool.total_value_locked(sim.oracle[-1]) for pool in sim.liquidity_pools]
        best_pool = tvls.index(max(tvls))
        new_row["Best Pool"] = best_pool + 1
        new_row["Best Pool TVL/CFMM"] = tvls[best_pool] / tvls[0]
        result = pd.concat([result, pd.DataFrame([new_row])], ignore_index=True)

        print(f"Simulation {i} took {time.time() - start_time} seconds")

    if not os.path.exists("results"):
        os.makedirs("results")

    result.to_csv("results/result.csv")
