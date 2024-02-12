import os
import pandas as pd
import time

from custom_types import Token
from simulator import Simulator
from diamond_protocol import core_protocol, vault_rebalancing, vault_conversion

# assume 12 second blocks as in the mainnet
BLOCKS_PER_DAY = 86400 // 12
NUM_DAYS = 10
V0 = 1e6
RESERVE_X = V0 / 2 / 1000
RESERVE_Y = V0 / 2
TX_FEE = 5.0
NEW_LIQUIDITY = V0 / 1000
NEW_LIQUIDITY_PERIOD = BLOCKS_PER_DAY


def diamond_before_swap(pool, price_feed, block_num):
    pass


def diamond_after_swap(pool, price_feed, block_num):
    core_protocol(pool, price_feed, TX_FEE)

    vault_rebalancing(pool, price_feed)
    if block_num % 10 == 0:
        vault_conversion(pool, price_feed)


def create_simulation():
    sim = Simulator(
        BLOCKS_PER_DAY, NUM_DAYS, TX_FEE, NEW_LIQUIDITY, NEW_LIQUIDITY_PERIOD
    )

    sim.create_liquidity_pool(Token.ETH, Token.USDC, RESERVE_X, RESERVE_Y, 0.003, False)
    sim.create_diamond_pool(
        Token.ETH,
        Token.USDC,
        RESERVE_X,
        RESERVE_Y,
        0.003,
        False,
        0.3,
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
        0.3,
        True,
        None,
        diamond_after_swap,
    )

    sim.create_oracle(0.05)
    return sim


if __name__ == "__main__":

    num_pools = 3

    result = pd.DataFrame(
        columns=["Price"]
        + [f"TVL_{i+1}" for i in range(num_pools)]
        + [f"LVR_{i+1}" for i in range(num_pools)]
        + [f"Collected_Fees_{i+1}" for i in range(num_pools)]
        + ["Best Pool", "Best Pool TVL/CFMM"]
    )

    for i in range(100):
        start_time = time.time()
        print(f"Running simulation {i}")

        sim = create_simulation()
        sim.run(verbose=False)

        result.loc[i, "Price"] = sim.oracle[-1][Token.ETH] / sim.oracle[-1][Token.USDC]
        for j, pool in enumerate(sim.liquidity_pools):
            result.loc[i, f"TVL_{j+1}"] = pool.total_value_locked(sim.oracle[-1])
            result.loc[i, f"LVR_{j+1}"] = pool.lvr
            result.loc[i, f"Collected_Fees_{j+1}"] = pool.collected_fees
        tvls = [pool.total_value_locked(sim.oracle[-1]) for pool in sim.liquidity_pools]
        best_pool = tvls.index(max(tvls))
        result.loc[i, "Best Pool"] = best_pool + 1
        result.loc[i, "Best Pool TVL/CFMM"] = tvls[best_pool] / tvls[0]

        print(f"Simulation {i} took {time.time() - start_time} seconds")

    if not os.path.exists("results"):
        os.makedirs("results")

    result.to_csv("results/result_new_liquidity.csv")
