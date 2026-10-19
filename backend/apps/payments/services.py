import random
import uuid
from decimal import Decimal

class MockPaymentResult:
    def __init__(self, is_success: bool, provider_ref: str = "", error_message: str = ""):
        self.is_success = is_success
        self.provider_ref = provider_ref
        self.error_message = error_message

    def to_dict(self):
        return {
            'status': 'success' if self.is_success else 'failed',
            'provider_ref': self.provider_ref,
        }

class MockPaymentService:
    """
    Mock payment service simulating an external payment processor.
    Clean interface: charge(order, token)
    - tok_success: payment passes, returns mock provider ref (e.g., 'mock_8841')
    - tok_fail / fail: payment fails (simulated card decline / insufficient funds)
    """

    @staticmethod
    def charge(order, token: str) -> MockPaymentResult:
        token_str = str(token).strip()

        if token_str in ('tok_fail', 'fail'):
            return MockPaymentResult(
                is_success=False,
                provider_ref="",
                error_message="Payment failed. No money was taken and your cart is unchanged."
            )

        if token_str in ('tok_success', 'success') or token_str.startswith('tok_'):
            ref = f"mock_{random.randint(1000, 9999)}"
            return MockPaymentResult(
                is_success=True,
                provider_ref=ref,
                error_message=""
            )

        # Default fallback for unknown tokens
        return MockPaymentResult(
            is_success=False,
            provider_ref="",
            error_message="Invalid card token provided. Payment simulation failed."
        )
