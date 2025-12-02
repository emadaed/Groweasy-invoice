// form_items.js - INVENTORY-ONLY VERSION (Manual Entry Removed)
class InvoiceFormManager {
    constructor() {
        this.inventoryData = [];
        this.usedProductIds = new Set();
        this.initialize();
    }

    initialize() {
        console.log('🔄 Initializing invoice form...');
        this.loadInventoryData();
        this.setupCoreEventListeners();
        this.createInventorySection();
        this.updateEmptyState();
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
        document.addEventListener('click', (e) => {
            // Remove item buttons
            if (e.target.classList.contains('removeItemBtn')) {
                this.removeItem(e.target);
            }

            // Inventory add button
            if (e.target.id === 'addInventoryBtn') {
                this.addInventoryItemFromDropdown();
            }

            // Show all inventory
            if (e.target.id === 'showAllInventory') {
                this.showAllInventory();
            }

            // Search result add buttons
            if (e.target.classList.contains('add-inventory-search-item')) {
                const productId = e.target.dataset.id;
                const productName = e.target.dataset.name;
                const productPrice = e.target.dataset.price;
                const productStock = e.target.dataset.stock;
                this.addInventoryItem(productId, productName, productPrice, productStock);
            }
        });

        // Inventory search
        document.addEventListener('input', (e) => {
            if (e.target.id === 'inventorySearch') {
                this.searchInventory(e.target.value);
            }
        });

        // Real-time stock validation
        document.addEventListener('input', (e) => {
            if (e.target.name === 'item_qty[]') {
                this.validateQuantityInRealTime(e.target);
            }
        });
    }

    createInventorySection() {
        // ✅ Inventory section now exists in form.html - no need to create dynamically
        if (document.getElementById('inventorySection')) {
            console.log('✅ Inventory section found in HTML');
            return;
        } else {
            console.error('❌ Inventory section missing from form.html');
        }
    }

    updateInventoryDropdown() {
        const dropdown = document.getElementById('inventoryDropdown');
        if (!dropdown) return;

        dropdown.innerHTML = '<option value="">Select product...</option>';

        this.inventoryData.forEach(item => {
            // Skip items already in invoice
            if (this.usedProductIds.has(item.id.toString())) {
                return;
            }

            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = `${item.name} - $${item.price} (Stock: ${item.stock})`;
            option.dataset.name = item.name;
            option.dataset.price = item.price;
            option.dataset.stock = item.stock;
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
            item.name.toLowerCase().includes(searchTerm.toLowerCase()) &&
            !this.usedProductIds.has(item.id.toString())
        );

        this.displaySearchResults(filteredItems);
    }

    showAllInventory() {
        const availableItems = this.inventoryData.filter(item =>
            !this.usedProductIds.has(item.id.toString())
        );
        this.displaySearchResults(availableItems);
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
            <div class="row g-3">
                ${items.map(item => `
                    <div class="col-12 col-md-6 col-lg-4">
                        <div class="card h-100 shadow-sm hover-shadow">
                            <div class="card-body">
                                <h6 class="card-title text-primary mb-2">${this.escapeHtml(item.name)}</h6>
                                <div class="mb-3">
                                    <div class="d-flex justify-content-between mb-1">
                                        <span class="text-muted">Price:</span>
                                        <strong class="text-success">$${item.price}</strong>
                                    </div>
                                    <div class="d-flex justify-content-between">
                                        <span class="text-muted">Stock:</span>
                                        <span class="badge ${item.stock > 10 ? 'bg-success' : item.stock > 0 ? 'bg-warning' : 'bg-danger'}">
                                            ${item.stock} units
                                        </span>
                                    </div>
                                </div>
                                <button type="button" class="btn btn-sm btn-success w-100 add-inventory-search-item"
                                        data-id="${item.id}"
                                        data-name="${this.escapeHtml(item.name)}"
                                        data-price="${item.price}"
                                        data-stock="${item.stock}">
                                    ➕ Add to Invoice
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
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
            selectedOption.dataset.price,
            selectedOption.dataset.stock
        );

        dropdown.selectedIndex = 0;
    }

    addInventoryItem(productId, productName, productPrice, productStock) {
        // Duplicate prevention check
        if (this.usedProductIds.has(productId)) {
            this.showToast('⚠️ This item is already in the invoice', 'warning');
            return;
        }

        const itemsContainer = document.getElementById('itemsContainer');
        if (!itemsContainer) {
            console.error('❌ Items container not found');
            return;
        }

        // Add to used products tracker
        this.usedProductIds.add(productId);

        // Create new item row
        const newRow = document.createElement('div');
        newRow.className = 'row g-2 align-items-end mb-2 item-row';
        newRow.innerHTML = this.createItemRowHTML(productName, productPrice, productId, productStock);

        // Add to container
        itemsContainer.appendChild(newRow);

        this.showToast(`📦 ${productName} added to invoice!`);
        this.updateEmptyState();

        // Update dropdown to exclude this item
        this.updateInventoryDropdown();

        // Clear search
        const resultsDiv = document.getElementById('inventoryResults');
        if (resultsDiv) resultsDiv.style.display = 'none';

        const searchInput = document.getElementById('inventorySearch');
        if (searchInput) searchInput.value = '';
    }

    createItemRowHTML(name = '', price = '', productId = '', stock = '') {
        const stockInfo = `<small class="text-muted d-block">Available stock: ${stock}</small>`;

        return `
            <div class="col-md-6">
                <label class="form-label small">Item/Service Name</label>
                <input type="text" name="item_name[]" class="form-control"
                       value="${this.escapeHtml(name)}" required readonly>
                ${stockInfo}
                <input type="hidden" name="item_id[]" value="${productId}">
            </div>
            <div class="col-md-3">
                <label class="form-label small">Quantity</label>
                <input type="number" name="item_qty[]" class="form-control"
                       placeholder="Qty" required min="1" value="1" max="${stock}">
                <small class="text-muted">Max: ${stock}</small>
            </div>
            <div class="col-md-2">
                <label class="form-label small">Price ($)</label>
                <input type="number" name="item_price[]" class="form-control"
                       value="${price}" required min="0" step="0.01" readonly>
            </div>
            <div class="col-md-1 text-end">
                <button type="button" class="btn btn-light removeItemBtn mt-3" title="Remove">&times;</button>
            </div>
        `;
    }

    removeItem(button) {
        const row = button.closest('.item-row');
        const itemsContainer = document.getElementById('itemsContainer');

        if (!row || !itemsContainer) return;

        // Remove from used products tracker
        const productIdInput = row.querySelector('input[name="item_id[]"]');
        if (productIdInput && productIdInput.value) {
            this.usedProductIds.delete(productIdInput.value);
        }

        // Remove row
        row.remove();
        this.showToast('🗑️ Item removed', 'error');

        // Update dropdown to include this item again
        this.updateInventoryDropdown();
        this.updateEmptyState();
    }

    validateQuantityInRealTime(input) {
        const row = input.closest('.item-row');
        const productIdInput = row.querySelector('input[name="item_id[]"]');

        if (!productIdInput || !productIdInput.value) return;

        const productId = productIdInput.value;
        const requestedQty = parseInt(input.value) || 0;

        // Find product in inventory data
        const product = this.inventoryData.find(item => item.id.toString() === productId);
        if (!product) return;

        if (requestedQty > product.stock) {
            input.classList.add('is-invalid');
            this.showToast(`⚠️ Only ${product.stock} units available for ${product.name}`, 'warning');
        } else {
            input.classList.remove('is-invalid');
        }
    }

    updateEmptyState() {
        const itemsContainer = document.getElementById('itemsContainer');
        const noItemsMessage = document.getElementById('noItemsMessage');

        if (!itemsContainer || !noItemsMessage) return;

        const itemRows = itemsContainer.querySelectorAll('.item-row');

        if (itemRows.length === 0) {
            noItemsMessage.style.display = 'block';
        } else {
            noItemsMessage.style.display = 'none';
        }
    }

    showToast(message, type = 'success') {
        if (typeof window.showToast === 'function') {
            const bgColor = type === 'error' ? '#dc3545' : type === 'warning' ? '#ffc107' : '#28a745';
            window.showToast(message, bgColor);
        } else {
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