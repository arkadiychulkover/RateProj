async function loadRandomUser() {
    try {
        const response = await fetch("/lenta/users/get_random_user/");

        if (!response.ok) return;

        const user = await response.json();

        const usernameElem = document.getElementById("username");
        const ratingElem = document.getElementById("rating");
        const userImageElem = document.getElementById("user-image");
        const rateBtn = document.getElementById("rate-btn");

        if (usernameElem) usernameElem.innerText = "@" + user.username;
        
        if (ratingElem) {
            const displayRating = user.display_rating !== undefined ? user.display_rating : user.rating;
            ratingElem.innerText = "Rating: " + displayRating;
        }

        if (userImageElem && user.url_paths && user.url_paths.length > 0) {
            userImageElem.src = user.url_paths[0];
        }

        if (rateBtn) rateBtn.dataset.userId = user.id;

    } catch (error) {
        console.error(error);
    }
}

const rateBtn = document.getElementById("rate-btn");
if (rateBtn) {
    rateBtn.addEventListener("click", async function () {
        const userId = this.dataset.userId;
        if (!userId) return;

        try {
            const response = await fetch(`/lenta/users/${userId}/add_rating/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : ""
                },
                body: JSON.stringify({ rate: 10 })
            });

            if (response.ok) {
                await loadRandomUser();
            }
        } catch (error) {
            console.error(error);
        }
    });
}

loadRandomUser();