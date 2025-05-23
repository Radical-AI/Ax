#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

from typing import Any

import pandas as pd
import plotly.graph_objs as go
from ax.adapter.base import Adapter
from ax.plot.base import AxPlotConfig, AxPlotTypes, DECIMALS
from ax.plot.helper import get_plot_data
from ax.utils.stats.statstools import marginal_effects
from plotly import subplots


def plot_marginal_effects(model: Adapter, metric: str) -> AxPlotConfig:
    """
    Calculates and plots the marginal effects -- the effect of changing one
    factor away from the randomized distribution of the experiment and fixing it
    at a particular level.

    Args:
        model: Model to use for estimating effects
        metric: The metric for which to plot marginal effects.

    Returns:
        AxPlotConfig of the marginal effects
    """
    plot_data, _, _ = get_plot_data(model, {}, {metric})

    arm_dfs = []
    for arm in plot_data.in_sample.values():
        arm_df = pd.DataFrame(arm.parameters, index=[arm.name])
        arm_df["mean"] = arm.y_hat[metric]
        arm_df["sem"] = arm.se_hat[metric]
        arm_dfs.append(arm_df)
    effect_table = marginal_effects(pd.concat(arm_dfs, axis=0))

    varnames = effect_table["Name"].unique()
    # pyre-fixme[33]: Given annotation cannot contain `Any`.
    data: list[Any] = []
    for varname in varnames:
        var_df = effect_table[effect_table["Name"] == varname]
        data += [
            go.Bar(
                x=var_df["Level"],
                y=var_df["Beta"],
                error_y={"type": "data", "array": var_df["SE"]},
                name=varname,
            )
        ]
    fig = subplots.make_subplots(
        cols=len(varnames),
        rows=1,
        subplot_titles=list(varnames),
        print_grid=False,
        shared_yaxes=True,
    )
    for idx, item in enumerate(data):
        fig.append_trace(item, 1, idx + 1)
    fig.layout.showlegend = False
    # fig.layout.margin = go.layout.Margin(l=2, r=2)
    fig.layout.title = "Marginal Effects by Factor"
    fig.layout.yaxis = {
        "title": "% higher than experiment average",
        "hoverformat": f".{DECIMALS}f",
    }
    # pyre-fixme[6]: For 1st argument expected `Dict[str, typing.Any]` but got `Figure`.
    return AxPlotConfig(data=fig, plot_type=AxPlotTypes.GENERIC)
