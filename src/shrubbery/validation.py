from typing import Any, Generator

import numpy as np
import pandas as pd
from sklearn.model_selection import BaseCrossValidator

from shrubbery.constants import COLUMN_INDEX_ERA
from shrubbery.observability import logger


# Numerai-specific cross-validation generator
# See also:
# * https://scikit-learn.org/stable/glossary.html#term-CV-splitter
# * https://scikit-learn.org/stable/modules/cross_validation.html
# * https://github.com/scikit-learn/scikit-learn/blob/8c9c1f27b/sklearn/model_selection/_split.py#L469  # noqa: E501
class NumeraiTimeSeriesSplitter(BaseCrossValidator):
    def __init__(self, cv: int, embargo: int) -> None:
        self._cv = cv
        self._embargo = embargo

    def get_n_splits(
        self, x: np.ndarray, y: np.ndarray, groups: Any = None
    ) -> int:  # ty: ignore[invalid-method-override]
        # See also:
        # - https://scikit-learn.org/stable/glossary.html#term-get_n_splits
        return self._cv

    def split(
        self, x: np.ndarray, y: np.ndarray, groups: Any = None
    ) -> Generator[tuple[np.ndarray, np.ndarray], None, None]:  # ty: ignore[invalid-method-override]
        # See also:
        # - https://scikit-learn.org/stable/glossary.html#term-split
        assert x is not None, 'Training vector was not provided'
        assert y is not None, 'Target values were not provided'
        assert x.shape[0] == y.shape[0], 'Mismatch of input shapes'

        eras = x[:, COLUMN_INDEX_ERA]
        all_train_eras = np.unique(eras)
        len_split = len(all_train_eras) // self._cv
        test_splits = [
            all_train_eras[i * len_split : (i + 1) * len_split]
            for i in range(self._cv)
        ]
        # Fix the last test split to have all the last eras,
        # in case the number of eras wasn't divisible by cv
        remainder = len(all_train_eras) % self._cv
        if remainder != 0:
            test_splits[-1] = np.append(
                test_splits[-1], all_train_eras[-remainder:]
            )

        train_splits = []
        for test_split in test_splits:
            test_split_max = int(np.max(test_split))
            test_split_min = int(np.min(test_split))
            # Get all of the eras that aren't in the test split
            train_split_not_embargoed = [
                e
                for e in all_train_eras
                if not (test_split_min <= int(e) <= test_split_max)
            ]
            # Embargo the train split so we have no leakage.
            # one era is length 5, so we need to embargo
            # by target_length/5 eras.
            # To be consistent for all targets, let's embargo everything
            # by 60/5 == 12 eras.
            train_split = [
                e
                for e in train_split_not_embargoed
                if abs(int(e) - test_split_max) > self._embargo
                and abs(int(e) - test_split_min) > self._embargo
            ]
            train_splits.append(train_split)

        # Convenient way to iterate over train and test splits
        training_data = pd.DataFrame(x)
        train_test_zip = zip(train_splits, test_splits)
        for train_test_split in train_test_zip:
            train_split, test_split = train_test_split
            train_split_index = training_data[COLUMN_INDEX_ERA].isin(
                train_split
            )
            test_split_index = training_data[COLUMN_INDEX_ERA].isin(test_split)
            train_split_shape = train_split_index[train_split_index].shape
            test_split_shape = test_split_index[test_split_index].shape
            logger.info(f'Train split shape: {train_split_shape}')
            logger.info(f'Test split shape: {test_split_shape}')
            # Using `.copy(deep=True)` for better performance
            train_split_array = train_split_index.copy(deep=True).to_numpy(
                dtype=np.bool_
            )
            test_split_array = test_split_index.copy(deep=True).to_numpy(
                dtype=np.bool_
            )
            yield train_split_array, test_split_array
