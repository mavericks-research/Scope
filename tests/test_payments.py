import pytest
import stripe # For accessing stripe.error types if needed, and for type hinting
from unittest.mock import patch, MagicMock
from app.models import Video, User, UserVideoUnlock
from app import db as _db # Using _db to avoid conflict with db fixture name
from decimal import Decimal

@pytest.fixture
def paid_video_setup(auth_data, db): # db here refers to the fixture from conftest
    client, access_token, user_info = auth_data
    user = User.query.get(user_info['id'])

    video_owner = User(username="video_owner_for_payment", email="payment_owner@example.com", password="password")
    _db.session.add(video_owner)
    _db.session.commit()

    paid_video = Video(
        title="Test Paid Video",
        filename="paid.mp4",
        file_path="/fake/paid.mp4",
        user_id=video_owner.id, # Owned by someone else
        is_paid_unlock=True,
        price=Decimal("10.00"),
        is_public=True
    )
    _db.session.add(paid_video)
    _db.session.commit()

    # Log in the user from auth_data for making requests
    client.post('/auth/logout', follow_redirects=True) # Ensure clean session
    login_resp = client.post('/auth/login', data={'identifier': user.username, 'password': 'password123'}, follow_redirects=True)
    assert login_resp.status_code == 200, "Login failed in paid_video_setup"

    return client, user, paid_video, access_token # access_token might not be needed if client session is used


def test_create_payment_intent_success(paid_video_setup):
    client, user, video, _ = paid_video_setup

    with patch('stripe.PaymentIntent.create') as mock_stripe_create:
        mock_stripe_create.return_value = MagicMock(client_secret='pi_123_secret_456')

        response = client.post(f'/payments/video/{video.id}/create-payment-intent')

        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['client_secret'] == 'pi_123_secret_456'
        assert json_data['video_id'] == video.id
        assert json_data['video_price'] == float(video.price)

        mock_stripe_create.assert_called_once_with(
            amount=1000, # 10.00 * 100
            currency='usd',
            automatic_payment_methods={'enabled': True},
            metadata={
                'video_id': video.id,
                'user_id': user.id,
                'video_title': video.title
            }
        )

def test_create_payment_intent_video_not_paid(paid_video_setup):
    client, user, video, _ = paid_video_setup
    video.is_paid_unlock = False
    video.price = None
    _db.session.commit()

    response = client.post(f'/payments/video/{video.id}/create-payment-intent')
    assert response.status_code == 400
    assert "not available for purchase" in response.get_json()['error']

def test_create_payment_intent_video_already_unlocked(paid_video_setup):
    client, user, video, _ = paid_video_setup

    # Create an unlock record
    unlock = UserVideoUnlock(user_id=user.id, video_id=video.id, stripe_payment_intent_id='pi_prev_unlock')
    _db.session.add(unlock)
    _db.session.commit()

    response = client.post(f'/payments/video/{video.id}/create-payment-intent')
    assert response.status_code == 200 # Or 400 depending on desired behavior
    assert "Video already unlocked" in response.get_json()['msg']

def test_create_payment_intent_stripe_api_error(paid_video_setup):
    client, user, video, _ = paid_video_setup

    with patch('stripe.PaymentIntent.create') as mock_stripe_create:
        mock_stripe_create.side_effect = stripe.error.StripeError("Stripe API is down")

        response = client.post(f'/payments/video/{video.id}/create-payment-intent')

        assert response.status_code == 403 # As per current error handling in route
        assert "Stripe API is down" in response.get_json()['error']

def test_create_payment_intent_video_not_found(paid_video_setup):
    client, _, _, _ = paid_video_setup
    non_existent_video_id = 99999
    response = client.post(f'/payments/video/{non_existent_video_id}/create-payment-intent')
    assert response.status_code == 404 # get_or_404 will trigger this

def test_create_payment_intent_unauthenticated(client, db): # Using standard client and db
    # Create a public, paid video by some user
    owner = User(username="owner_temp", email="owner_temp@example.com", password="password")
    db.session.add(owner)
    db.session.commit()
    paid_video = Video(title="Public Paid Video", user_id=owner.id, filename="public_paid.mp4", file_path="/fake/public_paid.mp4", is_public=True, is_paid_unlock=True, price=Decimal("5.00"))
    db.session.add(paid_video)
    db.session.commit()

    client.get('/auth/logout', follow_redirects=True) # Ensure logged out
    response = client.post(f'/payments/video/{paid_video.id}/create-payment-intent', follow_redirects=False)
    assert response.status_code == 302 # Redirect to login
    assert '/auth/login' in response.headers['Location']

# Tests for Stripe Webhook will be added next
# Need to mock incoming request data and headers for webhook tests.
# Also need to consider how to trigger db operations within webhook without http client.
# (e.g. by directly calling the webhook handler function with mock request context)

def test_stripe_webhook_payment_intent_succeeded(client, db, app):
    # Setup: Create a user and a video that can be "paid" for
    user = User(username="webhook_user", email="webhook@example.com", password="password")
    db.session.add(user)
    db.session.commit() # Commit user to get user.id

    video = Video(title="Webhook Test Video", filename="wh_test.mp4", file_path="/fake/wh.mp4",
                  user_id=user.id, is_paid_unlock=True, price=Decimal("12.34"))
    db.session.add(video)
    db.session.commit() # Commit video

    # Mock Stripe event payload for payment_intent.succeeded
    mock_payment_intent_id = "pi_mock_webhook_123"
    mock_event_payload = {
        "id": "evt_mock_event_123",
        "object": "event",
        "api_version": "2020-08-27", # Use a relevant API version
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": mock_payment_intent_id,
                "object": "payment_intent",
                "amount": 1234,
                "currency": "usd",
                "status": "succeeded",
                "metadata": {
                    "video_id": str(video.id),
                    "user_id": str(user.id)
                }
                # Add other necessary fields if your logic depends on them
            }
        }
    }

    # Mock current_app.config for the webhook secret for this test
    # This bypasses actual signature verification if it's the mock secret
    with patch.dict(app.config, {"STRIPE_WEBHOOK_SECRET": "whsec_YOUR_MOCK_STRIPE_WEBHOOK_SECRET"}):
        response = client.post('/payments/stripe-webhook',
                               data=json.dumps(mock_event_payload),
                               content_type='application/json',
                               headers={'Stripe-Signature': 'dummy_sig_for_mock_bypass'}) # Signature not verified with mock secret

    assert response.status_code == 200
    assert response.get_json()['received'] is True

    # Verify UserVideoUnlock record was created
    unlock_record = UserVideoUnlock.query.filter_by(
        user_id=user.id,
        video_id=video.id,
        stripe_payment_intent_id=mock_payment_intent_id
    ).first()
    assert unlock_record is not None
    assert unlock_record.user_id == user.id
    assert unlock_record.video_id == video.id

def test_stripe_webhook_missing_metadata(client, db, app):
    mock_event_payload_no_meta = {
        "id": "evt_mock_no_meta", "object": "event", "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_no_meta", "object": "payment_intent", "metadata": {}}}
    }
    with patch.dict(app.config, {"STRIPE_WEBHOOK_SECRET": "whsec_YOUR_MOCK_STRIPE_WEBHOOK_SECRET"}):
        response = client.post('/payments/stripe-webhook', data=json.dumps(mock_event_payload_no_meta), content_type='application/json')
    assert response.status_code == 400
    assert "Missing metadata" in response.get_json()['error']

def test_stripe_webhook_invalid_signature(client, db, app):
    # Use a non-mock secret to force signature verification
    with patch.dict(app.config, {"STRIPE_WEBHOOK_SECRET": "whsec_real_secret_for_test"}):
        response = client.post('/payments/stripe-webhook',
                               data='{"id": "evt_bad_sig", "type": "payment_intent.succeeded"}',
                               content_type='application/json',
                               headers={'Stripe-Signature': 't=123,v1=bad_signature_value'})
    assert response.status_code == 400 # stripe.error.SignatureVerificationError
    assert "Invalid signature" in response.get_json()['error']

# Need to import json for the webhook tests
import json


# --- Tests for Plaid Link Token and Payment Method Setting ---

@pytest.fixture
def logged_in_client(client, auth_data):
    """Provides a client that is logged in via Flask-Login session."""
    _, _, user_info = auth_data # User 'testuser', pass 'password123'
    # Perform a form login to establish session
    logout_resp = client.get('/auth/logout', follow_redirects=True) # Clean previous session
    assert logout_resp.status_code == 200
    login_resp = client.post('/auth/login', data={
        'identifier': user_info['username'],
        'password': 'password123'
    }, follow_redirects=True)
    assert login_resp.status_code == 200 # Should be on /upload page
    return client, user_info # Return client and user_info for convenience

def test_create_link_token_success(logged_in_client, app):
    client, _ = logged_in_client
    # Plaid client is mocked in the route for now, so no need to patch plaid.api here yet
    # unless we want to test specific Plaid client call parameters.

    response = client.post('/payments/create-link-token')
    assert response.status_code == 200
    json_data = response.get_json()
    assert 'link_token' in json_data
    assert 'mock_link_token_sandbox' in json_data['link_token']

def test_create_link_token_unauthenticated(client):
    response = client.post('/payments/create-link-token', follow_redirects=False)
    assert response.status_code == 302 # Redirect to login
    assert '/auth/login' in response.headers['Location']

def test_set_payment_method_success(logged_in_client, db, app):
    client, user_info = logged_in_client
    user_id = user_info['id']

    # Plaid client and token exchange are mocked in the route for now.
    mock_public_token = "public-sandbox-token-123"

    response = client.post('/payments/set-payment-method', json={
        'public_token': mock_public_token,
        'metadata': {'accounts': [{'id': 'mock_account_id'}]} # Some mock metadata
    })

    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['status'] == 'success'
    assert json_data['stripe_payment_source_id'] == "pm_card_visa" # The mocked ID

    # Verify user model was updated
    user = User.query.get(user_id)
    assert user.stripe_payment_source_id == "pm_card_visa"

def test_set_payment_method_missing_public_token(logged_in_client):
    client, _ = logged_in_client
    response = client.post('/payments/set-payment-method', json={}) # Missing public_token
    assert response.status_code == 400
    assert "Missing public_token" in response.get_json()['error']

def test_set_payment_method_unauthenticated(client):
    response = client.post('/payments/set-payment-method', json={'public_token': 'some-token'}, follow_redirects=False)
    assert response.status_code == 302 # Redirect to login
    assert '/auth/login' in response.headers['Location']


# --- Tests for Payment Completion Route ---

def test_payment_complete_success(logged_in_client, app, db):
    client, user_info = logged_in_client
    user_id = user_info['id']

    # Create a dummy video for context, though not strictly needed for this PI retrieve mock
    video = Video(title="Payment Complete Test Video", user_id=user_id, filename="pctv.mp4", file_path="/f/pctv.mp4", is_public=True)
    db.session.add(video)
    db.session.commit()

    mock_pi_id = "pi_mock_succeeded_123"
    mock_client_secret = f"{mock_pi_id}_secret_abcdef"

    with patch('stripe.PaymentIntent.retrieve') as mock_retrieve:
        mock_retrieve.return_value = MagicMock(
            id=mock_pi_id,
            status='succeeded',
            client_secret=mock_client_secret
            # metadata would typically be here if needed by the route, but not directly used in this success flash
        )

        # Simulate redirect from Stripe with parameters
        response = client.get(f'/payments/payment-complete?payment_intent={mock_pi_id}&payment_intent_client_secret={mock_client_secret}&redirect_status=succeeded&video_id={video.id}', follow_redirects=False)

    assert response.status_code == 302 # Redirects to home
    assert response.headers['Location'] == '/' # frontend.home

    # To check flashed messages, we'd need to follow the redirect and inspect the response content
    # Or use a custom way to capture flashes if that's set up in conftest.
    # For now, we'll assume the flash happens if the redirect is correct.
    # A more thorough test would capture and verify flash messages.
    # Example (if response was not a redirect but rendered a template with flashes):
    # client.get('/some_page_that_shows_flashes')
    # assert b"Payment successful!" in followed_response.data
    # This is harder to test directly with redirects without more setup.

def test_payment_complete_processing(logged_in_client, app, db):
    client, user_info = logged_in_client # Correct unpacking
    video = Video(title="Processing Test Video", user_id=user_info['id'], filename="ptv.mp4", file_path="/f/ptv.mp4", is_public=True)
    db.session.add(video)
    db.session.commit()
    mock_pi_id = "pi_mock_processing_456"
    with patch('stripe.PaymentIntent.retrieve') as mock_retrieve:
        mock_retrieve.return_value = MagicMock(status='processing')
        response = client.get(f'/payments/payment-complete?payment_intent={mock_pi_id}&video_id={video.id}', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'] == '/'
    # Check flash for "processing" - similar challenge as above

def test_payment_complete_failed(logged_in_client, app, db):
    client, user_info = logged_in_client # Correct unpacking
    video = Video(title="Failed Test Video", user_id=user_info['id'], filename="ftv.mp4", file_path="/f/ftv.mp4", is_public=True)
    db.session.add(video)
    db.session.commit()
    mock_pi_id = "pi_mock_failed_789"
    with patch('stripe.PaymentIntent.retrieve') as mock_retrieve:
        mock_retrieve.return_value = MagicMock(status='requires_payment_method')
        response = client.get(f'/payments/payment-complete?payment_intent={mock_pi_id}&video_id={video.id}', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'] == '/'
    # Check flash for "failed"

def test_payment_complete_missing_pi_id(logged_in_client):
    client, _ = logged_in_client # Correct unpacking, user_info not needed here
    response = client.get('/payments/payment-complete', follow_redirects=False) # No PI ID
    assert response.status_code == 302 # Redirects home
    assert response.headers['Location'] == '/'
    # Check for "Payment Intent ID missing" flash

def test_payment_complete_stripe_error(logged_in_client, app):
    client, _ = logged_in_client # Correct unpacking, user_info not needed here
    with patch('stripe.PaymentIntent.retrieve') as mock_retrieve:
        mock_retrieve.side_effect = stripe.error.StripeError("Stripe is down")
        response = client.get('/payments/payment-complete?payment_intent=pi_anyid', follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'] == '/'
    # Check for "Error verifying payment" flash
