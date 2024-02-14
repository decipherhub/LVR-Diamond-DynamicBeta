import numpy as np
from typing import Optional, Callable

from custom_types import Token, Oracle
from pool import LiquidityPool, DiamondPool
from strategy import multi_pool_random_swap, perform_arbitrage
from dynamic_fee import (
    calculate_volatility,
    calculate_dynamic_fee,
    calculate_dynamic_beta,
)


class Simulator:
    liquidity_pools: list[LiquidityPool] = []
    oracle: Oracle = []
    volatility: list[float] = []
    blocks_per_day: int
    num_days: int
    tx_fee_per_eth: float
    new_liquidity: float
    new_liquidity_period: int

    def __init__(
        self,
        blocks_per_day: int,
        num_days: int,
        tx_fee_per_eth: float,
        new_liquidity: float,
        new_liquidity_period: int,
    ):

        self.blocks_per_day = blocks_per_day
        self.num_days = num_days
        self.tx_fee_per_eth = tx_fee_per_eth
        self.new_liquidity = new_liquidity
        self.new_liquidity_period = new_liquidity_period

    def create_liquidity_pool(
        self,
        token_x: Token,
        token_y: Token,
        reserve_x: float,
        reserve_y: float,
        fee: float,
        dyanmic_fee: bool,
    ):
        liquidity_pool = LiquidityPool(token_x, token_y, fee, dyanmic_fee)

        liquidity_pool.add_liquidity(token_x, reserve_x)
        liquidity_pool.add_liquidity(token_y, reserve_y)

        self.liquidity_pools.append(liquidity_pool)

    def create_diamond_pool(
        self,
        token_x: Token,
        token_y: Token,
        reserve_x: float,
        reserve_y: float,
        fee: float,
        dynamic_fee: bool,
        beta: float,
        dynamic_beta: bool,
        beforeHook: Optional[Callable] = None,
        afterHook: Optional[Callable] = None,
    ):
        diamond_pool = DiamondPool(
            token_x,
            token_y,
            fee,
            dynamic_fee,
            beta,
            dynamic_beta,
            beforeHook,
            afterHook,
        )

        diamond_pool.add_liquidity(token_x, reserve_x)
        diamond_pool.add_liquidity(token_y, reserve_y)

        self.liquidity_pools.append(diamond_pool)

    def create_oracle(self, initial_price: float, sigma_per_day: float):
        """
        Create an oracle for the liquidity pool using geometric Brownian motion.

        Args:
            initial_price (float): The initial price of the asset.
            sigma_per_day (float): The volatility of the asset per day.
        """
        mu = 0.0

        dt = 1 / self.blocks_per_day

        price_path_eth = np.exp(
            (mu - sigma_per_day**2 / 2) * dt
            + sigma_per_day
            * np.random.normal(
                0, np.sqrt(dt), size=(self.num_days + 2) * self.blocks_per_day - 1
            ).T
        )

        price_path_eth = np.insert(price_path_eth, 0, 1.0)
        price_path_eth = price_path_eth.cumprod()
        price_path_eth = (
            price_path_eth * initial_price / price_path_eth[self.blocks_per_day * 2]
        )

        price_path_usdc = np.ones((self.num_days + 2) * self.blocks_per_day)

        self.oracle = [
            {Token.ETH: price_path_eth[i], Token.USDC: price_path_usdc[i]}
            for i in range((self.num_days + 2) * self.blocks_per_day)
        ]
        self.volatility = calculate_volatility(
            Token.ETH, Token.USDC, self.oracle, self.blocks_per_day
        )
        self.oracle = self.oracle[self.blocks_per_day * 2 :]

    def simulate_pool(self, pools: list[LiquidityPool], block_num: int):
        price_feed = self.oracle[block_num]

        # Before Swaps
        for pool in pools:
            if isinstance(pool, DiamondPool):
                if pool.dynamic_beta:
                    pool.beta = calculate_dynamic_beta(self.volatility[block_num])
                    # print(pool.beta)
                if pool.before_swap:
                    pool.before_swap(pool, price_feed, block_num)
            else:
                if pool.dynamic_fee:
                    pool.fee = calculate_dynamic_fee(self.volatility[block_num])
                    # print(pool.fee)

        # Retail Swaps
        multi_pool_random_swap(pools, price_feed)

        # After Swaps
        for pool in pools:
            if isinstance(pool, DiamondPool):
                if pool.after_swap:
                    pool.after_swap(pool, price_feed, block_num)

            else:
                perform_arbitrage(pool, price_feed, self.tx_fee_per_eth)

    def run_block(self, block_num: int):
        self.simulate_pool(self.liquidity_pools, block_num)

    def print_snapshot(self, block_num: int):
        print(f"Block {block_num}------------------------------------")
        for pool in self.liquidity_pools:
            is_diamond = isinstance(pool, DiamondPool)
            print(f"Type of Pool: {'Diamond' if is_diamond else 'Liquidity'}")
            print(f"{pool.token_x} Reserve: {pool.reserve_x:,.2f}")
            print(f"{pool.token_y} Reserve: {pool.reserve_y:,.2f}")
            print(f"Pool Price: {pool.price:,.2f}")
            print(f"Oracle Price: {self.oracle[block_num][pool.token_x]:,.2f}")
            print(f"TVL: {pool.total_value_locked(self.oracle[block_num]):,.2f}")
            print(f"LVR: {pool.lvr:,.2f}")
            print(f"Collected Fees: {pool.collected_fees:,.2f}")
            if is_diamond:
                print(f"Vault {pool.token_x} Reserve: {pool.vault.reserve_x:,.2f}")
                print(f"Vault {pool.token_y} Reserve: {pool.vault.reserve_y:,.2f}")

    def run(self, verbose: bool = False):
        if verbose:
            self.print_snapshot(0)

        for block_num in range(self.blocks_per_day * self.num_days):
            self.run_block(block_num)

            # if verbose and (block_num + 1) % self.blocks_per_day == 0:
            if verbose and block_num == self.blocks_per_day * self.num_days - 1:
                self.print_snapshot(block_num)

            if (
                self.new_liquidity > 0
                and self.new_liquidity_period > 0
                and (block_num + 1) % self.new_liquidity_period == 0
                and block_num != 0
            ):
                tvls = [
                    pool.total_value_locked(self.oracle[block_num])
                    for pool in self.liquidity_pools
                ]
                # Seperate the new liquidity proportionally to the TVL of each pool
                for i, pool in enumerate(self.liquidity_pools):
                    new_liquidity = self.new_liquidity * (tvls[i] / sum(tvls))
                    new_reserve_x = new_liquidity / 2 / pool.price
                    new_reserve_y = new_liquidity / 2
                    pool.add_liquidity(pool.token_x, new_reserve_x)
                    pool.add_liquidity(pool.token_y, new_reserve_y)
