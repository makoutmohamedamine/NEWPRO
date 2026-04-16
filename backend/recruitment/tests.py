from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Candidate
from .services import seed_demo_content


class RecruitmentApiTests(TestCase):
    def setUp(self):
        seed_demo_content()

    def test_dashboard_returns_seeded_content(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["stats"]["totalCandidates"], 3)
        self.assertTrue(payload["jobProfiles"])

    def test_upload_candidate_parses_text_cv(self):
        content = (
            "Hind Tazi\n"
            "hind.tazi@example.com\n"
            "+212600000000\n"
            "Python Django React SQL Power BI Master 2020 2024"
        ).encode("utf-8")
        upload = SimpleUploadedFile("hind_tazi_cv.txt", content, content_type="text/plain")

        response = self.client.post(
            reverse("candidate-upload"),
            {"cv": upload, "source": Candidate.Source.MANUAL},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Candidate.objects.count(), 4)
        self.assertEqual(response.json()["candidate"]["fullName"], "Hind Tazi")
