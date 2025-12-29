// Admin Panel JavaScript

// Global state
let currentPage = 0;
let pageSize = 50;
let totalRules = 0;
let currentFilters = {};
let authCredentials = null;
let filtersData = null;

// Retail Asset Charges state
let retailCurrentPage = 0;
let retailTotalCharges = 0;
let retailCurrentFilters = {};
let retailFiltersData = null;

// Location service state
let branchCurrentPage = 0;
let branchTotalLocations = 0;
let branchCurrentFilters = {};
let machineCurrentPage = 0;
let machineTotalLocations = 0;
let machineCurrentFilters = {};
let priorityCurrentPage = 0;
let priorityTotalLocations = 0;
let priorityCurrentFilters = {};
let locationFiltersData = null;

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
    setupEventListeners();
});

// Authentication
function checkAuth() {
    const stored = localStorage.getItem('adminAuth');
    if (stored) {
        try {
            authCredentials = JSON.parse(stored);
            testAuth();
        } catch (e) {
            showLogin();
        }
    } else {
        showLogin();
    }
}

function showLogin() {
    document.getElementById('loginModal').style.display = 'block';
    document.getElementById('mainContent').style.display = 'none';
}

function hideLogin() {
    document.getElementById('loginModal').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';
}

function testAuth() {
    fetch('/api/health', {
        headers: {
            'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
        }
    })
    .then(response => {
        if (response.ok) {
            hideLogin();
            loadFilters();
            loadRules();
            loadRetailAssetFilters();
            loadRetailAssetCharges();
            loadLocationFilters();
            loadBranches();
            loadMachines();
            loadPriorityCenters();
        } else {
            showLogin();
        }
    })
    .catch(() => showLogin());
}

// Event Listeners
function setupEventListeners() {
    // Login form
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    
    // Filters
    document.getElementById('applyFilters').addEventListener('click', applyFilters);
    document.getElementById('clearFilters').addEventListener('click', clearFilters);
    document.getElementById('addNewRule').addEventListener('click', showAddModal);
    
    // Pagination
    document.getElementById('prevPage').addEventListener('click', () => {
        if (currentPage > 0) {
            currentPage--;
            loadRules();
        }
    });
    
    document.getElementById('nextPage').addEventListener('click', () => {
        if ((currentPage + 1) * pageSize < totalRules) {
            currentPage++;
            loadRules();
        }
    });
    
    // Edit form
    document.getElementById('editForm').addEventListener('submit', handleSave);
    
    // Retail Asset Charges filters
    document.getElementById('retailApplyFilters').addEventListener('click', applyRetailFilters);
    document.getElementById('retailClearFilters').addEventListener('click', clearRetailFilters);
    document.getElementById('addNewRetailCharge').addEventListener('click', showAddRetailModal);
    
    // Location service filters
    document.getElementById('branchApplyFilters').addEventListener('click', applyBranchFilters);
    document.getElementById('branchClearFilters').addEventListener('click', clearBranchFilters);
    document.getElementById('machineApplyFilters').addEventListener('click', applyMachineFilters);
    document.getElementById('machineClearFilters').addEventListener('click', clearMachineFilters);
    document.getElementById('priorityApplyFilters').addEventListener('click', applyPriorityFilters);
    document.getElementById('priorityClearFilters').addEventListener('click', clearPriorityFilters);
    
    // Location pagination
    document.getElementById('branchPrevPage').addEventListener('click', () => {
        if (branchCurrentPage > 0) {
            branchCurrentPage--;
            loadBranches();
        }
    });
    document.getElementById('branchNextPage').addEventListener('click', () => {
        if ((branchCurrentPage + 1) * pageSize < branchTotalLocations) {
            branchCurrentPage++;
            loadBranches();
        }
    });
    
    document.getElementById('machinePrevPage').addEventListener('click', () => {
        if (machineCurrentPage > 0) {
            machineCurrentPage--;
            loadMachines();
        }
    });
    document.getElementById('machineNextPage').addEventListener('click', () => {
        if ((machineCurrentPage + 1) * pageSize < machineTotalLocations) {
            machineCurrentPage++;
            loadMachines();
        }
    });
    
    document.getElementById('priorityPrevPage').addEventListener('click', () => {
        if (priorityCurrentPage > 0) {
            priorityCurrentPage--;
            loadPriorityCenters();
        }
    });
    document.getElementById('priorityNextPage').addEventListener('click', () => {
        if ((priorityCurrentPage + 1) * pageSize < priorityTotalLocations) {
            priorityCurrentPage++;
            loadPriorityCenters();
        }
    });
    
    // Retail pagination
    document.getElementById('retailPrevPage').addEventListener('click', () => {
        if (retailCurrentPage > 0) {
            retailCurrentPage--;
            loadRetailAssetCharges();
        }
    });
    
    document.getElementById('retailNextPage').addEventListener('click', () => {
        if ((retailCurrentPage + 1) * pageSize < retailTotalCharges) {
            retailCurrentPage++;
            loadRetailAssetCharges();
        }
    });
}

// Tab switching
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    if (tabName === 'card-fees') {
        document.getElementById('card-fees-tab').classList.add('active');
        document.querySelector('.tab-btn[onclick="switchTab(\'card-fees\')"]').classList.add('active');
    } else if (tabName === 'retail-assets') {
        document.getElementById('retail-assets-tab').classList.add('active');
        document.querySelector('.tab-btn[onclick="switchTab(\'retail-assets\')"]').classList.add('active');
    } else if (tabName === 'branches') {
        document.getElementById('branches-tab').classList.add('active');
        document.querySelector('.tab-btn[onclick="switchTab(\'branches\')"]').classList.add('active');
        loadBranches();
    } else if (tabName === 'machines') {
        document.getElementById('machines-tab').classList.add('active');
        document.querySelector('.tab-btn[onclick="switchTab(\'machines\')"]').classList.add('active');
        loadMachines();
    } else if (tabName === 'priority-centers') {
        document.getElementById('priority-centers-tab').classList.add('active');
        document.querySelector('.tab-btn[onclick="switchTab(\'priority-centers\')"]').classList.add('active');
        loadPriorityCenters();
    }
}

// Login Handler
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');
    
    try {
        const response = await fetch('/api/health', {
            headers: {
                'Authorization': 'Basic ' + btoa(username + ':' + password)
            }
        });
        
        if (response.ok) {
            authCredentials = { username, password };
            localStorage.setItem('adminAuth', JSON.stringify(authCredentials));
            errorDiv.textContent = '';
            errorDiv.classList.remove('show');
            hideLogin();
            loadFilters();
            loadRules();
        } else {
            errorDiv.textContent = 'Invalid username or password';
            errorDiv.classList.add('show');
        }
    } catch (error) {
        errorDiv.textContent = 'Connection error. Please try again.';
        errorDiv.classList.add('show');
    }
}

// API Helper
async function apiCall(endpoint, options = {}) {
    const defaultHeaders = {
        'Content-Type': 'application/json',
        'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
    };
    
    const response = await fetch(endpoint, {
        ...options,
        headers: { ...defaultHeaders, ...options.headers }
    });
    
    if (response.status === 401) {
        localStorage.removeItem('adminAuth');
        showLogin();
        throw new Error('Unauthorized');
    }
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
}

// Load Filters
async function loadFilters() {
    try {
        filtersData = await apiCall('/api/filters');
        
        // Populate filter dropdowns
        populateSelect('filterChargeType', filtersData.charge_types);
        populateSelect('filterCardCategory', filtersData.card_categories);
        populateSelect('filterCardNetwork', filtersData.card_networks);
        populateSelect('filterCardProduct', filtersData.card_products);
        populateSelect('filterProductLine', filtersData.product_lines);
    } catch (error) {
        console.error('Error loading filters:', error);
        showError('Failed to load filters');
    }
}

function populateSelect(selectId, options) {
    const select = document.getElementById(selectId);
    // Keep the "All" option
    const allOption = select.options[0];
    select.innerHTML = '';
    select.appendChild(allOption);
    
    options.forEach(option => {
        const opt = document.createElement('option');
        opt.value = option;
        opt.textContent = option;
        select.appendChild(opt);
    });
}

// Load Rules
async function loadRules() {
    const tbody = document.getElementById('rulesTableBody');
    tbody.innerHTML = '<tr><td colspan="11" class="loading">Loading...</td></tr>';
    
    try {
        const params = new URLSearchParams({
            limit: pageSize,
            offset: currentPage * pageSize,
            ...currentFilters
        });
        
        const data = await apiCall(`/api/rules?${params}`);
        totalRules = data.total;
        
        updatePagination();
        renderRules(data.rules);
        
        document.getElementById('totalCount').textContent = `Total: ${totalRules}`;
        document.getElementById('showingCount').textContent = `Showing: ${data.rules.length}`;
    } catch (error) {
        console.error('Error loading rules:', error);
        tbody.innerHTML = `<tr><td colspan="11" class="loading" style="color: red;">Error: ${error.message}</td></tr>`;
    }
}

function renderRules(rules) {
    const tbody = document.getElementById('rulesTableBody');
    
    if (rules.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="loading">No rules found</td></tr>';
        return;
    }
    
    tbody.innerHTML = rules.map(rule => `
        <tr>
            <td title="${rule.fee_id}">${rule.fee_id.substring(0, 8)}...</td>
            <td>${rule.charge_type}</td>
            <td>${rule.card_category}</td>
            <td>${rule.card_network}</td>
            <td>${rule.card_product || '-'}</td>
            <td>${formatNumber(rule.fee_value)}</td>
            <td>${rule.fee_unit}</td>
            <td>${rule.fee_basis}</td>
            <td>${rule.effective_from}</td>
            <td><span class="status-badge status-${rule.status.toLowerCase()}">${rule.status}</span></td>
            <td class="actions-cell">
                <button class="btn btn-primary btn-small" onclick="editRule('${rule.fee_id}')">Edit</button>
                <button class="btn btn-danger btn-small" onclick="deleteRule('${rule.fee_id}')">Delete</button>
            </td>
        </tr>
    `).join('');
}

function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 4
    }).format(num);
}

function updatePagination() {
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    const pageInfo = document.getElementById('pageInfo');
    
    prevBtn.disabled = currentPage === 0;
    nextBtn.disabled = (currentPage + 1) * pageSize >= totalRules;
    
    const start = currentPage * pageSize + 1;
    const end = Math.min((currentPage + 1) * pageSize, totalRules);
    pageInfo.textContent = `Page ${currentPage + 1} (${start}-${end} of ${totalRules})`;
}

// Filters
function applyFilters() {
    currentFilters = {};
    
    const chargeType = document.getElementById('filterChargeType').value;
    const cardCategory = document.getElementById('filterCardCategory').value;
    const cardNetwork = document.getElementById('filterCardNetwork').value;
    const cardProduct = document.getElementById('filterCardProduct').value;
    const productLine = document.getElementById('filterProductLine').value;
    const statusFilter = document.getElementById('filterStatus').value;
    
    if (chargeType) currentFilters.charge_type = chargeType;
    if (cardCategory) currentFilters.card_category = cardCategory;
    if (cardNetwork) currentFilters.card_network = cardNetwork;
    if (cardProduct) currentFilters.card_product = cardProduct;
    if (productLine) currentFilters.product_line = productLine;
    if (statusFilter) currentFilters.status_filter = statusFilter;
    
    currentPage = 0;
    loadRules();
}

function clearFilters() {
    document.getElementById('filterChargeType').value = '';
    document.getElementById('filterCardCategory').value = '';
    document.getElementById('filterCardNetwork').value = '';
    document.getElementById('filterCardProduct').value = '';
    document.getElementById('filterProductLine').value = '';
    document.getElementById('filterStatus').value = '';
    
    currentFilters = {};
    currentPage = 0;
    loadRules();
}

// Edit Rule
async function editRule(feeId) {
    try {
        const rule = await apiCall(`/api/rules/${feeId}`);
        populateEditForm(rule);
        document.getElementById('editModal').style.display = 'block';
        document.getElementById('modalTitle').textContent = 'Edit Fee Rule';
    } catch (error) {
        showError('Failed to load rule: ' + error.message);
    }
}

function showAddModal() {
    // Clear form
    document.getElementById('editForm').reset();
    document.getElementById('editFeeId').value = '';
    
    // Set defaults
    document.getElementById('editCardCategory').value = 'CREDIT';
    document.getElementById('editFeeUnit').value = 'BDT';
    document.getElementById('editFeeBasis').value = 'PER_YEAR';
    document.getElementById('editConditionType').value = 'NONE';
    document.getElementById('editPriority').value = '100';
    document.getElementById('editStatus').value = 'ACTIVE';
    document.getElementById('editProductLine').value = 'CREDIT_CARDS';
    document.getElementById('editEffectiveFrom').value = new Date().toISOString().split('T')[0];
    
    document.getElementById('editModal').style.display = 'block';
    document.getElementById('modalTitle').textContent = 'Add New Fee Rule';
}

function populateEditForm(rule) {
    document.getElementById('editFeeId').value = rule.fee_id;
    document.getElementById('editChargeType').value = rule.charge_type;
    document.getElementById('editCardCategory').value = rule.card_category;
    document.getElementById('editCardNetwork').value = rule.card_network;
    document.getElementById('editCardProduct').value = rule.card_product || '';
    document.getElementById('editFullCardName').value = rule.full_card_name || '';
    document.getElementById('editFeeValue').value = rule.fee_value;
    document.getElementById('editFeeUnit').value = rule.fee_unit;
    document.getElementById('editFeeBasis').value = rule.fee_basis;
    document.getElementById('editMinFeeValue').value = rule.min_fee_value || '';
    document.getElementById('editMinFeeUnit').value = rule.min_fee_unit || '';
    document.getElementById('editMaxFeeValue').value = rule.max_fee_value || '';
    document.getElementById('editFreeEntitlementCount').value = rule.free_entitlement_count || '';
    document.getElementById('editConditionType').value = rule.condition_type;
    document.getElementById('editNoteReference').value = rule.note_reference || '';
    document.getElementById('editPriority').value = rule.priority;
    document.getElementById('editStatus').value = rule.status;
    document.getElementById('editProductLine').value = rule.product_line;
    document.getElementById('editEffectiveFrom').value = rule.effective_from;
    document.getElementById('editEffectiveTo').value = rule.effective_to || '';
    document.getElementById('editRemarks').value = rule.remarks || '';
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
    document.getElementById('editError').textContent = '';
    document.getElementById('editError').classList.remove('show');
}

async function handleSave(e) {
    e.preventDefault();
    const errorDiv = document.getElementById('editError');
    errorDiv.textContent = '';
    errorDiv.classList.remove('show');
    
    const feeId = document.getElementById('editFeeId').value;
    const formData = {
        charge_type: document.getElementById('editChargeType').value,
        card_category: document.getElementById('editCardCategory').value,
        card_network: document.getElementById('editCardNetwork').value,
        card_product: document.getElementById('editCardProduct').value,
        full_card_name: document.getElementById('editFullCardName').value || null,
        fee_value: parseFloat(document.getElementById('editFeeValue').value),
        fee_unit: document.getElementById('editFeeUnit').value,
        fee_basis: document.getElementById('editFeeBasis').value,
        min_fee_value: document.getElementById('editMinFeeValue').value ? parseFloat(document.getElementById('editMinFeeValue').value) : null,
        min_fee_unit: document.getElementById('editMinFeeUnit').value || null,
        max_fee_value: document.getElementById('editMaxFeeValue').value ? parseFloat(document.getElementById('editMaxFeeValue').value) : null,
        free_entitlement_count: document.getElementById('editFreeEntitlementCount').value ? parseInt(document.getElementById('editFreeEntitlementCount').value) : null,
        condition_type: document.getElementById('editConditionType').value,
        note_reference: document.getElementById('editNoteReference').value || null,
        priority: parseInt(document.getElementById('editPriority').value),
        status: document.getElementById('editStatus').value,
        product_line: document.getElementById('editProductLine').value,
        effective_from: document.getElementById('editEffectiveFrom').value,
        effective_to: document.getElementById('editEffectiveTo').value || null,
        remarks: document.getElementById('editRemarks').value || null
    };
    
    try {
        if (feeId) {
            // Update existing
            await apiCall(`/api/rules/${feeId}`, {
                method: 'PUT',
                body: JSON.stringify(formData)
            });
            showSuccess('Rule updated successfully!');
        } else {
            // Create new
            await apiCall('/api/rules', {
                method: 'POST',
                body: JSON.stringify(formData)
            });
            showSuccess('Rule created successfully!');
        }
        
        closeEditModal();
        loadRules();
    } catch (error) {
        errorDiv.textContent = 'Error: ' + error.message;
        errorDiv.classList.add('show');
    }
}

async function deleteRule(feeId) {
    if (!confirm('Are you sure you want to delete this rule? It will be marked as INACTIVE.')) {
        return;
    }
    
    try {
        await apiCall(`/api/rules/${feeId}`, {
            method: 'DELETE'
        });
        showSuccess('Rule deleted successfully!');
        loadRules();
    } catch (error) {
        showError('Error deleting rule: ' + error.message);
    }
}

function showError(message) {
    // Create or update error message
    let errorDiv = document.querySelector('.error-message.global');
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error-message global';
        document.querySelector('.container').insertBefore(errorDiv, document.querySelector('.container').firstChild);
    }
    errorDiv.textContent = message;
    errorDiv.classList.add('show');
    setTimeout(() => errorDiv.classList.remove('show'), 5000);
}

function showSuccess(message) {
    // Create or update success message
    let successDiv = document.querySelector('.success-message.global');
    if (!successDiv) {
        successDiv = document.createElement('div');
        successDiv.className = 'success-message global';
        document.querySelector('.container').insertBefore(successDiv, document.querySelector('.container').firstChild);
    }
    successDiv.textContent = message;
    successDiv.classList.add('show');
    setTimeout(() => successDiv.classList.remove('show'), 3000);
}

// Close modal on outside click
window.onclick = function(event) {
    const loginModal = document.getElementById('loginModal');
    const editModal = document.getElementById('editModal');
    if (event.target === loginModal) {
        // Don't close login modal on outside click
    }
    if (event.target === editModal) {
        closeEditModal();
    }
}

// Retail Asset Charges Functions
async function loadRetailAssetFilters() {
    try {
        retailFiltersData = await apiCall('/api/retail-asset-filters');
        
        populateSelect('retailFilterLoanProduct', retailFiltersData.loan_products);
        populateSelect('retailFilterChargeType', retailFiltersData.charge_types);
    } catch (error) {
        console.error('Error loading retail asset filters:', error);
    }
}

async function loadRetailAssetCharges() {
    const tbody = document.getElementById('retailChargesTableBody');
    tbody.innerHTML = '<tr><td colspan="9" class="loading">Loading...</td></tr>';
    
    try {
        const params = new URLSearchParams({
            limit: pageSize,
            offset: retailCurrentPage * pageSize,
            ...retailCurrentFilters
        });
        
        const data = await apiCall(`/api/retail-asset-charges?${params}`);
        retailTotalCharges = data.total;
        
        updateRetailPagination();
        renderRetailCharges(data.charges);
        
        document.getElementById('retailTotalCount').textContent = `Total: ${retailTotalCharges}`;
        document.getElementById('retailShowingCount').textContent = `Showing: ${data.charges.length}`;
    } catch (error) {
        console.error('Error loading retail asset charges:', error);
        tbody.innerHTML = `<tr><td colspan="9" class="loading" style="color: red;">Error: ${error.message}</td></tr>`;
    }
}

function renderRetailCharges(charges) {
    const tbody = document.getElementById('retailChargesTableBody');
    
    if (charges.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading">No charges found</td></tr>';
        return;
    }
    
    tbody.innerHTML = charges.map(charge => {
        let feeDisplay = '-';
        if (charge.tier_1_fee_value) {
            feeDisplay = `Tier 1: ${charge.tier_1_fee_value}% (max ${formatNumber(charge.tier_1_max_fee)})`;
            if (charge.tier_2_fee_value) {
                feeDisplay += `; Tier 2: ${charge.tier_2_fee_value}% (max ${formatNumber(charge.tier_2_max_fee)})`;
            }
        } else if (charge.fee_value) {
            feeDisplay = `${formatNumber(charge.fee_value)} ${charge.fee_unit}`;
            if (charge.min_fee_value || charge.max_fee_value) {
                feeDisplay += ` (Min: ${formatNumber(charge.min_fee_value || 0)}, Max: ${formatNumber(charge.max_fee_value || 0)})`;
            }
        } else if (charge.original_charge_text) {
            feeDisplay = charge.original_charge_text.substring(0, 50) + (charge.original_charge_text.length > 50 ? '...' : '');
        }
        
        return `
            <tr>
                <td title="${charge.charge_id}">${charge.charge_id.substring(0, 8)}...</td>
                <td>${charge.loan_product_name}</td>
                <td>${charge.charge_type}</td>
                <td title="${charge.charge_description}">${charge.charge_description.substring(0, 40)}${charge.charge_description.length > 40 ? '...' : ''}</td>
                <td title="${charge.original_charge_text || ''}">${feeDisplay}</td>
                <td>${charge.fee_unit}</td>
                <td>${charge.effective_from}</td>
                <td><span class="status-badge status-${charge.status.toLowerCase()}">${charge.status}</span></td>
                <td class="actions-cell">
                    <button class="btn btn-primary btn-small" onclick="editRetailCharge('${charge.charge_id}')">Edit</button>
                    <button class="btn btn-danger btn-small" onclick="deleteRetailCharge('${charge.charge_id}')">Delete</button>
                </td>
            </tr>
        `;
    }).join('');
}

function updateRetailPagination() {
    const prevBtn = document.getElementById('retailPrevPage');
    const nextBtn = document.getElementById('retailNextPage');
    const pageInfo = document.getElementById('retailPageInfo');
    
    prevBtn.disabled = retailCurrentPage === 0;
    nextBtn.disabled = (retailCurrentPage + 1) * pageSize >= retailTotalCharges;
    
    const start = retailCurrentPage * pageSize + 1;
    const end = Math.min((retailCurrentPage + 1) * pageSize, retailTotalCharges);
    pageInfo.textContent = `Page ${retailCurrentPage + 1} (${start}-${end} of ${retailTotalCharges})`;
}

function applyRetailFilters() {
    retailCurrentFilters = {};
    
    const loanProduct = document.getElementById('retailFilterLoanProduct').value;
    const chargeType = document.getElementById('retailFilterChargeType').value;
    const statusFilter = document.getElementById('retailFilterStatus').value;
    
    if (loanProduct) retailCurrentFilters.loan_product = loanProduct;
    if (chargeType) retailCurrentFilters.charge_type = chargeType;
    if (statusFilter) retailCurrentFilters.status_filter = statusFilter;
    
    retailCurrentPage = 0;
    loadRetailAssetCharges();
}

function clearRetailFilters() {
    document.getElementById('retailFilterLoanProduct').value = '';
    document.getElementById('retailFilterChargeType').value = '';
    document.getElementById('retailFilterStatus').value = '';
    
    retailCurrentFilters = {};
    retailCurrentPage = 0;
    loadRetailAssetCharges();
}

async function editRetailCharge(chargeId) {
    try {
        const charge = await apiCall(`/api/retail-asset-charges/${chargeId}`);
        // For now, show alert - can add full edit modal later
        alert(`Edit functionality for retail asset charges coming soon!\n\nCharge: ${charge.charge_description}\nProduct: ${charge.loan_product_name}`);
    } catch (error) {
        showError('Failed to load charge: ' + error.message);
    }
}

async function deleteRetailCharge(chargeId) {
    if (!confirm('Are you sure you want to delete this charge? It will be marked as INACTIVE.')) {
        return;
    }
    
    try {
        await apiCall(`/api/retail-asset-charges/${chargeId}`, {
            method: 'DELETE'
        });
        showSuccess('Charge deleted successfully!');
        loadRetailAssetCharges();
    } catch (error) {
        showError('Error deleting charge: ' + error.message);
    }
}

function showAddRetailModal() {
    alert('Add new retail asset charge functionality coming soon!');
}


// Location Service Functions
// Note: Variables are declared at the top of the file (lines 18-27)

async function loadLocationFilters() {
    try {
        locationFiltersData = await apiCall('/api/locations/filters');
        
        // Populate branch filters
        const branchCitySelect = document.getElementById('branchFilterCity');
        const branchRegionSelect = document.getElementById('branchFilterRegion');
        if (branchCitySelect && branchRegionSelect) {
            branchCitySelect.innerHTML = '<option value="">All</option>';
            branchRegionSelect.innerHTML = '<option value="">All</option>';
            locationFiltersData.cities.forEach(city => {
                branchCitySelect.innerHTML += `<option value="${city}">${city}</option>`;
            });
            locationFiltersData.regions.forEach(region => {
                branchRegionSelect.innerHTML += `<option value="${region}">${region}</option>`;
            });
        }
 
 // Populate machine filters
 const machineCitySelect = document.getElementById('machineFilterCity');
 const machineRegionSelect = document.getElementById('machineFilterRegion');
        if (machineCitySelect && machineRegionSelect) {
            machineCitySelect.innerHTML = '<option value="">All</option>';
            machineRegionSelect.innerHTML = '<option value="">All</option>';
            locationFiltersData.cities.forEach(city => {
                machineCitySelect.innerHTML += `<option value="${city}">${city}</option>`;
            });
            locationFiltersData.regions.forEach(region => {
                machineRegionSelect.innerHTML += `<option value="${region}">${region}</option>`;
            });
        }
 
        // Populate priority filters
        const priorityCitySelect = document.getElementById('priorityFilterCity');
        const priorityRegionSelect = document.getElementById('priorityFilterRegion');
        if (priorityCitySelect && priorityRegionSelect) {
            priorityCitySelect.innerHTML = '<option value="">All</option>';
            priorityRegionSelect.innerHTML = '<option value="">All</option>';
            locationFiltersData.cities.forEach(city => {
                priorityCitySelect.innerHTML += `<option value="${city}">${city}</option>`;
            });
            locationFiltersData.regions.forEach(region => {
                priorityRegionSelect.innerHTML += `<option value="${region}">${region}</option>`;
            });
        }
 } catch (error) {
 console.error('Error loading location filters:', error);
 }
}

async function loadBranches() {
    try {
 const params = new URLSearchParams({
 type: 'branch',
 limit: pageSize,
 offset: branchCurrentPage * pageSize
 });
 
 if (branchCurrentFilters.city) params.append('city', branchCurrentFilters.city);
 if (branchCurrentFilters.region) params.append('region', branchCurrentFilters.region);
 if (branchCurrentFilters.search) params.append('search', branchCurrentFilters.search);
 
        const data = await apiCall(`/api/locations?${params.toString()}`);
        
        branchTotalLocations = data.total;
        document.getElementById('branchTotalCount').textContent = `Total: ${branchTotalLocations}`;
        document.getElementById('branchShowingCount').textContent = `Showing: ${data.locations.length}`;
        document.getElementById('branchPageInfo').textContent = `Page ${branchCurrentPage + 1}`;
        
        const tbody = document.getElementById('branchesTableBody');
        tbody.innerHTML = '';
        
        if (data.locations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="no-data">No branches found</td></tr>';
        } else {
            data.locations.forEach(loc => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${loc.code || ''}</td>
                    <td>${loc.name}</td>
                    <td>${loc.address.street}</td>
                    <td>${loc.address.city}</td>
                    <td>${loc.address.region}</td>
                    <td>${loc.status || ''}</td>
                `;
                tbody.appendChild(row);
            });
        }
 
 document.getElementById('branchPrevPage').disabled = branchCurrentPage === 0;
 document.getElementById('branchNextPage').disabled = (branchCurrentPage + 1) * pageSize >= branchTotalLocations;
 } catch (error) {
 console.error('Error loading branches:', error);
 const tbody = document.getElementById('branchesTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="error">Error loading branches</td></tr>';
 }
}

async function loadMachines() {
    try {
 const params = new URLSearchParams({
 limit: pageSize,
 offset: machineCurrentPage * pageSize
 });
 
 if (machineCurrentFilters.type) params.append('type', machineCurrentFilters.type);
 if (machineCurrentFilters.city) params.append('city', machineCurrentFilters.city);
 if (machineCurrentFilters.region) params.append('region', machineCurrentFilters.region);
 if (machineCurrentFilters.search) params.append('search', machineCurrentFilters.search);
 
        const data = await apiCall(`/api/locations?${params.toString()}`);
        
        machineTotalLocations = data.total;
        document.getElementById('machineTotalCount').textContent = `Total: ${machineTotalLocations}`;
        document.getElementById('machineShowingCount').textContent = `Showing: ${data.locations.length}`;
        document.getElementById('machinePageInfo').textContent = `Page ${machineCurrentPage + 1}`;
        
        const tbody = document.getElementById('machinesTableBody');
        tbody.innerHTML = '';
        
        if (data.locations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="no-data">No machines found</td></tr>';
        } else {
            data.locations.forEach(loc => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${loc.machine_type || loc.type.toUpperCase()}</td>
                    <td>${loc.machine_count || 1}</td>
                    <td>${loc.address.street}</td>
                    <td>${loc.address.city}</td>
                    <td>${loc.address.region}</td>
                `;
                tbody.appendChild(row);
            });
        }
 
 document.getElementById('machinePrevPage').disabled = machineCurrentPage === 0;
 document.getElementById('machineNextPage').disabled = (machineCurrentPage + 1) * pageSize >= machineTotalLocations;
 } catch (error) {
 console.error('Error loading machines:', error);
 const tbody = document.getElementById('machinesTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="error">Error loading machines</td></tr>';
 }
}

async function loadPriorityCenters() {
    try {
 const params = new URLSearchParams({
 type: 'priority_center',
 limit: pageSize,
 offset: priorityCurrentPage * pageSize
 });
 
 if (priorityCurrentFilters.city) params.append('city', priorityCurrentFilters.city);
 if (priorityCurrentFilters.region) params.append('region', priorityCurrentFilters.region);
 if (priorityCurrentFilters.search) params.append('search', priorityCurrentFilters.search);
 
        const data = await apiCall(`/api/locations?${params.toString()}`);
        
        priorityTotalLocations = data.total;
        document.getElementById('priorityTotalCount').textContent = `Total: ${priorityTotalLocations}`;
        document.getElementById('priorityShowingCount').textContent = `Showing: ${data.locations.length}`;
        document.getElementById('priorityPageInfo').textContent = `Page ${priorityCurrentPage + 1}`;
        
        const tbody = document.getElementById('priorityCentersTableBody');
        tbody.innerHTML = '';
        
        if (data.locations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="no-data">No priority centers found</td></tr>';
        } else {
            data.locations.forEach(loc => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${loc.name}</td>
                    <td>${loc.address.city}</td>
                    <td>${loc.address.region}</td>
                `;
                tbody.appendChild(row);
            });
        }
 
 document.getElementById('priorityPrevPage').disabled = priorityCurrentPage === 0;
 document.getElementById('priorityNextPage').disabled = (priorityCurrentPage + 1) * pageSize >= priorityTotalLocations;
 } catch (error) {
 console.error('Error loading priority centers:', error);
 const tbody = document.getElementById('priorityCentersTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="3" class="error">Error loading priority centers</td></tr>';
 }
}

function applyBranchFilters() {
 branchCurrentFilters = {};
 const city = document.getElementById('branchFilterCity').value;
 const region = document.getElementById('branchFilterRegion').value;
 const search = document.getElementById('branchFilterSearch').value;
 
 if (city) branchCurrentFilters.city = city;
 if (region) branchCurrentFilters.region = region;
 if (search) branchCurrentFilters.search = search;
 
 branchCurrentPage = 0;
 loadBranches();
}

function clearBranchFilters() {
 document.getElementById('branchFilterCity').value = '';
 document.getElementById('branchFilterRegion').value = '';
 document.getElementById('branchFilterSearch').value = '';
 branchCurrentFilters = {};
 branchCurrentPage = 0;
 loadBranches();
}

function applyMachineFilters() {
 machineCurrentFilters = {};
 const type = document.getElementById('machineFilterType').value;
 const city = document.getElementById('machineFilterCity').value;
 const region = document.getElementById('machineFilterRegion').value;
 const search = document.getElementById('machineFilterSearch').value;
 
 if (type) machineCurrentFilters.type = type;
 if (city) machineCurrentFilters.city = city;
 if (region) machineCurrentFilters.region = region;
 if (search) machineCurrentFilters.search = search;
 
 machineCurrentPage = 0;
 loadMachines();
}

function clearMachineFilters() {
 document.getElementById('machineFilterType').value = '';
 document.getElementById('machineFilterCity').value = '';
 document.getElementById('machineFilterRegion').value = '';
 document.getElementById('machineFilterSearch').value = '';
 machineCurrentFilters = {};
 machineCurrentPage = 0;
 loadMachines();
}

function applyPriorityFilters() {
 priorityCurrentFilters = {};
 const city = document.getElementById('priorityFilterCity').value;
 const region = document.getElementById('priorityFilterRegion').value;
 const search = document.getElementById('priorityFilterSearch').value;
 
 if (city) priorityCurrentFilters.city = city;
 if (region) priorityCurrentFilters.region = region;
 if (search) priorityCurrentFilters.search = search;
 
 priorityCurrentPage = 0;
 loadPriorityCenters();
}

function clearPriorityFilters() {
 document.getElementById('priorityFilterCity').value = '';
 document.getElementById('priorityFilterRegion').value = '';
 document.getElementById('priorityFilterSearch').value = '';
 priorityCurrentFilters = {};
 priorityCurrentPage = 0;
 loadPriorityCenters();
}
