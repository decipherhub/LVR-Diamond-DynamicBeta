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
        return self.sim.volatility[self.current_step]

    def _take_action(self, action):
        beta = action[0]
        self.sim.liquidity_pools[2].beta = beta
        self.sim.run_block(self.current_step)

    def step(self, action):
        # Execute one time step within the environment
        self._take_action(action)

        reward = self._calculate_value() - 1

        # reward *= self.current_step / MAX_STEPS

        self.current_step += 1

        done = self.current_step == len(self.sim.oracle) - 1

        obs = self._next_observation()

        return obs, reward, done, {}

    def reset(self):
        # Reset the state of the environment to an initial state

        self.sim = create_simulation()
        self.current_step = 0

        return self._next_observation()

    def render(self, mode="human", close=False):
        # Render the environment to the screen
        pass

    def _calculate_value(self):
        tvl_of_dynamic_beta = self.sim.liquidity_pools[2].total_value_locked(
            self.sim.oracle[self.current_step]
        )
        tvl_of_cfmm = self.sim.liquidity_pools[0].total_value_locked(
            self.sim.oracle[self.current_step]
        )
        return tvl_of_dynamic_beta / tvl_of_cfmm
