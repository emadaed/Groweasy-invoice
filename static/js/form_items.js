// form_items.js - FIXED EVENT DELEGATION VERSION
class InvoiceFormManager {
    constructor() {
        this.inventoryData = [];
        this.initialize();
    }

    initialize() {
        console.log('🔄 Initializing invoice form...');
        this.loadInventoryData();
        this.setupCoreEventListeners();
        this.createInventorySection();
    }

    loadInventoryData() {
        fetch('/api/inventory_items')
            .then(response => response.json())
            .then(items => {
                console.log(`📦 Loaded ${items.length} inventory items`);
                this.inventoryData = items;
                this.updateInventoryDropdown();
            })
            .catch(error => {
                console.error('❌ Failed to load inventory:', error);
            });
    }

    setupCoreEventListeners() {
        // Add item button - FIXED
        document.addEventListener('click', (e) => {
            if (e.target.id === 'addItemBtn') {
                e.preventDefault();
                this.addEmptyItem();
            }

            // Remove item buttons - FIXED
            if (e.target.classList.contains('removeItemBtn')) {
                this.removeItem(e.target);
            }

            // Inventory add button - FIXED
            if (e.target.id === 'addInventoryBtn') {
                this.addInventoryItemFromDropdown();
            }

            // Show all inventory - FIXED
            if (e.target.id === 'showAllInventory') {
                this.showAllInventory();
            }

            // Search result add buttons - FIXED
            if (e.target.classList.contains('add-inventory-search-item')) {
                const productId = e.target.dataset.id;
                const productName = e.target.dataset.name;
                const productPrice = e.target.dataset.price;
                this.addInventoryItem(productId, productName, productPrice);
            }
        });

        // Inventory search - FIXED
        document.addEventListener('input', (e) => {
            if (e.target.id === 'inventorySearch') {
                this.searchInventory(e.target.value);
            }
        });
    }

    createInventorySection() {
        if (document.getElementById('inventorySection')) return;

        const itemsCard = document.querySelector('.card.border-warning');
        if (!itemsCard) return;

        const inventoryHTML = `
            <div class="card mb-4 border-info" id="inventorySection">
                <div class="card-header bg-light">
                    <h5 class="mb-0 text-info">📦 Search Inventory</h5>
                </div>
                <div class="card-body">
                    <div class="mb-3">
                        <label class="form-label">Quick Search</label>
                        <div class="input-group">
                            <input type="text" class="form-control" id="inventorySearch"
                                   placeholder="Type product name...">
                            <button type="button" class="btn btn-outline-success" id="showAllInventory">
                                Show All
                            </button>
                        </div>
                    </div>
                    <div id="inventoryResults" style="display: none;"></div>

                    <div class="mb-3">
                        <label class="form-label">Or Select from List</label>
                        <div class="input-group">
                            <select class="form-control" id="inventoryDropdown">
                                <option value="">Select product...</option>
                            </select>
                            <button type="button" class="btn btn-outline-primary" id="addInventoryBtn">
                                Add to Invoice
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        itemsCard.insertAdjacentHTML('beforebegin', inventoryHTML);
        console.log('✅ Inventory section created');
    }

    updateInventoryDropdown() {
        const dropdown = document.getElementById('inventoryDropdown');
        if (!dropdown) return;

        dropdown.innerHTML = '<option value="">Select product...</option>';

        this.inventoryData.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = `${item.name} - ₹${item.price} (Stock: ${item.stock})`;
            option.dataset.name = item.name;
            option.dataset.price = item.price;
            dropdown.appendChild(option);
        });
    }

    searchInventory(searchTerm) {
        const resultsDiv = document.getElementById('inventoryResults');
        if (!resultsDiv) return;

        if (!searchTerm.trim()) {
            resultsDiv.style.display = 'none';
            return;
        }

        const filteredItems = this.inventoryData.filter(item =>
            item.name.toLowerCase().includes(searchTerm.toLowerCase())
        );

        this.displaySearchResults(filteredItems);
    }

    showAllInventory() {
        this.displaySearchResults(this.inventoryData);
    }

    displaySearchResults(items) {
        const resultsDiv = document.getElementById('inventoryResults');
        if (!resultsDiv) return;

        if (items.length === 0) {
            resultsDiv.innerHTML = '<div class="alert alert-warning">No matching products found</div>';
            resultsDiv.style.display = 'block';
            return;
        }

        const resultsHTML = `
            <div class="alert alert-info">
                <strong>Found ${items.length} product(s):</strong>
            </div>
            ${items.map(item => `
                <div class="card mb-2">
                    <div class="card-body py-2">
                        <div class="row align-items-center">
                            <div class="col">
                                <strong>${this.escapeHtml(item.name)}</strong><br>
                                <small class="text-muted">Price: ₹${item.price} | Stock: ${item.stock}</small>
                            </div>
                            <div class="col-auto">
                                <button type="button" class="btn btn-sm btn-success add-inventory-search-item"
                                        data-id="${item.id}"
                                        data-name="${this.escapeHtml(item.name)}"
                                        data-price="${item.price}">
                                    Add to Invoice
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('')}
        `;

        resultsDiv.innerHTML = resultsHTML;
        resultsDiv.style.display = 'block';
    }

    addInventoryItemFromDropdown() {
        const dropdown = document.getElementById('inventoryDropdown');
        if (!dropdown) return;

        const selectedOption = dropdown.options[dropdown.selectedIndex];

        if (!selectedOption.value) {
            this.showToast('⚠️ Please select a product first', 'warning');
            return;
        }

        this.addInventoryItem(
            selectedOption.value,
            selectedOption.dataset.name,
            selectedOption.dataset.price
        );

        dropdown.selectedIndex = 0;
    }

    addInventoryItem(productId, productName, productPrice) {
        const itemsContainer = document.getElementById('itemsContainer');
        if (!itemsContainer) {
            console.error('❌ Items container not found');
            return;
        }

        // Create new item row
        const newRow = document.createElement('div');
        newRow.className = 'row g-2 align-items-end mb-2 item-row';
        newRow.innerHTML = this.createItemRowHTML(productName, productPrice, productId);

        // Add to container
        itemsContainer.appendChild(newRow);

        this.showToast(`📦 ${productName} added to invoice!`);

        // Clear search
        const resultsDiv = document.getElementById('inventoryResults');
        if (resultsDiv) resultsDiv.style.display = 'none';

        const searchInput = document.getElementById('inventorySearch');
        if (searchInput) searchInput.value = '';
    }

    addEmptyItem() {
        const itemsContainer = document.getElementById('itemsContainer');
        if (!itemsContainer) return;

        const newRow = document.createElement('div');
        newRow.className = 'row g-2 align-items-end mb-2 item-row';
        newRow.innerHTML = this.createItemRowHTML();

        itemsContainer.appendChild(newRow);
        this.showToast('🌿 New item row added!');
    }

    createItemRowHTML(name = '', price = '', productId = '') {
        const isInventoryItem = name && price;
        const namePlaceholder = isInventoryItem ? '' : 'e.g., Web Development, Consultation';
        const pricePlaceholder = isInventoryItem ? '' : '0.00';
        const readonlyAttr = isInventoryItem ? 'readonly' : '';

        // ENABLE REMOVE BUTTONS - Remove the 'disabled' attribute
        const removeButtonDisabled = '';

        return `
            <div class="col-md-6">
                <label class="form-label small">Item/Service Name</label>
                <input type="text" name="item_name[]" class="form-control"
                       value="${this.escapeHtml(name)}"
                       placeholder="${namePlaceholder}"
                       required ${readonlyAttr}>
                <input type="hidden" name="item_id[]" value="${productId}">
            </div>
            <div class="col-md-3">
                <label class="form-label small">Quantity</label>
                <input type="number" name="item_qty[]" class="form-control"
                       placeholder="Qty" required min="1" value="1">
            </div>
            <div class="col-md-2">
                <label class="form-label small">Price ($)</label>
                <input type="number" name="item_price[]" class="form-control"
                       value="${price}" placeholder="${pricePlaceholder}"
                       required min="0" step="0.01" ${readonlyAttr}>
            </div>
            <div class="col-md-1 text-end">
                <button type="button" class="btn btn-light removeItemBtn mt-3" title="Remove" ${removeButtonDisabled}>&times;</button>
            </div>
        `;
    }

    removeItem(button) {
        const row = button.closest('.item-row');
        const itemsContainer = document.getElementById('itemsContainer');

        if (!row || !itemsContainer) return;

        // Check if this is the last row
        const allRows = itemsContainer.querySelectorAll('.item-row');
        if (allRows.length <= 1) {
            this.showToast('⚠️ At least one item is required', 'warning');
            return;
        }

        // Remove immediately
        row.remove();
        this.showToast('🗑️ Item removed', 'error');
    }

    showToast(message, type = 'success') {
        if (typeof window.showToast === 'function') {
            const bgColor = type === 'error' ? '#dc3545' : type === 'warning' ? '#ffc107' : '#28a745';
            window.showToast(message, bgColor);
        } else {
            // Fallback alert
            alert(message);
        }
    }

    escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    new InvoiceFormManager();
});