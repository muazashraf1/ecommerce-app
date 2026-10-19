from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework import status

class PaymentFailedException(APIException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Payment failed. No money was taken and your cart is unchanged.'
    default_code = 'payment_failed'

class StockUnavailableException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Not enough stock available for this product.'
    default_code = 'stock_unavailable'

class InvalidStatusTransitionException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Invalid order status transition.'
    default_code = 'invalid_status_transition'

class DuplicateConflictException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Conflict occurred. Duplicate operation detected.'
    default_code = 'duplicate_conflict'

def custom_exception_handler(exc, context):
    """
    Custom exception handler to return consistent format:
    {"detail": "Error message"}
    """
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(response.data, dict):
            # If standard detail is already present, keep it
            if 'detail' not in response.data:
                # If it's a dict with field errors, extract first error or join them into 'detail'
                errors = []
                for field, val in response.data.items():
                    if isinstance(val, list):
                        msg = " ".join([str(v) for v in val])
                    else:
                        msg = str(val)
                    errors.append(f"{field}: {msg}")
                response.data = {'detail': "; ".join(errors)}
        elif isinstance(response.data, list):
            response.data = {'detail': " ".join([str(v) for v in response.data])}

    return response
