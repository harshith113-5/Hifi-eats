// Function to fetch and display menu items from the API
async function fetchMenuItems() {
    try {
        const categoryFilter = document.getElementById('categoryFilter').value;
        const subcategoryFilter = document.getElementById('subcategoryFilter').value;
        const url = new URL('http://127.0.0.1:5000/api/menu'); // URL to the Flask API

        // Adding query parameters for filters
        if (categoryFilter) {
            url.searchParams.append('category', categoryFilter);
        }
        if (subcategoryFilter) {
            url.searchParams.append('subcategory', subcategoryFilter);
        }

        const response = await fetch(url);
        const menuData = await response.json();

        const menuSection = document.querySelector('.menu');
        menuSection.innerHTML = ''; // Clear any previous content

        menuData.forEach(item => {
            const menuItem = document.createElement('div');
            menuItem.classList.add('menu-item');

            menuItem.innerHTML = `
                <img src="${item.image_path}" alt="${item.name}">
                <div class="info">
                    <h3>${item.name}</h3>
                    <p>${item.description}</p>
                    <p class="price">$${(item.price - item.discount).toFixed(2)}</p>
                    ${item.discount > 0 ? `<p class="discount">$${item.price.toFixed(2)}</p>` : ''}
                    <button>Add to Cart</button>
                </div>
            `;

            menuSection.appendChild(menuItem);
        });
    } catch (error) {
        console.error('Error fetching menu items:', error);
    }
}

// Add event listeners to filters
document.getElementById('categoryFilter').addEventListener('change', fetchMenuItems);
document.getElementById('subcategoryFilter').addEventListener('change', fetchMenuItems);

// Load the menu items when the page is ready
window.onload = fetchMenuItems;
fetch('/api/menu')
    .then(response => response.json())
    .then(data => {
        const menuDiv = document.getElementById('menu');
        data.forEach(item => {
            const itemDiv = document.createElement('div');
            itemDiv.innerHTML = `
                <h3>${item.name} - ${item.price}</h3>
                <p>${item.description}</p>
                <button onclick="addToCart(${item.id})">Add to Cart</button>
            `;
            menuDiv.appendChild(itemDiv);
        });
    });

function addToCart(itemId) {
    fetch('/api/cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: itemId, quantity: 1 })
    });
}