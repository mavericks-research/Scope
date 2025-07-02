import stripe
import json # Added for json.loads
from flask import Blueprint, jsonify, current_app, request
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
# @payments_bp.route('/plaid/create_link_token', methods=['POST'])
# @login_required
# def create_plaid_link_token():
#     # ... logic to create and return Plaid link token ...
#     pass

# @payments_bp.route('/plaid/exchange_public_token', methods=['POST'])
# @login_required
# def exchange_plaid_public_token():
#     # ... logic to exchange public token and create Stripe bank account token ...
#     pass

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
