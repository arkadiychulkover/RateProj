async function loadRandomUser() {
    try {
        const response = await fetch("/lenta/users/get_random_user/");
        if (!response.ok) return;

        const user = await response.json();

        document.getElementById("username").innerText = "@" + user.username;
        document.getElementById("rating").innerText = "Rating: " + (user.display_rating || user.rating);
        
        const img = document.getElementById("user-image");
        if (user.url_paths && user.url_paths.length > 0) {
            img.src = user.url_paths[0];
        }

        document.getElementById("rate-data-holder").dataset.userId = user.id;
    } catch (e) {
        console.error(e);
    }
}

async function updateGlobalRating() {
    try {
        const res = await fetch('/lenta/users/get_user_rating/');
        if (res.ok) {
            const data = await res.json();
            const label = document.getElementById('UsersRating');
            if (label) label.innerText = data.rating;
        }
    } catch (e) {
        console.error(e);
    }
}

document.addEventListener("click", async function(e) {
    if (e.target.classList.contains("rate-num")) {
        const userId = document.getElementById("rate-data-holder").dataset.userId;
        const rateValue = e.target.dataset.value;

        if (!userId) return;

        try {
            const response = await fetch(`/lenta/users/${userId}/add_rating/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : ""
                },
                body: JSON.stringify({ rate: rateValue })
            });

            if (response.ok) {
                await loadRandomUser();
                await updateGlobalRating();
            }
        } catch (err) {
            console.error(err);
        }
    }
});

document.addEventListener("DOMContentLoaded", () => {
    loadRandomUser();
    updateGlobalRating();
});