from scripts.benchmark_pipeline import processing_seconds, result_identity


def test_processing_seconds_supports_baseline_job_shape():
    job = {
        "started_at": "2026-08-12T12:00:00+00:00",
        "finished_at": "2026-08-12T12:00:03.250000+00:00",
    }

    assert processing_seconds(job) == 3.25


def test_processing_seconds_supports_durable_attempt_history():
    job = {"attempt_history": [{"duration_ms": 1250}, {"duration_ms": 750}]}

    assert processing_seconds(job) == 2.0


def test_result_identity_falls_back_for_baseline_documents():
    job = {"document": {"id": 7, "generated_filename": "K_Acme_MSA_007.pdf"}}

    assert result_identity(job) == "K_Acme_MSA_007.pdf"
