"""
test_ingestion_manager.py
=========================
Unit tests for vehicle ingestion tracking, status management, and API lifecycle.
"""
import unittest
from unittest.mock import patch, MagicMock
import json

from ingestion.ingestion_manager import IngestionManager, IngestionJob


class TestIngestionManager(unittest.TestCase):
    def setUp(self):
        self.manager = IngestionManager()

    def test_create_and_get_job(self):
        job = self.manager.create_job("TestMake", "TestModel")
        self.assertIsNotNone(job.job_id)
        self.assertEqual(job.make, "Testmake")
        self.assertEqual(job.model, "Testmodel")
        self.assertEqual(job.status, "QUEUED")
        self.assertEqual(job.progress_pct, 0)
        self.assertGreaterEqual(len(job.logs), 1)

        retrieved = self.manager.get_job(job.job_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.job_id, job.job_id)

    def test_list_jobs(self):
        job1 = self.manager.create_job("BrandA", "ModelA")
        job2 = self.manager.create_job("BrandB", "ModelB")
        jobs = self.manager.list_jobs()
        job_ids = [j.job_id for j in jobs]
        self.assertIn(job1.job_id, job_ids)
        self.assertIn(job2.job_id, job_ids)

    def test_job_add_log(self):
        job = IngestionJob(
            job_id="test_log_job",
            make="Toyota",
            model="Innova",
            status="RUNNING"
        )
        job.add_log("Starting layer 1", level="info", layer_id="L01")
        self.assertEqual(len(job.logs), 1)
        self.assertEqual(job.logs[0]["layer_id"], "L01")
        self.assertEqual(job.logs[0]["message"], "Starting layer 1")
        self.assertEqual(job.logs[0]["level"], "info")
        self.assertIn("timestamp", job.logs[0])

    @patch("ingestion.ingestion_manager.run_collection")
    @patch("ingestion.ingestion_manager.load_vehicle_to_graph")
    @patch("ingestion.ingestion_manager.generate_cypher_script")
    def test_run_job_lifecycle_success(self, mock_cypher, mock_graph, mock_collection):
        mock_graph.return_value = {"nodes_merged": 42, "relationships_merged": 99}
        job = self.manager.create_job("Tata", "Punch")
        
        # Execute job synchronously
        self.manager.run_job_synchronous(job.job_id)

        updated_job = self.manager.get_job(job.job_id)
        self.assertEqual(updated_job.status, "COMPLETED")
        self.assertEqual(updated_job.progress_pct, 100)
        self.assertEqual(updated_job.completed_steps, 13)
        self.assertEqual(updated_job.stats.get("nodes_merged"), 42)
        self.assertEqual(updated_job.stats.get("relationships_merged"), 99)
        self.assertIsNotNone(updated_job.completed_at)
        self.assertIsNone(updated_job.error)

    @patch("ingestion.ingestion_manager.run_collection")
    def test_run_job_lifecycle_failure(self, mock_collection):
        mock_collection.side_effect = RuntimeError("Network connection lost")
        job = self.manager.create_job("Faulty", "Car")

        self.manager.run_job_synchronous(job.job_id)

        failed_job = self.manager.get_job(job.job_id)
        self.assertEqual(failed_job.status, "FAILED")
        self.assertIn("Network connection lost", failed_job.error)
        self.assertIsNotNone(failed_job.completed_at)


if __name__ == "__main__":
    unittest.main()
