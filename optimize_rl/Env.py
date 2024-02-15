import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
simulation_dir = os.path.join(parent_dir, "simulation")

sys.path.insert(0, simulation_dir)

import gym
from gym import spaces
import numpy as np


from main import create_simulation


class LVREnv(gym.Env):
    def __init__(self):
        super(LVREnv, self).__init__()

        self.action_space = spaces.Box(
            low=0, high=1, shape=(1,), dtype=np.float32
        )  # beta
        self.observation_space = spaces.Box(
            low=0, high=1, shape=(1,), dtype=np.float32
        )  # volatility

    def _next_observation(self):
        mean_volatilities = 372.3109369150782
        std_volatilities = 287.00165015363797
        return (
            self.sim.volatility[self.current_step] - mean_volatilities
        ) / std_volatilities

    def _take_action(self, action):
        beta = action[0]
        self.sim.liquidity_pools[2].beta = beta
        self.sim.after_swap(self.current_step)

    def step(self, action):
        # Execute one time step within the environment
        before_tvl_dynamic, before_tvl_diamond = self._calculate_value()

        self._take_action(action)

        self.current_step += 1

        self.sim.before_swap(self.current_step)
        self.sim.retail_swap(self.current_step)

        after_tvl_dynamic, after_tvl_diamond = self._calculate_value()

        reward = (
            after_tvl_dynamic / before_tvl_dynamic
            - after_tvl_diamond / before_tvl_diamond
        ) * 1e6

        # reward *= self.current_step / MAX_STEPS

        done = self.current_step == len(self.sim.oracle) - 1

        obs = self._next_observation()

        return obs, reward, done, {}

    def reset(self):
        # Reset the state of the environment to an initial state

        self.sim = create_simulation()
        self.sim.liquidity_pools[2].before_swap = None
        self.current_step = 0

        self.sim.before_swap(self.current_step)
        self.sim.retail_swap(self.current_step)

        return self._next_observation()

    def render(self, mode="human", close=False):
        # Render the environment to the screen
        pass

    def _calculate_value(self):
        tvl_of_dynamic_beta = self.sim.liquidity_pools[2].total_value_locked(
            self.sim.oracle[self.current_step]
        )
        tvl_of_diamond = self.sim.liquidity_pools[1].total_value_locked(
            self.sim.oracle[self.current_step]
        )
        tvl_of_cfmm = self.sim.liquidity_pools[0].total_value_locked(
            self.sim.oracle[self.current_step]
        )
        return tvl_of_dynamic_beta, tvl_of_diamond
