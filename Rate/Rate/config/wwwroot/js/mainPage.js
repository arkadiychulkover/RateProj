// ── Тема ─────────────────────────────────────────────────────────────────────
function toggleTheme() {
    const isLight = document.body.classList.toggle('light');
    const icon    = document.getElementById('themeIcon');
    const label   = document.getElementById('themeLabel');
    if (icon)  icon.className      = isLight ? 'ti ti-sun'  : 'ti ti-moon';
    if (label) label.textContent   = isLight ? 'Тёмная'     : 'Светлая';
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
}

// Восстанавливаем тему при загрузке
(function () {
    if (localStorage.getItem('theme') === 'light') {
        document.body.classList.add('light');
        const icon  = document.getElementById('themeIcon');
        const label = document.getElementById('themeLabel');
        if (icon)  icon.className    = 'ti ti-sun';
        if (label) label.textContent = 'Тёмная';
    }
})();

// ── Лента: загрузка случайного пользователя ──────────────────────────────────
async function loadRandomUser() {
    try {
        const response = await fetch('/lenta/users/get_random_user/');
        if (!response.ok) return;

        const user = await response.json();

        const usernameEl = document.getElementById('username');
        const ratingEl   = document.getElementById('rating');
        const img1       = document.getElementById('user-image-1');
        const img2       = document.getElementById('user-image-2');
        const holder     = document.getElementById('rate-data-holder');

        if (usernameEl) usernameEl.innerText = '@' + user.username;
        if (ratingEl)   ratingEl.innerText   = 'Rating: ' + (user.display_rating || user.rating);

        if (img1 && img2) {
            if (user.url_paths && user.url_paths.length >= 2) {
                img1.src = user.url_paths[0];
                img2.src = user.url_paths[1];
            } else if (user.url_paths && user.url_paths.length === 1) {
                img1.src = user.url_paths[0];
                img2.src = user.url_paths[0];
            }
        }

        if (holder) holder.dataset.userId = user.id;
    } catch (e) {
        console.error('loadRandomUser:', e);
    }
}

// ── Обновление рейтинга текущего пользователя в шапке ────────────────────────
async function updateGlobalRating() {
    try {
        const res = await fetch('/lenta/users/get_user_rating/');
        if (!res.ok) return;
        const data  = await res.json();
        const label = document.getElementById('UsersRating');
        if (label) label.innerText = data.display_rating || 'N/A';
    } catch (e) {
        console.error('updateGlobalRating:', e);
    }
}

// ── Клик по кнопкам оценки ────────────────────────────────────────────────────
document.addEventListener('click', async function (e) {
    if (!e.target.classList.contains('rate-num')) return;

    const holder = document.getElementById('rate-data-holder');
    if (!holder) return;

    const userId    = holder.dataset.userId;
    const rateValue = e.target.dataset.value;
    if (!userId) return;

    try {
        const csrfCookie = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='));
        const csrfToken = csrfCookie ? csrfCookie.split('=')[1] : '';

        const response = await fetch(`/lenta/users/${userId}/add_rating/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ rate: rateValue })
        });

        if (response.ok) {
            await loadRandomUser();
            await updateGlobalRating();
        }
    } catch (err) {
        console.error('add_rating:', err);
    }
});

// ── Инит ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Лента: загружаем случайного пользователя
    if (document.getElementById('rate-data-holder')) {
        loadRandomUser();
    }
    // Рейтинг в шапке — только если пользователь залогинен
    // (auth-страницы не имеют элемента UsersRating, но запрос всё равно идёт —
    //  определяем по наличию элемента, чтобы не получать 401 на login/register)
    if (document.getElementById('UsersRating')) {
        const isAuthPage = document.querySelector('.auth-card');
        if (!isAuthPage) {
            updateGlobalRating();
        }
    }
});
