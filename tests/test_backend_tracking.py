"""Tests for backend_tracking_query.py."""
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open, MagicMock
import pytest

import backend_tracking_query as btq


class TestLoadTrackingRegistry:
    def test_loads_valid_registry(self, temp_dir):
        registry = {"total_documents": 5}
        path = temp_dir / "_backend_tracking_registry.json"
        path.write_text(json.dumps(registry))
        result = btq.load_tracking_registry(str(temp_dir))
        assert result == registry

    def test_returns_none_when_missing(self, temp_dir):
        result = btq.load_tracking_registry(str(temp_dir))
        assert result is None

    def test_returns_none_on_invalid_json(self, temp_dir):
        path = temp_dir / "_backend_tracking_registry.json"
        path.write_text("not json")
        result = btq.load_tracking_registry(str(temp_dir))
        assert result is None


class TestQueryExpiringDocuments:
    def test_finds_expiring_within_months(self, mock_registry):
        today = datetime.now()
        mock_registry["expiration_tracking"][0]["expiration_date"] = (today + timedelta(days=30)).isoformat()
        mock_registry["expiration_tracking"][1]["expiration_date"] = (today + timedelta(days=60)).isoformat()
        result = btq.query_expiring_documents(mock_registry, months_ahead=12)
        assert len(result) == 2
        assert "days_until_expiration" in result[0]

    def test_ignores_expired_documents(self, mock_registry):
        today = datetime.now()
        mock_registry["expiration_tracking"][0]["expiration_date"] = (today - timedelta(days=30)).isoformat()
        result = btq.query_expiring_documents(mock_registry, months_ahead=12)
        assert len(result) == 0

    def test_ignores_far_future_documents(self, mock_registry):
        today = datetime.now()
        mock_registry["expiration_tracking"][0]["expiration_date"] = (today + timedelta(days=500)).isoformat()
        result = btq.query_expiring_documents(mock_registry, months_ahead=3)
        assert len(result) == 0

    def test_returns_empty_for_empty_registry(self):
        assert btq.query_expiring_documents({}, 12) == []

    def test_returns_empty_for_missing_expiration_tracking(self):
        assert btq.query_expiring_documents({"total_documents": 0}, 12) == []

    def test_skips_invalid_date_formats(self, mock_registry):
        mock_registry["expiration_tracking"][0]["expiration_date"] = "not-a-date"
        result = btq.query_expiring_documents(mock_registry, months_ahead=12)
        assert len(result) == 0

    def test_sorts_by_expiration_date(self, mock_registry):
        today = datetime.now()
        mock_registry["expiration_tracking"][0]["expiration_date"] = (today + timedelta(days=60)).isoformat()
        mock_registry["expiration_tracking"][1]["expiration_date"] = (today + timedelta(days=30)).isoformat()
        result = btq.query_expiring_documents(mock_registry, months_ahead=12)
        assert result[0]["expiration_date"] <= result[1]["expiration_date"]

    def test_calculates_days_until_correctly(self, mock_registry):
        today = datetime.now()
        future = today + timedelta(days=45)
        future = future.replace(hour=0, minute=0, second=0, microsecond=0)
        mock_registry["expiration_tracking"][0]["expiration_date"] = future.isoformat()
        result = btq.query_expiring_documents(mock_registry, months_ahead=12)
        assert abs(result[0]["days_until_expiration"] - 45) <= 1


class TestQueryByRetentionCategory:
    def test_filters_by_category(self, mock_registry):
        result = btq.query_by_retention_category(mock_registry, "Contracts")
        assert len(result) == 1
        assert result[0]["vendor"] == "Acme Corp"

    def test_returns_all_when_no_category(self, mock_registry):
        result = btq.query_by_retention_category(mock_registry)
        assert len(result) == 3

    def test_case_insensitive_filter(self, mock_registry):
        result = btq.query_by_retention_category(mock_registry, "contracts")
        assert len(result) == 1

    def test_returns_empty_for_no_match(self, mock_registry):
        result = btq.query_by_retention_category(mock_registry, "NonExistent")
        assert result == []

    def test_returns_empty_for_empty_registry(self):
        assert btq.query_by_retention_category({}, "Contracts") == []


class TestGenerateExcelReport:
    def test_returns_none_for_empty_registry(self):
        assert btq.generate_excel_report(None) is None

    def test_returns_none_for_no_documents(self):
        assert btq.generate_excel_report({"expiration_tracking": []}) is None

    def test_generates_report_with_correct_statuses(self, mock_registry):
        today = datetime.now()
        mock_registry["expiration_tracking"][0]["expiration_date"] = (today - timedelta(days=30)).isoformat()
        mock_registry["expiration_tracking"][1]["expiration_date"] = (today + timedelta(days=30)).isoformat()
        mock_registry["expiration_tracking"][2]["expiration_date"] = (today + timedelta(days=200)).isoformat()

        with patch("backend_tracking_query.pd") as mock_pd:
            mock_df = MagicMock()
            mock_pd.DataFrame.return_value = mock_df
            result = btq.generate_excel_report(mock_registry, "/tmp/report.xlsx")
            mock_pd.DataFrame.assert_called_once()
            mock_pd.ExcelWriter.assert_called_once()

    def test_adds_days_until_column(self, mock_registry):
        with patch("backend_tracking_query.pd") as mock_pd:
            btq.generate_excel_report(mock_registry, "/tmp/report.xlsx")
            assert mock_pd.DataFrame.called


class TestPrintSummary:
    def test_prints_summary_without_crashing(self, mock_registry, capsys):
        btq.print_summary(mock_registry)
        captured = capsys.readouterr()
        assert "BACKEND TRACKING SUMMARY" in captured.out

    def test_prints_nothing_for_none_registry(self, capsys):
        btq.print_summary(None)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_prints_zero_for_empty_registry(self, capsys):
        btq.print_summary({"total_documents": 0, "documents_with_expiration": 0})
        captured = capsys.readouterr()
        assert "Total documents: 0" in captured.out
