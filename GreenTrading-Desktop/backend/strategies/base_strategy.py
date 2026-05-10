#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base contract for strategy engines.
"""

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Abstract base class for all strategies."""

    strategy_id: str = ""
    strategy_name: str = ""

    @abstractmethod
    def analyze(self, symbol, df_h1, df_m15, df_m1=None, **kwargs):
        """
        Analyze a symbol and return a strategy result dictionary.

        Args:
            symbol: Trading symbol identifier.
            df_h1: H1 candles DataFrame.
            df_m15: M15 candles DataFrame.
            df_m1: Optional M1 candles DataFrame.
            **kwargs: Optional strategy-specific context.

        Returns:
            dict: Strategy analysis payload.
        """
        raise NotImplementedError
