document.addEventListener('DOMContentLoaded', () => {
    // 1. Избранное
    const favoriteButtons = document.querySelectorAll('.favorite-btn, .card-favorite');
    
    favoriteButtons.forEach(button => {
        button.addEventListener('click', async (e) => {
            e.preventDefault();
            const productId = button.dataset.productId;
            if (!productId) return;

            try {
                const response = await fetch(`/favorites/toggle/${productId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.is_favorite) {
                        button.classList.add('active');
                    } else {
                        button.classList.remove('active');
                    }
                } else if (response.status === 401) {
                    alert('Для добавления в избранное необходимо войти в аккаунт.');
                    window.location.href = '/login';
                }
            } catch (error) {
                console.error('Ошибка избранного:', error);
            }
        });
    });

    // 2. Галерея фото на странице товара
    const mainImage = document.querySelector('.product-main-image');
    const thumbnails = document.querySelectorAll('.product-thumb');

    if (mainImage && thumbnails.length > 0) {
        thumbnails.forEach(thumb => {
            thumb.addEventListener('click', () => {
                thumbnails.forEach(t => t.classList.remove('active'));
                thumb.classList.add('active');
                mainImage.src = thumb.src;
            });
        });
    }

    // 3. Сброс фильтров каталога
    const filterForm = document.querySelector('#filter-form');
    if (filterForm) {
        const resetBtn = document.querySelector('#reset-filters');
        if (resetBtn) {
            resetBtn.addEventListener('click', (e) => {
                e.preventDefault();
                filterForm.reset();
                window.location.href = '/catalog';
            });
        }
    }
});
