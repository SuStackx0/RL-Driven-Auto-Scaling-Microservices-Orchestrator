import numpy as np
import gymnasium as gym
from gymnasium import spaces

SERVICES = ["search", "recommendation", "payment", "auth"]
N_SERVICES = len(SERVICES)

# Simulation parameters per service
BASE_LATENCY   = [50.0,  30.0,  150.0,  80.0]   # ms at 1 replica, low load
TARGET_LATENCY = [100.0, 60.0,  300.0, 150.0]   # acceptable SLO threshold
CAPACITY_RPS   = [6.0,   10.0,   3.0,   7.0]    # sustainable RPS per replica

MAX_REPLICAS = 5
MIN_REPLICAS = 1
MAX_RPS      = 30.0


class ScalingEnv(gym.Env):
    """
    Simulated microservices environment for RL auto-scaling.

    Observation (20-dim float32, normalised to [0, 1]):
        For each of the 4 services: [avg_latency, p95_latency, error_rate, rps, instances]

    Action (MultiDiscrete [3,3,3,3]):
        Per service: 0=scale_down, 1=keep, 2=scale_up
    """

    metadata = {"render_modes": []}

    def __init__(self):
        super().__init__()
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(N_SERVICES * 5,), dtype=np.float32
        )
        self.action_space = spaces.MultiDiscrete([3] * N_SERVICES)
        self._step = 0

    # ------------------------------------------------------------------
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.instances = np.ones(N_SERVICES, dtype=np.float32)
        self.rps = self.np_random.uniform(1.0, 6.0, N_SERVICES).astype(np.float32)
        self._step = 0
        return self._obs(), {}

    # ------------------------------------------------------------------
    def step(self, action):
        # Apply scaling actions
        for i, a in enumerate(action):
            if a == 0:
                self.instances[i] = max(MIN_REPLICAS, self.instances[i] - 1)
            elif a == 2:
                self.instances[i] = min(MAX_REPLICAS, self.instances[i] + 1)

        # Evolve load: random bursts every ~15 steps
        self._step += 1
        if self._step % 15 == 0 and self.np_random.random() < 0.5:
            burst_i = self.np_random.integers(N_SERVICES)
            self.rps[burst_i] = self.np_random.uniform(18.0, 28.0)
        else:
            self.rps += self.np_random.uniform(-1.5, 2.0, N_SERVICES)
            self.rps = np.clip(self.rps, 1.0, MAX_RPS)

        reward = self._compute_reward()
        terminated = self._step >= 500
        return self._obs(), reward, terminated, False, {}

    # ------------------------------------------------------------------
    def _latency(self, i):
        load_ratio = self.rps[i] / (self.instances[i] * CAPACITY_RPS[i] + 1e-6)
        spike = max(0.0, load_ratio - 0.7) * 3.0
        avg = BASE_LATENCY[i] * (1.0 + spike)
        p95 = avg * self.np_random.uniform(1.1, 1.6)
        return avg, p95

    def _error_rate(self, i, latency):
        ratio = latency / TARGET_LATENCY[i]
        if ratio < 1.0:
            return self.np_random.uniform(0.0, 0.015)
        elif ratio < 2.0:
            return self.np_random.uniform(0.02, 0.08)
        return self.np_random.uniform(0.1, 0.35)

    def _obs(self):
        obs = []
        for i in range(N_SERVICES):
            avg, p95 = self._latency(i)
            err = self._error_rate(i, avg)
            obs += [
                min(avg / (TARGET_LATENCY[i] * 3), 1.0),
                min(p95 / (TARGET_LATENCY[i] * 3), 1.0),
                min(err, 1.0),
                min(self.rps[i] / MAX_RPS, 1.0),
                (self.instances[i] - MIN_REPLICAS) / (MAX_REPLICAS - MIN_REPLICAS),
            ]
        return np.array(obs, dtype=np.float32)

    def _compute_reward(self):
        reward = 0.0
        for i in range(N_SERVICES):
            avg, _ = self._latency(i)
            err = self._error_rate(i, avg)
            ratio = avg / TARGET_LATENCY[i]

            # Latency component
            if ratio < 0.7:
                reward += 1.5
            elif ratio < 1.0:
                reward += 1.0
            elif ratio < 1.5:
                reward -= 0.5
            else:
                reward -= 2.0

            # Error rate component
            reward -= err * 8.0

            # Cost component: penalise over-provisioning
            reward -= 0.15 * (self.instances[i] - 1)

        return float(reward)
