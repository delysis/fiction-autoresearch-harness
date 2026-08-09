import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fiction_harness.shared_endpoint import SharedEndpointAdmission


class SharedEndpointAdmissionTests(unittest.TestCase):
    def test_lease_records_and_releases_declared_context(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "leases.json"
            admission = SharedEndpointAdmission(
                state,
                parallel_slots=2,
                slot_context_tokens=100,
                reserved_slot_tokens=0,
                context_budget_tokens=100,
            )
            with admission.acquire(
                owner="test",
                prompt_hash="abc",
                prompt_tokens=40,
                completion_tokens=10,
            ) as lease:
                payload = json.loads(state.read_text())
                self.assertEqual(payload["leases"][0]["lease_id"], lease.lease_id)
                self.assertEqual(payload["leases"][0]["admitted_tokens"], 50)
            self.assertEqual(json.loads(state.read_text())["leases"], [])

    def test_rejects_single_request_over_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            admission = SharedEndpointAdmission(
                Path(temp) / "leases.json",
                slot_context_tokens=100,
                reserved_slot_tokens=0,
                context_budget_tokens=100,
            )
            with self.assertRaises(ValueError):
                admission.acquire(
                    owner="test",
                    prompt_hash="abc",
                    prompt_tokens=90,
                    completion_tokens=11,
                )

    def test_reaps_dead_process_lease(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "leases.json"
            state.write_text(
                json.dumps(
                    {
                        "leases": [
                            {
                                "lease_id": "dead",
                                "pid": 99999999,
                                "admitted_tokens": 100,
                            }
                        ]
                    }
                )
            )
            admission = SharedEndpointAdmission(
                state,
                parallel_slots=1,
                slot_context_tokens=100,
                reserved_slot_tokens=0,
                context_budget_tokens=100,
            )
            with patch.object(admission, "_pid_alive", return_value=False):
                lease = admission.acquire(
                    owner="test",
                    prompt_hash="abc",
                    prompt_tokens=50,
                    completion_tokens=10,
                )
            admission.release(lease.lease.lease_id)


if __name__ == "__main__":
    unittest.main()
