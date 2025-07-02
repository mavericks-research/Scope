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

    // Handler for "Unlock Video" buttons
    const unlockVideoButtons = document.querySelectorAll('.unlock-button');
    unlockVideoButtons.forEach(button => {
        button.addEventListener('click', async (event) => {
            const videoId = event.target.dataset.videoId;
            const videoPrice = event.target.dataset.price; // For display or confirmation

            // Create a status div next to the button or in a predefined place
            let statusDiv = document.getElementById(`unlock-status-${videoId}`);
            if (!statusDiv) {
                statusDiv = document.createElement('div');
                statusDiv.id = `unlock-status-${videoId}`;
                statusDiv.style.marginTop = '10px';
                event.target.parentNode.appendChild(statusDiv);
            }
            statusDiv.className = 'message';
            statusDiv.textContent = 'Processing unlock...';

            // Check if user is authenticated (Flask-Login adds current_user to global context, but JS can't see that directly)
            // We rely on MAVERICKSTREAM_USER_HAS_PAYMENT_SOURCE which implies authentication for true.
            if (typeof MAVERICKSTREAM_USER_HAS_PAYMENT_SOURCE === 'undefined') {
                 statusDiv.textContent = 'Login required to unlock videos. Please log in.';
                 statusDiv.className = 'message error';
                 // Optionally redirect to login: window.location.href = '/auth/login';
                 return;
            }

            if (!MAVERICKSTREAM_USER_HAS_PAYMENT_SOURCE) {
                statusDiv.textContent = 'No payment method found. Please add a bank account in your profile.';
                statusDiv.className = 'message error';
                // Optionally link to profile: event.target.insertAdjacentHTML('afterend', '<p><a href="/profile">Add Payment Method</a></p>');
                return;
            }

            try {
                // 1. Create Payment Intent
                const piResponse = await fetch(`/payments/video/${videoId}/create-payment-intent`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (!piResponse.ok) {
                    const errorResult = await piResponse.json();
                    throw new Error(errorResult.error || `Failed to create payment intent: ${piResponse.statusText}`);
                }
                const piResult = await piResponse.json();
                const clientSecret = piResult.client_secret;

                if (!clientSecret) {
                    throw new Error('Client secret not received for payment intent.');
                }
                statusDiv.textContent = 'Payment intent created. Confirming payment... (Mocked)';

                // 2. Mock Stripe Payment Confirmation (actual Stripe.js would be here)
                // For now, we'll just simulate a successful confirmation.
                // In a real app, you would use stripe.confirmCardPayment or similar.
                // The actual unlock happens via webhook after Stripe processes the payment.

                // Simulate a delay and success for mock
                await new Promise(resolve => setTimeout(resolve, 1500));

                statusDiv.textContent = `Mock payment confirmed for video ${videoId} (Price: $${videoPrice}). Video will be unlocked shortly after server processing. Please refresh if needed.`;
                statusDiv.className = 'message success';
                // Hide the button after successful "mock" attempt to prevent re-clicks before webhook potentially updates UI
                event.target.style.display = 'none';

            } catch (error) {
                console.error(`Error unlocking video ${videoId}:`, error);
                statusDiv.textContent = `Error: ${error.message}`;
                statusDiv.className = 'message error';
            }
        });
    });
});
