// Main JavaScript for Webtoon Site

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Bookmark toggle functionality
    const bookmarkButtons = document.querySelectorAll('.bookmark-toggle');
    bookmarkButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const webtoonId = this.dataset.webtoonId;
            const icon = this.querySelector('i');
            
            fetch(`/api/bookmark/${webtoonId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.is_bookmarked) {
                    icon.classList.remove('far');
                    icon.classList.add('fas');
                    this.setAttribute('title', 'Yer İşaretlerinden Kaldır');
                    this.setAttribute('data-bs-original-title', 'Yer İşaretlerinden Kaldır');
                } else {
                    icon.classList.remove('fas');
                    icon.classList.add('far');
                    this.setAttribute('title', 'Yer İşaretlerine Ekle');
                    this.setAttribute('data-bs-original-title', 'Yer İşaretlerine Ekle');
                }
                
                // Update tooltip
                var tooltip = bootstrap.Tooltip.getInstance(this);
                if (tooltip) {
                    tooltip.hide();
                    tooltip.update();
                }
            })
            .catch(error => console.error('Error:', error));
        });
    });
    
    // Simple Rating System
    const ratingStars = document.querySelectorAll('.rating-star');
    
    if (ratingStars.length > 0) {
        const simpleRating = document.querySelector('.simple-rating');
        const webtoonId = simpleRating.dataset.webtoonId;
        const ratingScore = document.querySelector('.rating-score');
        
        // Add hover effect
        ratingStars.forEach((star, index) => {
            // Mouseover event
            star.addEventListener('mouseover', function() {
                // Highlight current star and all previous stars
                for (let i = 0; i <= index; i++) {
                    ratingStars[i].classList.remove('far');
                    ratingStars[i].classList.add('fas');
                }
                
                // Unhighlight remaining stars
                for (let i = index + 1; i < ratingStars.length; i++) {
                    ratingStars[i].classList.remove('fas');
                    ratingStars[i].classList.add('far');
                }
            });
            
            // Click event for rating
            star.addEventListener('click', function() {
                // Convert 5-star score to 10-point score for the backend
                const starScore = parseInt(this.dataset.score);
                const backendScore = starScore * 2; // Convert to 10-point scale
                
                // Only process if logged in (check for webtoon ID)
                if (webtoonId) {
                    fetch(`/api/rate/${webtoonId}/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken'),
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        body: `score=${backendScore}`
                    })
                    .then(response => response.json())
                    .then(data => {
                        // Update score display (convert 10-point to 5-point)
                        if (ratingScore) {
                            const displayScore = (data.avg_rating / 2).toFixed(1);
                            ratingScore.textContent = `${displayScore}/5`;
                        }
                        
                        // Update user rating text (convert 10-point to 5-point)
                        let userRatingText = document.querySelector('.user-rating-text');
                        const userDisplayScore = (data.score / 2).toFixed(1);
                        if (userRatingText) {
                            userRatingText.textContent = `(Senin puanın: ${userDisplayScore})`;
                        } else {
                            const newRatingText = document.createElement('span');
                            newRatingText.className = 'user-rating-text';
                            newRatingText.textContent = `(Senin puanın: ${userDisplayScore})`;
                            simpleRating.appendChild(newRatingText);
                        }
                        
                        // Update star display based on new average
                        updateStarDisplay(data.avg_rating);
                        
                        // Update the data attribute for mouseout reset
                        simpleRating.dataset.avgRating = data.avg_rating;
                    })
                    .catch(error => console.error('Error:', error));
                }
            });
        });
        
        // Reset stars on mouseout
        simpleRating.addEventListener('mouseout', function() {
            const avgRating = parseFloat(this.dataset.avgRating);
            updateStarDisplay(avgRating);
        });
        
        // Helper function to update star display based on rating
        function updateStarDisplay(rating) {
            ratingStars.forEach((star, i) => {
                // Get the score threshold for this star position (1-indexed)
                const position = i + 1;
                const threshold = position * 2;
                
                if (rating >= threshold) {
                    star.classList.remove('far');
                    star.classList.add('fas');
                } else {
                    star.classList.remove('fas');
                    star.classList.add('far');
                }
            });
        }
    }
    
    // Comment form submission
    const commentForm = document.getElementById('comment-form');
    if (commentForm) {
        commentForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            
            fetch('/api/comment/add/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Create new comment element
                const commentsList = document.getElementById('comments-list');
                const newComment = document.createElement('div');
                newComment.className = 'comment';
                newComment.innerHTML = `
                    <div class="comment-header">
                        <span class="comment-username">${data.username}</span>
                        <span class="comment-date">${data.created_date}</span>
                    </div>
                    <div class="comment-content">
                        ${data.content}
                    </div>
                `;
                
                // Add the new comment to the top of the list
                commentsList.insertBefore(newComment, commentsList.firstChild);
                
                // Clear the form
                document.getElementById('id_content').value = '';
            })
            .catch(error => console.error('Error:', error));
        });
    }
    
    // Helper function to get CSRF token from cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}); 