"""Opt-in NSGA-II search over real validation performance and training cost."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize

from ml_training.config import TrainingConfig
from ml_training.train import run_training


class TrainingProblem(ElementwiseProblem):
    def __init__(self, args) -> None:
        super().__init__(n_var=3, n_obj=2, xl=np.array([-5.0, 0.1, -6.0]), xu=np.array([-2.5, 0.65, -2.5]))
        self.args = args
        self.runs: list[dict] = []

    def _evaluate(self, x, out, *args, **kwargs) -> None:
        learning_rate = float(10 ** x[0])
        dropout = float(x[1])
        weight_decay = float(10 ** x[2])
        config = TrainingConfig(
            manifest_path=self.args.manifest,
            output_dir=self.args.output_dir,
            image_size=self.args.image_size,
            batch_size=self.args.batch_size,
            epochs=self.args.candidate_epochs,
            learning_rate=learning_rate,
            weight_decay=weight_decay,
            dropout=dropout,
            patience=self.args.patience,
            workers=self.args.workers,
            seed=self.args.seed + len(self.runs),
            modality="fusion_env",
        )
        experiment = run_training(config)
        best_validation_f1 = max(x["validation_f1_macro"] for x in experiment["history"])
        best_validation_loss = min(x["validation_loss"] for x in experiment["history"])
        out["F"] = [1.0 - best_validation_f1, best_validation_loss]
        self.runs.append(
            {
                "experiment_id": experiment["id"],
                "learning_rate": learning_rate,
                "dropout": dropout,
                "weight_decay": weight_decay,
                "validation_f1_macro": best_validation_f1,
                "validation_loss": best_validation_loss,
            }
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", default="models")
    parser.add_argument("--population", type=int, default=8)
    parser.add_argument("--generations", type=int, default=4)
    parser.add_argument("--candidate-epochs", type=int, default=5)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    problem = TrainingProblem(args)
    result = minimize(
        problem,
        NSGA2(pop_size=args.population),
        ("n_gen", args.generations),
        seed=args.seed,
        verbose=True,
    )
    output = {
        "id": f"nsga2-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        "method": "NSGA-II",
        "objectives": ["1 - validation F1 macro", "validation cross-entropy loss"],
        "population": args.population,
        "generations": args.generations,
        "evaluations": problem.runs,
        "pareto_parameters": np.atleast_2d(result.X).tolist(),
        "pareto_objectives": np.atleast_2d(result.F).tolist(),
        "note": "The held-out test split is reported by training runs but is never an optimization objective.",
    }
    target = Path(args.output_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"experiment-{output['id']}.json"
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"experiment": output["id"], "pareto_candidates": len(np.atleast_2d(result.X))}, indent=2))


if __name__ == "__main__":
    main()
