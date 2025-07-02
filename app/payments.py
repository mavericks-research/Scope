import stripe
import json # Added for json.loads
from flask import Blueprint, jsonify, current_app, request, flash, redirect, url_for # Added
from flask_login import login_required, current_user
from .models import Video, UserVideoUnlock, User
from . import db

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/video/<int:video_id>/create-payment-intent', methods=['POST'])
@login_required
def create_payment_intent_for_video(video_id):
    video = Video.query.get_or_404(video_id)

    if not video.is_paid_unlock or video.price is None or video.price <= 0:
        return jsonify({"error": "This video is not available for purchase or price is not set."}), 400

    # Check if user has already unlocked this video
    existing_unlock = UserVideoUnlock.query.filter_by(user_id=current_user.id, video_id=video.id).first()
    if existing_unlock:
        return jsonify({"msg": "Video already unlocked.", "video_id": video.id}), 200 # Or 400 if we consider this an error

    stripe.api_key = current_app.config['STRIPE_API_KEY']

    try:
        # Amount in cents
        amount_cents = int(video.price * 100)

        payment_intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='usd',  # Consider making this configurable if needed
            automatic_payment_methods={'enabled': True},
            metadata={
                'video_id': video.id,
                'user_id': current_user.id,
                'video_title': video.title # For easier tracking in Stripe dashboard
            }
        )
        return jsonify({
            'client_secret': payment_intent.client_secret,
            'video_id': video.id,
            'video_price': float(video.price) # Send price back for frontend display confirmation
        }), 200
    except Exception as e:
        current_app.logger.error(f"Stripe PaymentIntent creation failed for video {video.id}, user {current_user.id}: {str(e)}")
        return jsonify(error=str(e)), 403 # Or 500 for general server error

# Placeholder for Plaid related routes to be added later
import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
import uuid # For mock token generation

# ... (other imports)

# Helper to initialize Plaid client (consider moving to a shared utility if used elsewhere)
def get_plaid_client(app_config):
    configuration = plaid.Configuration(
        host=plaid.Environment.Sandbox if app_config['PLAID_ENV'] == 'sandbox' else
             (plaid.Environment.Development if app_config['PLAID_ENV'] == 'development' else plaid.Environment.Production),
        api_key={
            'clientId': app_config['PLAID_CLIENT_ID'],
            'secret': app_config['PLAID_SECRET_KEY'],
        }
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)

@payments_bp.route('/create-link-token', methods=['POST']) # Changed to POST as it's creating a resource
@login_required
def create_plaid_link_token():
    try:
        plaid_client = get_plaid_client(current_app.config)

        request_body = LinkTokenCreateRequest(
            client_name="Mavericks Stream", # Replace with your app name
            language='en',
            country_codes=[CountryCode(cc) for cc in current_app.config.get('PLAID_COUNTRY_CODES', ['US'])],
            user=LinkTokenCreateRequestUser(
                client_user_id=str(current_user.id) # Must be a string
            ),
            products=[Products(p) for p in current_app.config.get('PLAID_PRODUCTS', ['auth'])],
            # redirect_uri='YOUR_REDIRECT_URI', # Optional: for OAuth flows if not using link_customization_name
            # webhook='YOUR_PLAID_WEBHOOK_URL' # Optional: if you want Plaid webhooks
        )

        # For now, we will mock the Plaid API call to avoid needing real credentials during this setup phase
        # In a real scenario:
        # response = plaid_client.link_token_create(request_body)
        # link_token = response['link_token']

        # Mocked response:
        mock_link_token = f"mock_link_token_sandbox_{current_user.id}_{uuid.uuid4().hex[:8]}"
        current_app.logger.info(f"Mock Plaid Link Token created for user {current_user.id}: {mock_link_token}")

        return jsonify({'link_token': mock_link_token}), 200

    except plaid.ApiException as e:
        current_app.logger.error(f"Plaid API Exception when creating link token: {e.body}")
        return jsonify(error={'status_code': e.status, 'message': str(e.body)}), e.status
    except Exception as e:
        current_app.logger.error(f"Error creating Plaid link token: {str(e)}")
        return jsonify(error=str(e)), 500


@payments_bp.route('/set-payment-method', methods=['POST'])
@login_required
def set_payment_method():
    data = request.get_json()
    public_token = data.get('public_token')
    # metadata = data.get('metadata') # Contains account_id, account name, mask, etc.

    if not public_token:
        return jsonify(error="Missing public_token"), 400

    try:
        # In a real scenario:
        # 1. Initialize Plaid client
        # plaid_client = get_plaid_client(current_app.config)
        # 2. Exchange public_token for an access_token
        # exchange_request = ItemPublicTokenExchangeRequest(public_token=public_token)
        # exchange_response = plaid_client.item_public_token_exchange(exchange_request)
        # access_token = exchange_response['access_token']
        # item_id = exchange_response['item_id'] # Store this if you need to manage the Plaid item later

        # 3. Create a Stripe bank account token using the Plaid access_token and an account_id
        #    (account_id would come from Link onSuccess metadata)
        # account_id = metadata['accounts'][0]['id'] if metadata and metadata.get('accounts') else None
        # if not account_id:
        #     return jsonify(error="Missing account_id from Plaid metadata"), 400
        #
        # processor_token_request = ProcessorStripeBankAccountTokenCreateRequest(
        # access_token=access_token, account_id=account_id
        # )
        # processor_response = plaid_client.processor_stripe_bank_account_token_create(processor_token_request)
        # stripe_bank_account_token = processor_response['stripe_bank_account_token'] # This is the btok_...

        # For now, MOCKING this entire process:
        current_app.logger.info(f"Received Plaid public_token for user {current_user.id}: {public_token}")
        # mock_stripe_source_id = f"btok_test_mock_{uuid.uuid4().hex[:10]}"
        # Using a common Stripe test card source for easier frontend testing with confirmCardPayment
        mock_stripe_source_id = "pm_card_visa" # A test payment method ID for Stripe
        current_app.logger.info(f"Mocking Stripe payment source ID for user {current_user.id}: {mock_stripe_source_id}")

        # Store the mock Stripe source ID on the user
        user = User.query.get(current_user.id)
        if not user:
            return jsonify(error="User not found"), 404 # Should not happen if @login_required works

        user.stripe_payment_source_id = mock_stripe_source_id
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Mock payment method set successfully.",
            "stripe_payment_source_id": mock_stripe_source_id
            # "plaid_item_id": item_id # If storing
        }), 200

    # except plaid.ApiException as e:
    #     current_app.logger.error(f"Plaid API Exception in set_payment_method: {e.body}")
    #     return jsonify(error={'status_code': e.status, 'message': str(e.body)}), e.status
    except Exception as e:
        current_app.logger.error(f"Error in set_payment_method: {str(e)}")
        db.session.rollback() # Rollback in case of db error during user update
        return jsonify(error=str(e)), 500

@payments_bp.route('/payment-complete', methods=['GET'])
@login_required # User should be logged in to see status of their payment
def payment_complete():
    payment_intent_client_secret = request.args.get('payment_intent_client_secret')
    payment_intent_id = request.args.get('payment_intent') # Stripe usually sends 'payment_intent'
    redirect_status = request.args.get('redirect_status')
    video_id = request.args.get('video_id') # Passed in our return_url

    # Prefer payment_intent_id if available, otherwise parse from client_secret if needed
    # Though Stripe usually provides payment_intent_id directly in return_url
    if not payment_intent_id and payment_intent_client_secret:
        payment_intent_id = payment_intent_client_secret.split('_secret_')[0]

    if not payment_intent_id:
        flash("Could not verify payment status: Payment Intent ID missing.", "error")
        return redirect(url_for('frontend.home'))

    try:
        stripe.api_key = current_app.config['STRIPE_API_KEY']
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        if redirect_status == 'succeeded' or payment_intent.status == 'succeeded':
            # The webhook should handle the actual unlock. Here we just confirm to the user.
            flash("Payment successful! Your video should be unlocked.", "success")
            # Check if unlock record exists (it might take a moment for webhook)
            unlock = UserVideoUnlock.query.filter_by(
                user_id=current_user.id,
                video_id=video_id,
                stripe_payment_intent_id=payment_intent.id
            ).first()
            if unlock:
                current_app.logger.info(f"User {current_user.id} successfully paid and confirmed unlock for video {video_id}.")
            else:
                current_app.logger.warning(f"Payment for video {video_id} by user {current_user.id} succeeded (PI: {payment_intent.id}), but unlock record not yet found via webhook. It might be delayed.")
                flash("Your payment is processing and the video will be unlocked shortly.", "info")

        elif redirect_status == 'processing' or payment_intent.status == 'processing':
            flash("Your payment is processing. We'll update you soon.", "info")
        elif redirect_status == 'requires_payment_method' or payment_intent.status == 'requires_payment_method':
            flash("Payment failed. Please try another payment method.", "error")
        else:
            flash(f"Payment status: {payment_intent.status}. Please contact support if issues persist.", "warning")

    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe API error on payment completion: {str(e)}")
        flash(f"Error verifying payment: {str(e)}", "error")
    except Exception as e:
        current_app.logger.error(f"Generic error on payment completion: {str(e)}")
        flash("An unexpected error occurred while verifying your payment.", "error")

    if video_id:
        return redirect(url_for('frontend.home')) # Or redirect to the specific video page if you have one: url_for('videos.view_video', video_id=video_id)
    return redirect(url_for('frontend.home'))


@payments_bp.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = current_app.config['STRIPE_WEBHOOK_SECRET']
    event = None

    try:
        # For testing, you might want to bypass verification IF using a mock secret
        # or if you are directly sending mock events.
        # In a real scenario, this verification is crucial.
        if endpoint_secret == 'whsec_YOUR_MOCK_STRIPE_WEBHOOK_SECRET' or not endpoint_secret:
            current_app.logger.warning("Stripe webhook signature verification bypassed due to mock or missing secret.")
            event = stripe.Event.construct_from(
                json.loads(payload), stripe.api_key
            )
        else:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
    except ValueError as e:
        # Invalid payload
        current_app.logger.error(f"Stripe webhook ValueError: {str(e)}")
        return jsonify(error="Invalid payload"), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        current_app.logger.error(f"Stripe webhook SignatureVerificationError: {str(e)}")
        return jsonify(error="Invalid signature"), 400
    except Exception as e:
        current_app.logger.error(f"Stripe webhook general error: {str(e)}")
        return jsonify(error="Webhook processing error"), 500


    # Handle the event
    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object # contains a stripe.PaymentIntent
        current_app.logger.info(f"PaymentIntent succeeded: {payment_intent.id}")

        metadata = payment_intent.metadata
        video_id = metadata.get('video_id')
        user_id = metadata.get('user_id')

        if not video_id or not user_id:
            current_app.logger.error(f"Missing video_id or user_id in PaymentIntent metadata: {payment_intent.id}")
            return jsonify(error="Missing metadata in PaymentIntent"), 400

        try:
            video_id = int(video_id)
            user_id = int(user_id)
        except ValueError:
            current_app.logger.error(f"Invalid video_id or user_id format in PaymentIntent metadata: {payment_intent.id}")
            return jsonify(error="Invalid metadata format"), 400

        # Check if unlock record already exists to prevent duplicates (e.g., from webhook retries)
        existing_unlock = UserVideoUnlock.query.filter_by(
            user_id=user_id,
            video_id=video_id,
            stripe_payment_intent_id=payment_intent.id # also check PI ID for idempotency
        ).first()

        if not existing_unlock:
            # Check if user and video exist before creating unlock record
            user = User.query.get(user_id)
            video = Video.query.get(video_id)

            if not user:
                current_app.logger.error(f"User not found for ID {user_id} from PaymentIntent {payment_intent.id}")
                return jsonify(error=f"User {user_id} not found"), 404 # Or 400
            if not video:
                current_app.logger.error(f"Video not found for ID {video_id} from PaymentIntent {payment_intent.id}")
                return jsonify(error=f"Video {video_id} not found"), 404 # Or 400

            unlock_record = UserVideoUnlock(
                user_id=user_id,
                video_id=video_id,
                stripe_payment_intent_id=payment_intent.id
            )
            db.session.add(unlock_record)
            try:
                db.session.commit()
                current_app.logger.info(f"UserVideoUnlock record created for user {user_id}, video {video_id}.")
            except Exception as e_commit:
                db.session.rollback()
                current_app.logger.error(f"Failed to commit UserVideoUnlock for user {user_id}, video {video_id}: {str(e_commit)}")
                return jsonify(error="Database error saving unlock"), 500
        else:
            current_app.logger.info(f"Unlock record already exists for user {user_id}, video {video_id}, PI {payment_intent.id}. Webhook handled.")

    elif event.type == 'payment_intent.payment_failed':
        payment_intent = event.data.object
        current_app.logger.warning(f"PaymentIntent failed: {payment_intent.id}. Reason: {payment_intent.last_payment_error.message if payment_intent.last_payment_error else 'Unknown'}")
        # Potentially notify the user or take other actions
    else:
        current_app.logger.info(f"Unhandled Stripe event type: {event.type}")

    return jsonify(received=True), 200
