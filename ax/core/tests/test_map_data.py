# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# pyre-strict


import numpy as np
import pandas as pd
from ax.core.data import Data
from ax.core.map_data import MapData, MapKeyInfo
from ax.utils.common.testutils import TestCase


class MapDataTest(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.df = pd.DataFrame(
            [
                {
                    "arm_name": "0_0",
                    "epoch": 0,
                    "mean": 3.0,
                    "sem": 0.3,
                    "trial_index": 0,
                    "metric_name": "a",
                },
                # repeated arm 0_0
                {
                    "arm_name": "0_0",
                    "epoch": 0,
                    "mean": 2.0,
                    "sem": 0.2,
                    "trial_index": 1,
                    "metric_name": "a",
                },
                {
                    "arm_name": "0_0",
                    "epoch": 0,
                    "mean": 1.8,
                    "sem": 0.3,
                    "trial_index": 1,
                    "metric_name": "b",
                },
                {
                    "arm_name": "0_1",
                    "epoch": 0,
                    "mean": 4.0,
                    "sem": 0.6,
                    "trial_index": 1,
                    "metric_name": "a",
                },
                {
                    "arm_name": "0_1",
                    "epoch": 0,
                    "mean": 3.7,
                    "sem": 0.5,
                    "trial_index": 1,
                    "metric_name": "b",
                },
                {
                    "arm_name": "0_1",
                    "epoch": 1,
                    "mean": 0.5,
                    "sem": None,
                    "trial_index": 1,
                    "metric_name": "a",
                },
                {
                    "arm_name": "0_1",
                    "epoch": 1,
                    "mean": 3.0,
                    "sem": None,
                    "trial_index": 1,
                    "metric_name": "b",
                },
            ]
        )

        self.map_key_infos = [
            MapKeyInfo(
                key="epoch",
                default_value=0,
            )
        ]

        self.mmd = MapData(df=self.df, map_key_infos=self.map_key_infos)

    def test_df(self) -> None:
        df = self.mmd.df
        self.assertEqual(set(df["trial_index"].drop_duplicates()), {0, 1})

    def test_map_key_info(self) -> None:
        self.assertEqual(self.map_key_infos, self.mmd.map_key_infos)

        self.assertEqual(self.mmd.map_key_infos[0].key, "epoch")
        self.assertEqual(self.mmd.map_key_infos[0].default_value, 0)
        self.assertEqual(self.mmd.map_key_infos[0].value_type, int)

    def test_init(self) -> None:
        empty = MapData()
        self.assertTrue(empty.map_df.empty)
        # Check that the required columns do not include any map keys.
        self.assertEqual(empty.REQUIRED_COLUMNS, empty.required_columns())
        self.assertEqual(set(empty.map_df.columns), empty.REQUIRED_COLUMNS)

        # Initialize empty with map key infos.
        empty = MapData(map_key_infos=self.map_key_infos)
        self.assertTrue(empty.map_df.empty)
        # Check that the required columns include the map keys.
        self.assertEqual(
            empty.REQUIRED_COLUMNS.union(["epoch"]), empty.required_columns()
        )
        self.assertEqual(set(empty.map_df.columns), empty.required_columns())

        with self.assertRaisesRegex(ValueError, "map_key_infos may be `None` iff"):
            MapData(df=self.df, map_key_infos=None)

    def test_properties(self) -> None:
        self.assertEqual(self.mmd.map_key_infos, self.map_key_infos)
        self.assertEqual(self.mmd.map_keys, ["epoch"])
        self.assertEqual(self.mmd.map_key_to_type, {"epoch": int})

    def test_clone(self) -> None:
        self.mmd._db_id = 1234
        clone = self.mmd.clone()
        # Make sure the two objects are equal.
        self.assertTrue(clone.map_df.equals(self.mmd.map_df))
        self.assertTrue(clone.df.equals(self.mmd.df))
        self.assertEqual(clone.map_key_infos, self.mmd.map_key_infos)
        self.assertEqual(clone.description, self.mmd.description)
        # Make sure it's not the original object or df.
        self.assertIsNot(clone, self.mmd)
        self.assertIsNot(clone.map_df, self.mmd.map_df)
        self.assertIsNone(clone._db_id)

    def test_combine(self) -> None:
        data = MapData.from_multiple_map_data([])
        self.assertEqual(data.map_df.size, 0)

        mmd_double = MapData.from_multiple_map_data([self.mmd, self.mmd])
        self.assertEqual(mmd_double.map_df.size, 2 * self.mmd.map_df.size)
        self.assertEqual(mmd_double.map_key_infos, self.mmd.map_key_infos)

        different_map_df = pd.DataFrame(
            [
                {
                    "arm_name": "0_3",
                    "timestamp": 11,
                    "mean": 2.0,
                    "sem": 0.2,
                    "trial_index": 1,
                    "metric_name": "a",
                },
                {
                    "arm_name": "0_3",
                    "timestamp": 18,
                    "mean": 1.8,
                    "sem": 0.3,
                    "trial_index": 1,
                    "metric_name": "b",
                },
            ]
        )
        different_map_key_infos = [MapKeyInfo(key="timestamp", default_value=0.0)]
        different_mmd = MapData(
            df=different_map_df, map_key_infos=different_map_key_infos
        )

        combined = MapData.from_multiple_map_data([self.mmd, different_mmd])
        self.assertEqual(
            len(combined.map_df), len(self.mmd.map_df) + len(different_mmd.map_df)
        )
        self.assertEqual(combined.map_df.columns.size, self.mmd.map_df.columns.size + 1)
        self.assertEqual(
            combined.map_key_infos, self.map_key_infos + different_map_key_infos
        )

        combined_subset = MapData.from_multiple_map_data(
            [self.mmd, different_mmd], ["a"]
        )
        self.assertTrue((combined_subset.map_df["metric_name"] == "a").all())

        data_df = pd.DataFrame(
            [
                {
                    "arm_name": "0_4",
                    "mean": 2.0,
                    "sem": 0.2,
                    "trial_index": 1,
                    "metric_name": "a",
                },
                {
                    "arm_name": "0_4",
                    "mean": 1.8,
                    "sem": 0.3,
                    "trial_index": 1,
                    "metric_name": "b",
                },
            ]
        )
        data = Data(df=data_df)

        downcast_combined = MapData.from_multiple_data([self.mmd, data])
        self.assertEqual(
            len(downcast_combined.map_df), len(self.mmd.map_df) + len(data.df)
        )
        self.assertEqual(
            downcast_combined.map_df.columns.size, self.mmd.map_df.columns.size
        )
        self.assertEqual(downcast_combined.map_key_infos, self.map_key_infos)

        # Check that the Data's rows' epoch cell has the correct default value
        self.assertTrue(
            (
                downcast_combined.map_df[downcast_combined.map_df["arm_name"] == "0_4"][
                    "epoch"
                ]
                == self.mmd.map_key_infos[0].default_value
            ).all()
        )

    def test_from_map_evaluations(self) -> None:
        for sem in (0.5, None):
            eval1 = (3.7, sem) if sem is not None else 3.7
            eval2 = (3.8, sem) if sem is not None else 3.8
            map_data = MapData.from_map_evaluations(
                evaluations={
                    "0_1": [
                        ({"f1": 1.0, "f2": 0.5}, {"b": eval1}),
                        ({"f1": 1.0, "f2": 0.75}, {"b": eval2}),
                    ]
                },
                trial_index=0,
            )
            self.assertEqual(map_data.map_df["sem"].isnull().all(), sem is None)
            self.assertEqual(len(map_data.map_df), 2)
            self.assertEqual(set(map_data.map_keys), {"f1", "f2"})

        with self.assertRaisesRegex(
            ValueError, "Inconsistent map_key sets in evaluations"
        ):
            MapData.from_map_evaluations(
                evaluations={
                    "0_1": [
                        ({"f1": 1.0, "f2": 0.5}, {"b": (3.7, 0.5)}),
                    ]
                },
                map_key_infos=[MapKeyInfo(key="f1", default_value=0.0)],
                trial_index=0,
            )

    def test_upcast(self) -> None:
        fresh = MapData(df=self.df, map_key_infos=self.map_key_infos)
        self.assertIsNone(fresh._memo_df)  # Assert df is not cached before first call

        self.assertEqual(
            fresh.df.columns.size,
            fresh.map_df.columns.size,
        )

        self.assertIsNotNone(fresh._memo_df)  # Assert df is cached after first call

        self.assertTrue(
            fresh.df.equals(
                fresh.map_df.sort_values(fresh.map_keys).drop_duplicates(
                    MapData.DEDUPLICATE_BY_COLUMNS, keep="last"
                )
            )
        )

    def test_latest(self) -> None:
        seed = 8888

        arm_names = ["0_0", "1_0", "2_0", "3_0"]
        max_epochs = [25, 50, 75, 100]
        metric_names = ["a", "b"]
        large_map_df = pd.DataFrame(
            [
                {
                    "arm_name": arm_name,
                    "epoch": epoch + 1,
                    "mean": epoch * 0.1,
                    "sem": 0.1,
                    "trial_index": trial_index,
                    "metric_name": metric_name,
                }
                for metric_name in metric_names
                for trial_index, (arm_name, max_epoch) in enumerate(
                    zip(arm_names, max_epochs)
                )
                for epoch in range(max_epoch)
            ]
        )
        large_map_data = MapData(df=large_map_df, map_key_infos=self.map_key_infos)

        shuffled_large_map_df = large_map_data.map_df.groupby(
            MapData.DEDUPLICATE_BY_COLUMNS
        ).sample(frac=1, random_state=seed)
        shuffled_large_map_data = MapData(
            df=shuffled_large_map_df, map_key_infos=self.map_key_infos
        )

        for rows_per_group in [1, 40]:
            large_map_data_latest = large_map_data.latest(rows_per_group=rows_per_group)

            if rows_per_group == 1:
                self.assertTrue(
                    large_map_data_latest.map_df.groupby("metric_name")
                    .epoch.transform(lambda col: set(col) == set(max_epochs))
                    .all()
                )

            # when rows_per_group is larger than the number of rows
            # actually observed in a group
            actual_rows_per_group = large_map_data_latest.map_df.groupby(
                MapData.DEDUPLICATE_BY_COLUMNS
            ).size()
            expected_rows_per_group = np.minimum(
                large_map_data_latest.map_df.groupby(
                    MapData.DEDUPLICATE_BY_COLUMNS
                ).epoch.max(),
                rows_per_group,
            )
            self.assertTrue(actual_rows_per_group.equals(expected_rows_per_group))

            # behavior should be consistent even if map_keys are not in ascending order
            shuffled_large_map_data_latest = shuffled_large_map_data.latest(
                rows_per_group=rows_per_group
            )
            self.assertTrue(
                shuffled_large_map_data_latest.map_df.equals(
                    large_map_data_latest.map_df
                )
            )

    def test_subsample(self) -> None:
        arm_names = ["0_0", "1_0", "2_0", "3_0"]
        max_epochs = [25, 50, 75, 100]
        metric_names = ["a", "b"]
        large_map_df = pd.DataFrame(
            [
                {
                    "arm_name": arm_name,
                    "epoch": epoch + 1,
                    "mean": epoch * 0.1,
                    "sem": 0.1,
                    "trial_index": trial_index,
                    "metric_name": metric_name,
                }
                for metric_name in metric_names
                for trial_index, (arm_name, max_epoch) in enumerate(
                    zip(arm_names, max_epochs)
                )
                for epoch in range(max_epoch)
            ]
        )
        large_map_data = MapData(df=large_map_df, map_key_infos=self.map_key_infos)
        large_map_df_sparse_metric = pd.DataFrame(
            [
                {
                    "arm_name": arm_name,
                    "epoch": epoch + 1,
                    "mean": epoch * 0.1,
                    "sem": 0.1,
                    "trial_index": trial_index,
                    "metric_name": metric_name,
                }
                for metric_name in metric_names
                for trial_index, (arm_name, max_epoch) in enumerate(
                    zip(arm_names, max_epochs)
                )
                for epoch in range(max_epoch if metric_name == "a" else max_epoch // 5)
            ]
        )
        large_map_data_sparse_metric = MapData(
            df=large_map_df_sparse_metric, map_key_infos=self.map_key_infos
        )

        # test keep_every
        subsample = large_map_data.subsample(keep_every=10)
        self.assertEqual(len(subsample.map_df), 52)
        subsample = large_map_data.subsample(keep_every=25)
        self.assertEqual(len(subsample.map_df), 20)
        subsample = large_map_data.subsample(limit_rows_per_group=7)
        self.assertEqual(len(subsample.map_df), 36)
        # test passing specific map_key
        subsample = large_map_data.subsample(map_key="epoch", keep_every=10)
        self.assertEqual(len(subsample.map_df), 52)

        # test limit_rows_per_group
        subsample = large_map_data.subsample(limit_rows_per_group=1)
        self.assertEqual(len(subsample.map_df), 8)
        subsample = large_map_data.subsample(limit_rows_per_group=7)
        self.assertEqual(len(subsample.map_df), 36)
        subsample = large_map_data.subsample(limit_rows_per_group=10)
        self.assertEqual(len(subsample.map_df), 52)
        subsample = large_map_data.subsample(limit_rows_per_group=1000)
        self.assertEqual(len(subsample.map_df), 500)

        # test limit_rows_per_metric
        subsample = large_map_data.subsample(limit_rows_per_metric=50)
        self.assertEqual(len(subsample.map_df), 100)
        subsample = large_map_data.subsample(limit_rows_per_metric=65)
        self.assertEqual(len(subsample.map_df), 128)
        subsample = large_map_data.subsample(limit_rows_per_metric=1000)
        self.assertEqual(len(subsample.map_df), 500)

        # test include_first_last
        subsample = large_map_data.subsample(
            limit_rows_per_metric=20, include_first_last=True
        )
        self.assertEqual(len(subsample.map_df), 40)
        # check that we 1 and 100 are included
        self.assertEqual(subsample.map_df["epoch"].min(), 1)
        self.assertEqual(subsample.map_df["epoch"].max(), 100)
        subsample = large_map_data.subsample(
            limit_rows_per_metric=20, include_first_last=False
        )
        self.assertEqual(len(subsample.map_df), 40)
        self.assertEqual(subsample.map_df["epoch"].min(), 1)
        self.assertEqual(subsample.map_df["epoch"].max(), 92)

        # test limit_rows_per_metric when some metrics are sparsely
        # reported (we shouldn't subsample those)
        subsample = large_map_data_sparse_metric.subsample(
            limit_rows_per_metric=100, include_first_last=False
        )
        map_df = large_map_data_sparse_metric.map_df
        subsample_map_df = subsample.map_df
        self.assertEqual(
            len(subsample_map_df[subsample_map_df["metric_name"] == "a"]), 85
        )
        self.assertEqual(
            len(subsample_map_df[subsample_map_df["metric_name"] == "b"]),
            len(map_df[map_df["metric_name"] == "b"]),
        )
