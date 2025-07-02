console.log("Mavericks Stream frontend script loaded!");

document.addEventListener('DOMContentLoaded', () => {
    const videoForm = document.querySelector('form[action*="upload_video"]');
    const messageDiv = document.createElement('div'); // For displaying messages
    if (videoForm) {
        videoForm.parentNode.insertBefore(messageDiv, videoForm.nextSibling); // Insert messageDiv after the form

        videoForm.addEventListener('submit', async (event) => {
            event.preventDefault(); // Prevent default form submission
            messageDiv.textContent = ''; // Clear previous messages
            messageDiv.className = ''; // Clear previous classes

            const token = localStorage.getItem('access_token');
            if (!token || token === "null" || token.trim() === "") {
                messageDiv.textContent = 'Error: You are not logged in or your session is invalid. Please log out and log in again to upload videos.';
                messageDiv.className = 'message error';
                // Optionally, re-enable submit button if you want them to try again after e.g. manual login in another tab
                // submitButton.disabled = false;
                // submitButton.textContent = 'Upload';
                return; // Stop the submission
            }

            const formData = new FormData(videoForm);
            // Ensure 'is_public' is included; FormData only includes checked checkboxes by default
            const isPublicCheckbox = videoForm.querySelector('input[name="is_public"]');
            if (isPublicCheckbox) {
                formData.set('is_public', isPublicCheckbox.checked ? 'true' : 'false');
            }

            // Handle paid unlock fields
            const isPaidUnlockCheckbox = videoForm.querySelector('input[name="is_paid_unlock"]');
            const priceInput = videoForm.querySelector('input[name="price"]');

            if (isPaidUnlockCheckbox) {
                formData.set('is_paid_unlock', isPaidUnlockCheckbox.checked ? 'true' : 'false');
                if (isPaidUnlockCheckbox.checked && priceInput && priceInput.value) {
                    formData.set('price', priceInput.value);
                } else if (isPaidUnlockCheckbox.checked && (!priceInput || !priceInput.value)) {
                    // This case should ideally be caught by form validation or server-side
                    // but good to be aware of on client too.
                    console.warn("Video marked as paid but no price is set.");
                    // Optionally, prevent submission or show an error here.
                } else {
                    // If not paid, ensure price is not sent or is empty
                    if (formData.has('price')) {
                        formData.delete('price');
                    }
                }
            }


            const submitButton = videoForm.querySelector('button[type="submit"]');
            submitButton.disabled = true;
            submitButton.textContent = 'Uploading...';

            try {
                const response = await fetch(videoForm.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'Authorization': `Bearer ${token}` // Use the retrieved token
                    }
                });

                const result = await response.json();

                if (response.ok) {
                    messageDiv.textContent = `Success: ${result.msg || 'Video uploaded successfully!'}. Video ID: ${result.video_id}`;
                    messageDiv.className = 'message success';
                    videoForm.reset(); // Clear the form
                } else {
                    messageDiv.textContent = `Error: ${result.msg || 'Failed to upload video.'} ${result.error ? result.error : ''}`;
                    messageDiv.className = 'message error';
                }
            } catch (error) {
                console.error('Upload error:', error);
                messageDiv.textContent = `Network error: ${error.message || 'Could not connect to server.'}`;
                messageDiv.className = 'message error';
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = 'Upload';
            }
        });
    }

    // Example: You can add JavaScript to interact with your page here
    const heading = document.querySelector('h1');
    if (heading) {
        heading.addEventListener('click', () => {
            // alert('You clicked the heading!'); // Replaced with less intrusive console log
            console.log('Heading clicked');
        });
    }

    // Plaid Link Button Handler
    const addBankAccountButton = document.getElementById('add-bank-account-button');
    if (addBankAccountButton) {
        addBankAccountButton.addEventListener('click', async (event) => {
            console.log('Add bank account button clicked. Plaid Link to be initialized here.');
            const plaidStatusDiv = document.getElementById('plaid-status');
            if (plaidStatusDiv) {
                plaidStatusDiv.textContent = 'Initiating Plaid Link...';
                plaidStatusDiv.className = 'message'; // Neutral message
            }

            try {
                // 1. Fetch link_token from backend
                const response = await fetch('/payments/create-link-token', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        // Add Authorization header if your endpoint is protected by JWT for this specific call
                        // For Flask-Login session-based protection, this isn't needed if cookies are sent.
                        // Assuming session cookie handles auth for this @login_required endpoint.
                    }
                });

                if (!response.ok) {
                    const errorResult = await response.json();
                    throw new Error(errorResult.error || `Failed to fetch link token: ${response.statusText}`);
                }

                const result = await response.json();
                const linkToken = result.link_token;

                if (!linkToken) {
                    throw new Error('Link token not received from server.');
                }

                if (plaidStatusDiv) plaidStatusDiv.textContent = 'Link token received. Initializing Plaid...';

                // 2. Initialize Plaid Link with token
                const handler = Plaid.create({
                    token: linkToken,
                    onSuccess: (public_token, metadata) => {
                        console.log('Plaid Link onSuccess: public_token=', public_token, 'metadata=', metadata);
                        if (plaidStatusDiv) {
                            plaidStatusDiv.textContent = `Success! Account connected: ${metadata.institution.name} - ${metadata.accounts[0].name} (${metadata.accounts[0].mask})`;
                            plaidStatusDiv.className = 'message success';
                        }
                        // 3. Send public_token and metadata to backend
                        sendPlaidPublicToken(public_token, metadata, plaidStatusDiv);
                    },
                    onLoad: () => {
                        console.log('Plaid Link loaded');
                        if (plaidStatusDiv) plaidStatusDiv.textContent = 'Plaid Link UI loaded.';
                    },
                    onExit: (err, metadata) => {
                        console.error('Plaid Link exited:', err, metadata);
                        if (plaidStatusDiv) {
                            let exitMsg = 'Plaid Link exited.';
                            if (err) exitMsg += ` Error: ${err.error_message || err.display_message || err.error_code}`;
                            if (metadata.status) exitMsg += ` Status: ${metadata.status}`;
                            plaidStatusDiv.textContent = exitMsg;
                            plaidStatusDiv.className = 'message error';
                        }
                    },
                    onEvent: (eventName, metadata) => {
                        console.log('Plaid Link event:', eventName, metadata);
                        // Optionally update plaidStatusDiv for certain events
                    }
                });

                // 4. Open Plaid Link
                handler.open();

            } catch (error) {
                console.error('Error in Plaid Link flow:', error);
                if (plaidStatusDiv) {
                    plaidStatusDiv.textContent = `Error: ${error.message}`;
                    plaidStatusDiv.className = 'message error';
                }
            }
        });
    }
});

async function sendPlaidPublicToken(publicToken, metadata, statusDiv) {
    try {
        if (statusDiv) {
            statusDiv.textContent = 'Processing payment method...';
            statusDiv.className = 'message';
        }

        const response = await fetch('/payments/set-payment-method', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                public_token: publicToken,
                metadata: { // Send some useful metadata, like account name/mask for display confirmation
                    institution_name: metadata.institution ? metadata.institution.name : null,
                    account_name: metadata.accounts && metadata.accounts.length > 0 ? metadata.accounts[0].name : null,
                    account_mask: metadata.accounts && metadata.accounts.length > 0 ? metadata.accounts[0].mask : null,
                    // account_id: metadata.accounts && metadata.accounts.length > 0 ? metadata.accounts[0].id : null, // For backend processing
                }
            })
        });

        if (!response.ok) {
            const errorResult = await response.json();
            throw new Error(errorResult.error || `Failed to set payment method: ${response.statusText}`);
        }

        const result = await response.json();
        if (statusDiv) {
            statusDiv.textContent = result.message || 'Payment method successfully set!';
            statusDiv.className = 'message success'; // Corrected variable name
        }
        console.log('Set payment method result:', result);
        // Potentially update UI to show the new payment method or a success indicator permanently

    } catch (error) {
        console.error('Error setting payment method:', error);
        if (statusDiv) {
            statusDiv.textContent = `Error setting payment method: ${error.message}`;
            statusDiv.className = 'message error';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // ... (existing listeners like videoForm, Plaid addBankAccountButton)

    // Stripe related variables (assuming STRIPE_PUBLISHABLE_KEY is available globally or via config)
    // This should be set from the server, e.g. in a script tag in the template.
    // For now, hardcoding a placeholder. Replace with actual loading from config.
    let stripe;
    try {
        // Try to get key from a global var set by template if available
        // This is a placeholder; in a real app, pass this from server-side config securely.
        const stripePublishableKey = typeof MAVERICKSTREAM_STRIPE_PUBLISHABLE_KEY !== 'undefined' ? MAVERICKSTREAM_STRIPE_PUBLISHABLE_KEY : "pk_test_YOUR_STRIPE_PUBLISHABLE_KEY_PLACEHOLDER";
        if (stripePublishableKey && stripePublishableKey.startsWith("pk_test_")) {
            stripe = Stripe(stripePublishableKey);
        } else {
            console.warn("Stripe publishable key not found or invalid. Payment Element will not initialize.");
        }
    } catch (e) {
        console.error("Failed to initialize Stripe:", e);
    }


    // Handler for "Unlock Video" buttons
    const unlockVideoButtons = document.querySelectorAll('.unlock-button');
    unlockVideoButtons.forEach(button => {
        button.addEventListener('click', async (event) => {
            event.preventDefault();
            const videoId = event.target.dataset.videoId;
            const videoPrice = event.target.dataset.price;

            const paymentElementContainer = document.getElementById(`payment-element-container-${videoId}`);
            const submitPaymentButton = document.getElementById(`submit-payment-button-${videoId}`);
            const paymentMessageDiv = document.getElementById(`payment-message-${videoId}`);

            if (!paymentElementContainer || !submitPaymentButton || !paymentMessageDiv) {
                console.error("Payment UI elements not found for video:", videoId);
                return;
            }

            paymentMessageDiv.textContent = ''; // Clear previous messages
            paymentMessageDiv.className = 'payment-message';


            // Check if user is authenticated and has a payment source (from global JS vars set by template)
            if (typeof MAVERICKSTREAM_USER_HAS_PAYMENT_SOURCE === 'undefined') {
                 paymentMessageDiv.textContent = 'Please log in to unlock videos.';
                 paymentMessageDiv.className = 'payment-message error';
                 // Consider redirect: window.location.href = '/auth/login?next=' + window.location.pathname;
                 return;
            }
            // Note: The Plaid flow sets up a source. For direct card/wallet payments via Payment Element,
            // this specific check might be less relevant if Payment Element handles new card entry.
            // However, if we want to enforce adding via Plaid first, it's useful.
            // For now, let's assume Payment Element will handle it.

            if (!stripe) {
                paymentMessageDiv.textContent = 'Payment system is currently unavailable. Stripe key missing.';
                paymentMessageDiv.className = 'payment-message error';
                return;
            }

            try {
                paymentMessageDiv.textContent = 'Initializing payment...';
                // 1. Create Payment Intent
                const piResponse = await fetch(`/payments/video/${videoId}/create-payment-intent`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (!piResponse.ok) {
                    const errorResult = await piResponse.json();
                    throw new Error(errorResult.error || `Payment setup failed: ${piResponse.statusText}`);
                }
                const piResult = await piResponse.json();
                const clientSecret = piResult.client_secret;

                if (!clientSecret) {
                    throw new Error('Failed to initialize payment (no client secret).');
                }

                // 2. Initialize Stripe Elements and mount Payment Element
                const appearance = { theme: 'stripe' /* or 'night', 'flat', etc. */ };
                const elements = stripe.elements({ appearance, clientSecret });
                const paymentElement = elements.create('payment');
                paymentElement.mount(`#payment-element-container-${videoId}`);

                paymentElementContainer.style.display = 'block';
                submitPaymentButton.style.display = 'block';
                event.target.style.display = 'none'; // Hide the original "Unlock for $X.XX" button
                paymentMessageDiv.textContent = ''; // Clear "Initializing" message

                // 3. Handle "Pay Now" button click
                submitPaymentButton.onclick = async () => { // Use onclick to replace previous if any
                    paymentMessageDiv.textContent = 'Processing payment...';
                    submitPaymentButton.disabled = true;

                    const { error } = await stripe.confirmPayment({
                        elements,
                        confirmParams: {
                            // Make sure to change this to your payment completion page
                            return_url: `${window.location.origin}/payments/payment-complete?video_id=${videoId}&payment_intent_client_secret=${clientSecret}`,
                        },
                    });

                    // This point will only be reached if there is an immediate error when
                    // confirming the payment. Otherwise, your customer will be redirected to
                    // your `return_url`. For example, some payment methods require a redirect.
                    if (error) {
                        if (error.type === "card_error" || error.type === "validation_error") {
                            paymentMessageDiv.textContent = error.message;
                        } else {
                            paymentMessageDiv.textContent = "An unexpected error occurred.";
                        }
                        paymentMessageDiv.className = 'payment-message error';
                        submitPaymentButton.disabled = false;
                    } else {
                        // Should not be reached if return_url is effective
                        paymentMessageDiv.textContent = "Payment submitted. Waiting for confirmation...";
                        paymentMessageDiv.className = 'payment-message success';
                    }
                };

            } catch (error) {
                console.error(`Error initializing payment for video ${videoId}:`, error);
                paymentMessageDiv.textContent = `Error: ${error.message}`;
                paymentMessageDiv.className = 'payment-message error';
                if (submitPaymentButton) submitPaymentButton.style.display = 'none';
                if (paymentElementContainer) paymentElementContainer.style.display = 'none';
                event.target.style.display = 'block'; // Show original unlock button again
            }
        });
    });
});
