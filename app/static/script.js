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
});
