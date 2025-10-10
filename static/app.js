// Logo Management
class LogoManager {
    constructor() {
        this.currentLogo = null;
        this.init();
    }

    init() {
        this.setupLogoUpload();
        this.loadSavedLogo();
    }

    setupLogoUpload() {
        const uploadArea = document.getElementById('logoUploadArea');
        const fileInput = document.getElementById('logoFile');

        if (!uploadArea || !fileInput) {
            console.error('Logo upload elements not found');
            return;
        }

        uploadArea.addEventListener('click', () => fileInput.click());
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('border-blue-500', 'bg-blue-50');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('border-blue-500', 'bg-blue-50');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('border-blue-500', 'bg-blue-50');
            if (e.dataTransfer.files.length > 0) {
                this.handleLogoUpload(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleLogoUpload(e.target.files[0]);
            }
        });
    }

    async handleLogoUpload(file) {
        if (!file.type.startsWith('image/')) {
            alert('Please select an image file (PNG, JPG, JPEG)');
            return;
        }

        if (file.size > 2 * 1024 * 1024) {
            alert('File size must be less than 2MB');
            return;
        }

        const formData = new FormData();
        formData.append('logo', file);

        try {
            this.showUploadProgress();
            
            const response = await fetch('/api/upload-logo', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (response.ok) {
                this.currentLogo = result.filename;
                this.showLogoPreview(`/static/uploads/${result.filename}`);
                this.saveLogoToStorage();
                this.hideUploadProgress();
                alert('Logo uploaded successfully!');
            } else {
                throw new Error(result.error || 'Upload failed');
            }
        } catch (error) {
            this.hideUploadProgress();
            alert('Error uploading logo: ' + error.message);
        }
    }

    showLogoPreview(imageUrl) {
        const preview = document.getElementById('logoPreview');
        const image = document.getElementById('previewImage');
        const uploadArea = document.getElementById('logoUploadArea');
        
        if (preview && image && uploadArea) {
            image.src = imageUrl;
            preview.classList.remove('hidden');
            uploadArea.classList.add('hidden');
        }
    }

    showUploadProgress() {
        const progress = document.getElementById('logoUploadProgress');
        const progressBar = document.getElementById('progressBar');
        
        if (progress && progressBar) {
            progress.classList.remove('hidden');
            
            let width = 0;
            const interval = setInterval(() => {
                if (width >= 90) {
                    clearInterval(interval);
                } else {
                    width += 10;
                    progressBar.style.width = width + '%';
                }
            }, 100);
        }
    }

    hideUploadProgress() {
        const progress = document.getElementById('logoUploadProgress');
        const progressBar = document.getElementById('progressBar');
        
        if (progress && progressBar) {
            progressBar.style.width = '100%';
            setTimeout(() => {
                progress.classList.add('hidden');
                progressBar.style.width = '0%';
            }, 500);
        }
    }

    removeLogo() {
        this.currentLogo = null;
        const preview = document.getElementById('logoPreview');
        const uploadArea = document.getElementById('logoUploadArea');
        
        if (preview && uploadArea) {
            preview.classList.add('hidden');
            uploadArea.classList.remove('hidden');
        }
        localStorage.removeItem('digireceipt_logo');
    }

    saveLogoToStorage() {
        if (this.currentLogo) {
            localStorage.setItem('digireceipt_logo', this.currentLogo);
        }
    }

    loadSavedLogo() {
        const savedLogo = localStorage.getItem('digireceipt_logo');
        if (savedLogo) {
            this.currentLogo = savedLogo;
            this.showLogoPreview(`/static/uploads/${savedLogo}`);
        }
    }

    getLogoPath() {
        return this.currentLogo;
    }
}

// Invoice Management
class InvoiceApp {
    constructor() {
        this.lineItems = [];
        this.taxRate = 17;
        this.init();
    }

    init() {
        this.loadFromStorage();
        this.setupEventListeners();
        this.addNewItem();
        this.updateTotals();
        this.renderHistory();
    }

    setupEventListeners() {
        const taxRateInput = document.getElementById('taxRate');
        if (taxRateInput) {
            taxRateInput.addEventListener('input', (e) => {
                this.taxRate = parseFloat(e.target.value) || 0;
                const taxRateDisplay = document.getElementById('taxRateDisplay');
                if (taxRateDisplay) {
                    taxRateDisplay.textContent = this.taxRate;
                }
                this.updateTotals();
                this.saveToStorage();
            });
        }

        const autoSaveFields = ['vendorName', 'vendorAddress', 'vendorPhone', 
                               'customerName', 'customerAddress', 'customerPhone', 
                               'invoiceNumber'];
        
        autoSaveFields.forEach(field => {
            const element = document.getElementById(field);
            if (element) {
                element.addEventListener('input', () => this.saveToStorage());
            }
        });
    }

    addNewItem(name = '', quantity = 1, price = 0) {
        const item = {
            id: Date.now() + Math.random(),
            name: name,
            quantity: quantity,
            price: price
        };
        
        this.lineItems.push(item);
        this.renderItems();
        this.updateTotals();
        this.saveToStorage();
        return item;
    }

    removeItem(id) {
        this.lineItems = this.lineItems.filter(item => item.id !== id);
        this.renderItems();
        this.updateTotals();
        this.saveToStorage();
    }

    updateItem(id, field, value) {
        const item = this.lineItems.find(item => item.id === id);
        if (item) {
            if (field === 'name') {
                item[field] = value;
            } else {
                item[field] = parseFloat(value) || 0;
            }
            this.updateTotals();
            this.saveToStorage();
        }
    }

    renderItems() {
        const container = document.getElementById('itemsContainer');
        if (!container) return;

        container.innerHTML = '';

        if (this.lineItems.length === 0) {
            container.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center p-4 text-gray-500">
                        No items added. Click "Add Item" to start.
                    </td>
                </tr>
            `;
            return;
        }

        this.lineItems.forEach(item => {
            const row = document.createElement('tr');
            row.className = 'invoice-item border-t';
            row.innerHTML = `
                <td class="p-3">
                    <input type="text" value="${item.name}" 
                           oninput="app.updateItem(${item.id}, 'name', this.value)"
                           placeholder="Item description"
                           class="w-full p-2 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500">
                </td>
                <td class="p-3">
                    <input type="number" value="${item.quantity}" min="1"
                           oninput="app.updateItem(${item.id}, 'quantity', this.value)"
                           class="w-20 p-2 border border-gray-300 rounded text-center focus:ring-2 focus:ring-blue-500">
                </td>
                <td class="p-3">
                    <input type="number" value="${item.price}" step="0.01" min="0"
                           oninput="app.updateItem(${item.id}, 'price', this.value)"
                           class="w-32 p-2 border border-gray-300 rounded text-right focus:ring-2 focus:ring-blue-500">
                </td>
                <td class="p-3 text-right font-semibold">
                    Rs. ${(item.quantity * item.price).toFixed(2)}
                </td>
                <td class="p-3 text-center">
                    <button onclick="app.removeItem(${item.id})" 
                            class="text-red-500 hover:text-red-700 transition-colors">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            container.appendChild(row);
        });
    }

    calculateTotals() {
        const subtotal = this.lineItems.reduce((sum, item) => {
            return sum + (item.quantity * item.price);
        }, 0);

        const taxAmount = (subtotal * this.taxRate) / 100;
        const grandTotal = subtotal + taxAmount;

        return { subtotal, taxAmount, grandTotal };
    }

    updateTotals() {
        const { subtotal, taxAmount, grandTotal } = this.calculateTotals();
        
        const subtotalEl = document.getElementById('subtotal');
        const taxAmountEl = document.getElementById('taxAmount');
        const grandTotalEl = document.getElementById('grandTotal');
        
        if (subtotalEl) subtotalEl.textContent = `Rs. ${subtotal.toFixed(2)}`;
        if (taxAmountEl) taxAmountEl.textContent = `Rs. ${taxAmount.toFixed(2)}`;
        if (grandTotalEl) grandTotalEl.textContent = `Rs. ${grandTotal.toFixed(2)}`;
    }

    collectFormData() {
        const items = this.lineItems
            .filter(item => item.name.trim() !== '' && item.price > 0)
            .map(item => ({
                name: item.name,
                quantity: item.quantity,
                price: item.price
            }));

        return {
            vendor_name: document.getElementById('vendorName')?.value || '',
            customer_name: document.getElementById('customerName')?.value || '',
            vendor_address: document.getElementById('vendorAddress')?.value || '',
            vendor_phone: document.getElementById('vendorPhone')?.value || '',
            customer_address: document.getElementById('customerAddress')?.value || '',
            customer_phone: document.getElementById('customerPhone')?.value || '',
            invoice_number: document.getElementById('invoiceNumber')?.value || '001',
            tax_rate: this.taxRate,
            items: items,
            ...this.calculateTotals()
        };
    }

    saveToStorage() {
        const data = {
            lineItems: this.lineItems,
            taxRate: this.taxRate,
            formData: this.collectFormData()
        };
        localStorage.setItem('digireceipt_data', JSON.stringify(data));
    }

    loadFromStorage() {
        const saved = localStorage.getItem('digireceipt_data');
        if (saved) {
            try {
                const data = JSON.parse(saved);
                this.lineItems = data.lineItems || [];
                this.taxRate = data.taxRate || 17;
                
                if (data.formData) {
                    Object.keys(data.formData).forEach(key => {
                        const element = document.getElementById(key);
                        if (element && data.formData[key] !== undefined) {
                            element.value = data.formData[key];
                        }
                    });
                }
                
                const taxRateInput = document.getElementById('taxRate');
                const taxRateDisplay = document.getElementById('taxRateDisplay');
                if (taxRateInput) taxRateInput.value = this.taxRate;
                if (taxRateDisplay) taxRateDisplay.textContent = this.taxRate;
                
                this.renderItems();
            } catch (e) {
                console.error('Error loading saved data:', e);
            }
        }
    }

    clearForm() {
        if (confirm('Are you sure you want to clear all data?')) {
            this.lineItems = [];
            this.taxRate = 17;
            
            const fields = ['vendorName', 'vendorAddress', 'vendorPhone', 
                          'customerName', 'customerAddress', 'customerPhone', 
                          'invoiceNumber'];
            
            fields.forEach(field => {
                const element = document.getElementById(field);
                if (element) element.value = '';
            });
            
            const taxRateInput = document.getElementById('taxRate');
            const taxRateDisplay = document.getElementById('taxRateDisplay');
            if (taxRateInput) taxRateInput.value = '17';
            if (taxRateDisplay) taxRateDisplay.textContent = '17';
            
            this.taxRate = 17;
            this.renderItems();
            this.updateTotals();
            localStorage.removeItem('digireceipt_data');
        }
    }

    async generatePDF() {
        const formData = this.collectFormData();
        
        // Basic validation
        if (!formData.vendor_name || !formData.customer_name || formData.items.length === 0) {
            alert('Please fill in Business Name, Customer Name, and add at least one item.');
            return;
        }

        try {
            const generateBtn = document.querySelector('button[onclick="generatePDF()"]');
            const originalText = generateBtn.innerHTML;
            generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Generating...';
            generateBtn.disabled = true;

            // Add logo filename to form data
            if (window.logoManager) {
                formData.logo_filename = window.logoManager.getLogoPath();
            }

            const response = await fetch('/api/generate-pdf', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `invoice_${formData.invoice_number}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                
                // Add to history
                this.addToHistory(formData);
                alert('PDF generated and downloaded successfully!');
            } else {
                const error = await response.json();
                throw new Error(error.error || 'PDF generation failed');
            }
        } catch (error) {
            console.error('Error generating PDF:', error);
            alert('Error generating PDF: ' + error.message);
        } finally {
            const generateBtn = document.querySelector('button[onclick="generatePDF()"]');
            if (generateBtn) {
                generateBtn.innerHTML = '<i class="fas fa-file-pdf mr-2"></i>Generate PDF Invoice';
                generateBtn.disabled = false;
            }
        }
    }

    addToHistory(invoiceData) {
        const history = JSON.parse(localStorage.getItem('digireceipt_history') || '[]');
        history.unshift({
            id: Date.now(),
            invoice_number: invoiceData.invoice_number,
            customer_name: invoiceData.customer_name,
            amount: invoiceData.grandTotal,
            date: new Date().toLocaleDateString()
        });
        
        // Keep only last 10 invoices
        localStorage.setItem('digireceipt_history', JSON.stringify(history.slice(0, 10)));
        this.renderHistory();
    }

    renderHistory() {
        const history = JSON.parse(localStorage.getItem('digireceipt_history') || '[]');
        const container = document.getElementById('invoiceHistory');
        
        if (!container) return;

        if (history.length === 0) {
            container.innerHTML = '<p class="text-gray-500 text-sm text-center">No invoice history yet</p>';
            return;
        }

        container.innerHTML = history.map(invoice => `
            <div class="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                <div>
                    <div class="font-medium text-gray-800">${invoice.invoice_number}</div>
                    <div class="text-sm text-gray-600">${invoice.customer_name}</div>
                </div>
                <div class="text-right">
                    <div class="font-semibold text-green-600">Rs. ${invoice.amount.toFixed(2)}</div>
                    <div class="text-xs text-gray-500">${invoice.date}</div>
                </div>
            </div>
        `).join('');
    }
}

// Global functions
function addNewItem() {
    if (window.app) {
        window.app.addNewItem();
    }
}

function generatePDF() {
    if (window.app) {
        window.app.generatePDF();
    }
}

function clearForm() {
    if (window.app) {
        window.app.clearForm();
    }
}

function removeLogo() {
    if (window.logoManager) {
        window.logoManager.removeLogo();
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new InvoiceApp();
    window.logoManager = new LogoManager();
});