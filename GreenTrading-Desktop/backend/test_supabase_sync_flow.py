#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation script for dashboard -> Supabase sync -> history flow.

Uses a fake in-memory Supabase service so it can run without real credentials.
This validates:
- setup payload includes entrada/stoploss
- sync emits create path and stores record
- history endpoint/service can read the stored record
- no-SIN-SETUP snapshots expose entrada/stoploss keys
"""

import io
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta

import pandas as pd

import smc_m15_service


def make_df(rows):
    return pd.DataFrame(rows)


def build_zone_trigger_data():
    now = datetime(2024, 1, 1)

    h1_rows = []
    h1_closes = [100, 103, 101, 106, 102, 108, 104, 110, 106]
    for i, close in enumerate(h1_closes):
        h1_rows.append({
            "time": now + timedelta(hours=i),
            "open": close - 1,
            "high": close + 1,
            "low": close - 2,
            "close": close
        })

    m15_rows = [
        {"time": now + timedelta(minutes=15 * 0), "open": 100, "high": 101, "low": 99, "close": 100},
        {"time": now + timedelta(minutes=15 * 1), "open": 100, "high": 103, "low": 100, "close": 102},
        {"time": now + timedelta(minutes=15 * 2), "open": 101, "high": 102, "low": 101, "close": 101.5},
        {"time": now + timedelta(minutes=15 * 3), "open": 101.5, "high": 105, "low": 102.5, "close": 104},
        {"time": now + timedelta(minutes=15 * 4), "open": 103.5, "high": 104, "low": 101, "close": 101.5},
        {"time": now + timedelta(minutes=15 * 5), "open": 101.5, "high": 102, "low": 100.5, "close": 101},
        {"time": now + timedelta(minutes=15 * 6), "open": 101, "high": 102.5, "low": 101.2, "close": 102},
        {"time": now + timedelta(minutes=15 * 7), "open": 102, "high": 106, "low": 104.5, "close": 105.5},
        {"time": now + timedelta(minutes=15 * 8), "open": 105.5, "high": 107, "low": 105, "close": 106.5},
    ]

    return make_df(h1_rows), make_df(m15_rows)


class FakeSupabaseService:
    def __init__(self):
        self.records = []
        self.next_id = 1

    def get_active_setup_by_symbol(self, strategy_id, symbol):
        for record in reversed(self.records):
            if (
                record["strategy_id"] == strategy_id
                and record["symbol"] == symbol
                and record.get("estado") not in ["TP", "SL", "DESCARTADA"]
            ):
                return record
        return None

    def get_active_setup(self, strategy_id, symbol, entrada, stoploss):
        for record in reversed(self.records):
            if (
                record["strategy_id"] == strategy_id
                and record["symbol"] == symbol
                and record["entrada"] == entrada
                and record["stoploss"] == stoploss
                and record["estado"] not in ["TP", "SL", "DESCARTADA"]
            ):
                return record
        return None

    def create_setup(self, setup_data):
        print("SUPABASE INSERT INTENT: fake")
        record = dict(setup_data)
        record["id"] = self.next_id
        self.next_id += 1
        self.records.append(record)
        print("SUPABASE OK: fake insert")
        return record

    def update_setup(self, setup_id, updates):
        for record in self.records:
            if record["id"] == setup_id:
                record.update(updates)
                print("SUPABASE OK: fake update")
                return record
        return None

    def get_setup_history(self, **kwargs):
        return list(reversed(self.records))


def main():
    original_service = smc_m15_service.supabase_service
    original_cache = dict(smc_m15_service._setup_cache)

    fake_service = FakeSupabaseService()
    smc_m15_service.supabase_service = fake_service
    smc_m15_service._setup_cache.clear()

    try:
        df_h1, df_m15 = build_zone_trigger_data()

        captured = io.StringIO()
        with redirect_stdout(captured):
            result = smc_m15_service.analyze_symbol_smc("Boom 1000 Index", df_h1, df_m15)
        output = captured.getvalue()

        assert "entrada" in result, "analysis result must include entrada"
        assert "stoploss" in result, "analysis result must include stoploss"
        assert result["entrada"] is not None, "entrada should be populated for valid setup"
        assert result["stoploss"] is not None, "stoploss should be populated for valid setup"
        assert "SUPABASE INSERT INTENT" in output, "sync flow must log insert intent"
        assert "SUPABASE OK: fake insert" in output, "fake supabase insert should succeed"
        assert len(fake_service.records) == 1, "record should be stored in fake Supabase"

        history = fake_service.get_setup_history()
        assert len(history) == 1, "history should return inserted setup"
        assert history[0]["symbol"] == "Boom 1000 Index", "history should expose inserted symbol"
        assert history[0]["entrada"] == result["entrada"], "history should preserve entrada"
        assert history[0]["stoploss"] == result["stoploss"], "history should preserve stoploss"

        sin_setup = smc_m15_service.create_sin_setup_response("Crash 500 Index", 123.45)
        assert "entrada" in sin_setup and sin_setup["entrada"] is None, "SIN SETUP should include entrada=None"
        assert "stoploss" in sin_setup and sin_setup["stoploss"] is None, "SIN SETUP should include stoploss=None"

        print("OK: analysis result includes entrada/stoploss")
        print("OK: sync flow emits SUPABASE INSERT INTENT")
        print("OK: fake Supabase insert succeeds")
        print("OK: stored record is visible in history")
        print("OK: SIN SETUP fallback exposes entrada/stoploss=None")
        print("NOTE: live Supabase table verification requires a real .env and reachable project")

    finally:
        smc_m15_service.supabase_service = original_service
        smc_m15_service._setup_cache.clear()
        smc_m15_service._setup_cache.update(original_cache)


if __name__ == "__main__":
    main()
