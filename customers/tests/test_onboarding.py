from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomerOnboardingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass123")
        self.client.login(username="tester", password="pass123")

    def test_onboarding_cash_customer(self):
        url = reverse("customer_onboarding")
        response = self.client.post(url, {
            "onboarding_type": "DIRECT",
            "full_name": "John Doe",
            "customer_id": "CUST001",
            "mobile_number": "0712345678",
            "account_number": "ACC001",
            "nearest_warehouse": 1,
            "motorcycle": 1,
            "payment_model": "CASH",
            "cash_amount": "500000",
        })
        self.assertEqual(response.status_code, 302)  # should redirect after save
