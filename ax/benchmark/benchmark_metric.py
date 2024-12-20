# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from typing import Any

from ax.core.base_trial import BaseTrial
from ax.core.batch_trial import BatchTrial
from ax.core.data import Data

from ax.core.map_data import MapData, MapKeyInfo
from ax.core.map_metric import MapMetric
from ax.core.metric import Metric, MetricFetchE, MetricFetchResult
from ax.utils.common.result import Err, Ok
from pyre_extensions import none_throws


def _get_no_metadata_msg(trial_index: int) -> str:
    return f"No metadata available for trial {trial_index}."


def _get_no_metadata_err(trial: BaseTrial) -> Err[Data, MetricFetchE]:
    return Err(
        MetricFetchE(
            message=_get_no_metadata_msg(trial_index=trial.index),
            exception=None,
        )
    )


def _validate_trial_and_kwargs(
    trial: BaseTrial, class_name: str, **kwargs: Any
) -> None:
    """
    Validate that:
    - Kwargs are empty
    - No arms within a BatchTrial have been abandoned
    """
    if len(kwargs) > 0:
        raise NotImplementedError(
            f"Arguments {set(kwargs)} are not supported in "
            f"{class_name}.fetch_trial_data."
        )
    if isinstance(trial, BatchTrial) and len(trial.abandoned_arms) > 0:
        raise NotImplementedError(
            "BenchmarkMetric does not support abandoned arms in batch trials."
        )


class BenchmarkMetric(Metric):
    """A generic metric used for observed values produced by Ax Benchmarks.

    Compatible with results generated by `BenchmarkRunner`.
    """

    def __init__(
        self,
        name: str,
        # Needed to be boolean (not None) for validation of MOO opt configs
        lower_is_better: bool,
        observe_noise_sd: bool = True,
    ) -> None:
        """
        Args:
            name: Name of the metric.
            lower_is_better: If `True`, lower metric values are considered better.
            observe_noise_sd: If `True`, the standard deviation of the observation
                noise is included in the `sem` column of the the returned data.
                If `False`, `sem` is set to `None` (meaning that the model will
                have to infer the noise level).
        """
        super().__init__(name=name, lower_is_better=lower_is_better)
        # Declare `lower_is_better` as bool (rather than optional as in the base class)
        self.lower_is_better: bool = lower_is_better
        self.observe_noise_sd: bool = observe_noise_sd

    def fetch_trial_data(self, trial: BaseTrial, **kwargs: Any) -> MetricFetchResult:
        """
        Args:
            trial: The trial from which to fetch data.
            kwargs: Unsupported and will raise an exception.

        Returns:
            A MetricFetchResult containing the data for the requested metric.
        """
        _validate_trial_and_kwargs(
            trial=trial, class_name=self.__class__.__name__, **kwargs
        )
        if len(trial.run_metadata) == 0:
            return _get_no_metadata_err(trial=trial)

        df = trial.run_metadata["benchmark_metadata"].dfs[self.name]
        if df["step"].nunique() > 1:
            raise ValueError(
                f"Trial {trial.index} has data from multiple time steps. This is"
                " not supported by `BenchmarkMetric`; use `BenchmarkMapMetric`."
            )
        df = df.drop(columns=["step", "virtual runtime"])
        if not self.observe_noise_sd:
            df["sem"] = None
        return Ok(value=Data(df=df))


class BenchmarkMapMetric(MapMetric):
    # pyre-fixme: Inconsistent override [15]: `map_key_info` overrides attribute
    # defined in `MapMetric` inconsistently. Type `MapKeyInfo[int]` is not a
    # subtype of the overridden attribute `MapKeyInfo[float]`
    map_key_info: MapKeyInfo[int] = MapKeyInfo(key="step", default_value=0)

    def __init__(
        self,
        name: str,
        # Needed to be boolean (not None) for validation of MOO opt configs
        lower_is_better: bool,
        observe_noise_sd: bool = True,
    ) -> None:
        """
        Args:
            name: Name of the metric.
            lower_is_better: If `True`, lower metric values are considered better.
            observe_noise_sd: If `True`, the standard deviation of the observation
                noise is included in the `sem` column of the the returned data.
                If `False`, `sem` is set to `None` (meaning that the model will
                have to infer the noise level).
        """
        super().__init__(name=name, lower_is_better=lower_is_better)
        # Declare `lower_is_better` as bool (rather than optional as in the base class)
        self.lower_is_better: bool = lower_is_better
        self.observe_noise_sd: bool = observe_noise_sd

    @classmethod
    def is_available_while_running(cls) -> bool:
        return True

    def fetch_trial_data(self, trial: BaseTrial, **kwargs: Any) -> MetricFetchResult:
        """
        If the trial has been completed, look up the ``sim_start_time`` and
        ``sim_completed_time`` on the corresponding ``SimTrial``, and return all
        data from keys 0, ..., ``sim_completed_time - sim_start_time``. If the
        trial has not completed, return all data from keys 0, ..., ``sim_runtime
        - sim_start_time``.

        Args:
            trial: The trial from which to fetch data.
            kwargs: Unsupported and will raise an exception.

        Returns:
            A MetricFetchResult containing the data for the requested metric.
        """
        _validate_trial_and_kwargs(
            trial=trial, class_name=self.__class__.__name__, **kwargs
        )
        if len(trial.run_metadata) == 0:
            return _get_no_metadata_err(trial=trial)

        metadata = trial.run_metadata["benchmark_metadata"]

        backend_simulator = metadata.backend_simulator

        if backend_simulator is None:
            max_t = float("inf")
        else:
            sim_trial = none_throws(
                backend_simulator.get_sim_trial_by_index(trial.index)
            )
            # The BackendSimulator distinguishes between queued and running
            # trials "for testing particular initialization cases", but these
            # are all "running" to Scheduler.
            # start_time = none_throws(sim_trial.sim_queued_time)
            start_time = none_throws(sim_trial.sim_start_time)

            if sim_trial.sim_completed_time is None:  # Still running
                max_t = backend_simulator.time - start_time
            else:
                if sim_trial.sim_completed_time > backend_simulator.time:
                    raise RuntimeError(
                        "The trial's completion time is in the future! This is "
                        f"unexpected. {sim_trial.sim_completed_time=}, "
                        f"{backend_simulator.time=}"
                    )
                # Completed, may have stopped early
                max_t = none_throws(sim_trial.sim_completed_time) - start_time

        df = (
            metadata.dfs[self.name]
            .loc[lambda x: x["virtual runtime"] <= max_t]
            .drop(columns=["virtual runtime"])
            .reset_index(drop=True)
            # Just in case the key was renamed by a subclass
            .rename(columns={"step": self.map_key_info.key})
        )
        if not self.observe_noise_sd:
            df["sem"] = None

        return Ok(value=MapData(df=df, map_key_infos=[self.map_key_info]))
