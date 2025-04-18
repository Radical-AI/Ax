#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict

import os


def is_running_in_papermill() -> bool:
    return os.environ.get("RUNNING_IN_PAPERMILL") == "True"
