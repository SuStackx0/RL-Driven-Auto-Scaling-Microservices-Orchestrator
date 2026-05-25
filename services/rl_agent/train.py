"""
Standalone training script. Run directly to retrain the scaling policy:
    python train.py [--steps 100000]
"""

import argparse
import os

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import EvalCallback
from stable_baselines3.common.env_util import make_vec_env

from env import ScalingEnv


def train(total_timesteps: int = 100_000, model_path: str = "models/scaling_policy"):
    os.makedirs("models", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    train_env = make_vec_env(ScalingEnv, n_envs=4)
    eval_env  = make_vec_env(ScalingEnv, n_envs=1)

    model = PPO(
        "MlpPolicy",
        train_env,
        learning_rate=3e-4,
        n_steps=1024,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        verbose=1,
        tensorboard_log="./logs/",
    )

    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path="./models/best/",
        log_path="./logs/",
        eval_freq=5_000,
        n_eval_episodes=5,
        deterministic=True,
        render=False,
    )

    print(f"Training PPO for {total_timesteps:,} timesteps...")
    model.learn(total_timesteps=total_timesteps, callback=eval_cb, progress_bar=True)
    model.save(model_path)
    print(f"Saved → {model_path}.zip")
    return model


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=100_000)
    ap.add_argument("--out",   type=str, default="models/scaling_policy")
    args = ap.parse_args()
    train(args.steps, args.out)
