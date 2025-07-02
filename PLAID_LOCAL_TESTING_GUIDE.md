# Guide to Testing Plaid Locally (Development Environment)

This guide outlines the steps to change the application from using a mocked Plaid setup to testing against Plaid's live Development environment.

## Prerequisites

1.  **Plaid Developer Account:**
    *   Sign up at [Plaid.com](https://plaid.com/) if you haven't already.
    *   Access your Dashboard to find your API keys for the "Development" environment.
2.  **Stripe Test Account:**
    *   You'll need Stripe test API keys if you intend to fully test the Plaid token exchange into a Stripe payment method.

## Configuration Changes

1.  **Environment Variables (.env file):**
    Update your local `.env` file with your Plaid Development credentials and ensure Stripe keys are test keys:

    ```env
    # ... other existing variables ...

    # Plaid Configuration
    PLAID_CLIENT_ID=your_plaid_dev_client_id
    PLAID_SECRET_KEY=your_plaid_dev_secret
    PLAID_ENV=development # Change from 'sandbox' or other mock value
    # PLAID_PRODUCTS and PLAID_COUNTRY_CODES can usually remain as they are, e.g.:
    # PLAID_PRODUCTS=auth,transactions
    # PLAID_COUNTRY_CODES=US

    # Stripe Configuration (ensure these are your TEST keys)
    STRIPE_API_KEY=sk_test_YOUR_STRIPE_TEST_SECRET_KEY
    STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_STRIPE_TEST_PUBLISHABLE_KEY
    STRIPE_WEBHOOK_SECRET=whsec_YOUR_STRIPE_TEST_WEBHOOK_SECRET # Use your local test webhook secret if verifying locally
    ```
    *   The application (`app/__init__.py`) is designed to pick these up.

## Code Modifications (Un-mocking)

You'll need to modify `app/payments.py` to make real API calls instead of returning mocked data.

1.  **Endpoint: `/payments/create-link-token`**
    *   Locate the `create_plaid_link_token` function.
    *   **Comment out** the mock token generation:
        ```python
        # Mocked response:
        # mock_link_token = f"mock_link_token_sandbox_{current_user.id}_{uuid.uuid4().hex[:8]}"
        # current_app.logger.info(f"Mock Plaid Link Token created for user {current_user.id}: {mock_link_token}")
        # return jsonify({'link_token': mock_link_token}), 200
        ```
    *   **Uncomment and use** the actual Plaid API call:
        ```python
        # In a real scenario:
        response = plaid_client.link_token_create(request_body)
        link_token = response['link_token']
        current_app.logger.info(f"Plaid Link Token created for user {current_user.id}")
        return jsonify({'link_token': link_token}), 200
        ```

2.  **Endpoint: `/payments/set-payment-method`**
    *   Locate the `set_payment_method` function.
    *   **Comment out** the mock Stripe source ID generation:
        ```python
        # current_app.logger.info(f"Received Plaid public_token for user {current_user.id}: {public_token}")
        # mock_stripe_source_id = "pm_card_visa"
        # current_app.logger.info(f"Mocking Stripe payment source ID for user {current_user.id}: {mock_stripe_source_id}")
        # user.stripe_payment_source_id = mock_stripe_source_id
        ```
    *   **Uncomment and use** the actual Plaid API calls to exchange the `public_token` and create a Stripe bank account token. You'll also need to import necessary Plaid models.

        ```python
        # At the top of app/payments.py, ensure these (or similar) are imported:
        # from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
        # from plaid.model.processor_stripe_bank_account_token_create_request import ProcessorStripeBankAccountTokenCreateRequest

        # Inside the try block of set_payment_method:
        plaid_client = get_plaid_client(current_app.config)

        # 1. Exchange public_token for an access_token
        exchange_request = plaid.model.item_public_token_exchange_request.ItemPublicTokenExchangeRequest(public_token=public_token)
        exchange_response = plaid_client.item_public_token_exchange(exchange_request)
        access_token = exchange_response['access_token']
        item_id = exchange_response['item_id'] # Optional: Store this if you need to manage the Plaid item

        # 2. Create a Stripe bank account token
        # Get account_id from metadata sent by frontend (from Plaid Link's onSuccess)
        account_id_from_frontend = data.get('metadata', {}).get('account_id')
        if not account_id_from_frontend:
            current_app.logger.error("Missing account_id in metadata from Plaid Link onSuccess callback.")
            return jsonify(error="Missing account_id from Plaid metadata"), 400

        processor_token_request = plaid.model.processor_stripe_bank_account_token_create_request.ProcessorStripeBankAccountTokenCreateRequest(
            access_token=access_token,
            account_id=account_id_from_frontend
        )
        processor_response = plaid_client.processor_stripe_bank_account_token_create(processor_token_request)
        stripe_bank_account_token = processor_response['stripe_bank_account_token'] # This is the btok_...

        current_app.logger.info(f"Successfully obtained Stripe bank account token for user {current_user.id}: {stripe_bank_account_token}")

        # Store the real Stripe bank account token
        user = User.query.get(current_user.id)
        if not user:
            return jsonify(error="User not found"), 404

        user.stripe_payment_source_id = stripe_bank_account_token # Store the btok_
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Payment method successfully linked via Plaid and Stripe.",
            "stripe_payment_source_id": stripe_bank_account_token,
            "plaid_item_id": item_id
        }), 200
        ```

## Frontend JavaScript (`app/static/script.js`)

1.  **Ensure `account_id` is sent from Plaid Link `onSuccess`:**
    *   In the `sendPlaidPublicToken` function (called by Plaid Link's `onSuccess`), make sure the `metadata` object you send to your `/payments/set-payment-method` backend includes the `account_id`.
    *   The `metadata` object from Plaid Link's `onSuccess` has an `accounts` array. Each account object in this array has an `id` field. You typically use the first account's ID.

    ```javascript
    // Inside sendPlaidPublicToken function, when constructing the body for fetch:
    body: JSON.stringify({
        public_token: publicToken,
        metadata: {
            institution_name: metadata.institution ? metadata.institution.name : null,
            account_name: metadata.accounts && metadata.accounts.length > 0 ? metadata.accounts[0].name : null,
            account_mask: metadata.accounts && metadata.accounts.length > 0 ? metadata.accounts[0].mask : null,
            account_id: metadata.accounts && metadata.accounts.length > 0 ? metadata.accounts[0].id : null // Crucial for creating Stripe token
        }
    })
    ```

## Stripe Integration Notes (Beyond Plaid)

*   **Using the `btok_` token:** The `stripe_bank_account_token` (e.g., `btok_...`) obtained from Plaid is a short-lived token. You need to use it immediately with Stripe to:
    1.  Create a Stripe Customer (if one doesn't exist for your user).
    2.  Attach the bank account as a PaymentMethod to that Customer. This will give you a persistent PaymentMethod ID (e.g., `pm_...`).
    3.  Store this persistent `pm_...` ID (or the Customer ID if you intend to charge their default source) as the `user.stripe_payment_source_id` instead of the temporary `btok_...`.
*   The current `create-payment-intent` endpoint might need to be updated to use a saved PaymentMethod ID associated with a Stripe Customer when creating the Payment Intent.

## Testing with Plaid Development Environment

*   Use Plaid's provided test credentials for the Link flow (e.g., `user_good`, `pass_good` for various institutions available in Development). You can find these in your Plaid Dashboard.
*   You will be making live API calls to Plaid's Development servers.
*   Check the Plaid Dashboard for logs of your API requests and Link events.
*   If you have OAuth redirect URIs for specific bank integrations, ensure they are configured in your Plaid application settings.

By following these steps, you can transition from a fully mocked Plaid interaction to testing against Plaid's actual Development environment. Remember to handle potential API errors gracefully.
