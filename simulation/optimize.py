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


def dynamic_after_swap(pool, price_feed, volatility, block_num):
    pass


def create_simulation(
    blocks_per_day=BLOCKS_PER_DAY,
    num_days=NUM_DAYS,
    tx_fee_per_eth=TX_FEE_PER_ETH,
    new_liquidity=NEW_LIQUIDITY,
    new_liquidity_period=NEW_LIQUIDITY_PERIOD,
    beta=0.75,
    diamond_after_swap=diamond_after_swap,
    dynamic_after_swap=dynamic_after_swap,
) -> Simulator:
    sim = Simulator(
        blocks_per_day, num_days, tx_fee_per_eth, new_liquidity, new_liquidity_period
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
        beta,
    )
    sim.create_diamond_pool(
        Token.ETH,
        Token.USDC,
        RESERVE_X,
        RESERVE_Y,
        0.003,
        None,
        dynamic_after_swap,
        beta,
    )

    sim.create_oracle(INITIAL_PRICE, 0.05)
    return sim


if __name__ == "__main__":

    num_pools = 3

    range_initial_min_fees = [0.01, 0.05, 0.1, 0.15, 0.2]
    range_alpha1 = np.arange(0.03, 0.6, 0.03)
    range_alpha2 = [0.0012, 0.012, 0.12, 1.2]
    range_beta1 = np.arange(300, 420, 30)
    range_beta2 = [600, 6000, 60000, 600000, 6000000]
    range_gamma1 = [1 / 54, 1 / 59, 1 / 64]
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
    print("Total parameters to test:", len(parameters))

    best_result = {
        "initial_min_fees": 0,
        "alpha1": 0,
        "alpha2": 0,
        "beta1": 0,
        "beta2": 0,
        "gamma1": 0,
        "gamma2": 0,
        "tvl_ratio": 0,
    }

    if not os.path.exists("results"):
        os.makedirs("results")

    if not os.path.exists("results/optimize.csv"):
        log_f = open("results/optimize.csv", "w")
        log_f.write(
            "initial_min_fees,alpha1,alpha2,beta1,beta2,gamma1,gamma2,tvl_ratio\n"
        )
    else:
        # Remove already tested parameters
        df = pd.read_csv("results/optimize.csv")
        df.columns = df.columns.str.strip()
        tested_parameters = df[
            [
                "initial_min_fees",
                "alpha1",
                "alpha2",
                "beta1",
                "beta2",
                "gamma1",
                "gamma2",
            ]
        ].values
        print("Tested parameters:", len(tested_parameters))
        tested_parameters_tuples = [tuple(row) for row in tested_parameters]
        parameters = [p for p in parameters if tuple(p) not in tested_parameters_tuples]
        print("Remaining parameters to test:", len(parameters))
        best_result = df.iloc[df["tvl_ratio"].idxmax()].to_dict()
        print(f"Best result so far: {best_result}")
        log_f = open("results/optimize.csv", "a")

    while len(parameters) > 0:
        # Choose parameter set Randomly
        initial_min_fees, alpha1, alpha2, beta1, beta2, gamma1, gamma2 = parameters.pop(
            0
        )
        print(
            f"Running simulation with parameters: {initial_min_fees}, {alpha1}, {alpha2}, {beta1}, {beta2}, {gamma1}, {gamma2}"
        )
        start_time = time.time()

        def custom_dynamic_after_swap(pool, price_feed, volatility, block_num):
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
            sim = create_simulation(dynamic_after_swap=custom_dynamic_after_swap)
            sim.run(verbose=False)
            tvl_ratio.append(
                sim.liquidity_pools[2].total_value_locked(sim.oracle[-1])
                / sim.liquidity_pools[1].total_value_locked(sim.oracle[-1])
            )

        print(f"Simulation took {time.time() - start_time} seconds")
        print(f"TVL ratio: {np.mean(tvl_ratio)}")
        log_f.write(
            f"{initial_min_fees}, {alpha1}, {alpha2}, {beta1}, {beta2}, {gamma1}, {gamma2}, {np.mean(tvl_ratio)}\n"
        )
        log_f.flush()

        if np.mean(tvl_ratio) > best_result["tvl_ratio"]:
            best_result = {
                "initial_min_fees": initial_min_fees,
                "alpha1": alpha1,
                "alpha2": alpha2,
                "beta1": beta1,
                "beta2": beta2,
                "gamma1": gamma1,
                "gamma2": gamma2,
                "tvl_ratio": np.mean(tvl_ratio),
            }
        print(f"Best result: {best_result}")

    log_f.close()
