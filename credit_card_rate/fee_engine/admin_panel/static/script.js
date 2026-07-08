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
let retailPageSize = 25; // Default rows per page for retail charges
let retailFiltersData = null;

// Skybanking Fees state
let skybankingCurrentPage = 0;
let skybankingTotalFees = 0;
let skybankingCurrentFilters = {};
let skybankingFiltersData = null;

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

// POIs/Landmarks state
let poiCurrentPage = 0;
let poiTotal = 0;
let poiCurrentFilters = {};

// Phonebook state
let phonebookCurrentPage = 1;
let phonebookPageSize = 25;
let phonebookTotal = 0;
let phonebookCurrentFilters = {};
let phonebookFiltersData = null;
let currentViewingEmployee = null;

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
            loadSkybankingFilters();
            loadSkybankingFees();
            loadLocationFilters();
            loadBranches();
            loadMachines();
            loadPriorityCenters();
            loadPois();
            loadPhonebookFilters();
            loadPhonebookStats();
            loadPhonebook();
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
    
    // Export buttons
    const exportCardFeesBtn = document.getElementById('exportCardFees');
    if (exportCardFeesBtn) {
        exportCardFeesBtn.addEventListener('click', exportCardFeesToCSV);
    }
    
    const exportRetailChargesBtn = document.getElementById('exportRetailCharges');
    if (exportRetailChargesBtn) {
        exportRetailChargesBtn.addEventListener('click', exportRetailChargesToCSV);
    }
    
    const exportSkybankingFeesBtn = document.getElementById('exportSkybankingFees');
    if (exportSkybankingFeesBtn) {
        exportSkybankingFeesBtn.addEventListener('click', exportSkybankingFeesToCSV);
    }
    
    const exportBranchesBtn = document.getElementById('exportBranches');
    if (exportBranchesBtn) {
        exportBranchesBtn.addEventListener('click', exportBranchesToCSV);
    }
    
    const exportMachinesBtn = document.getElementById('exportMachines');
    if (exportMachinesBtn) {
        exportMachinesBtn.addEventListener('click', exportMachinesToCSV);
    }
    
    const exportPriorityCentersBtn = document.getElementById('exportPriorityCenters');
    if (exportPriorityCentersBtn) {
        exportPriorityCentersBtn.addEventListener('click', exportPriorityCentersToCSV);
    }
    
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
    
    // Location edit forms
    const editBranchForm = document.getElementById('editBranchForm');
    const editMachineForm = document.getElementById('editMachineForm');
    const editPriorityForm = document.getElementById('editPriorityForm');
    const editRetailForm = document.getElementById('editRetailForm');
    const editPoiForm = document.getElementById('editPoiForm');
    if (editBranchForm) {
        editBranchForm.addEventListener('submit', handleSaveBranch);
    }
    if (editMachineForm) {
        editMachineForm.addEventListener('submit', handleSaveMachine);
    }
    if (editPriorityForm) {
        editPriorityForm.addEventListener('submit', handleSavePriority);
    }
    if (editRetailForm) {
        editRetailForm.addEventListener('submit', handleSaveRetailCharge);
    }
    if (editPoiForm) {
        editPoiForm.addEventListener('submit', handleSavePoi);
    }
    
    // Retail Asset Charges filters
    document.getElementById('retailApplyFilters').addEventListener('click', applyRetailFilters);
    document.getElementById('retailClearFilters').addEventListener('click', clearRetailFilters);
    document.getElementById('addNewRetailCharge').addEventListener('click', showAddRetailModal);
    
    // Skybanking Fees filters
    const skybankingApplyFilters = document.getElementById('skybankingApplyFilters');
    const skybankingClearFilters = document.getElementById('skybankingClearFilters');
    const skybankingAddNewFee = document.getElementById('skybankingAddNewFee');
    if (skybankingApplyFilters) {
        skybankingApplyFilters.addEventListener('click', applySkybankingFilters);
    }
    if (skybankingClearFilters) {
        skybankingClearFilters.addEventListener('click', clearSkybankingFilters);
    }
    if (skybankingAddNewFee) {
        skybankingAddNewFee.addEventListener('click', showAddSkybankingModal);
    }
    
    // Skybanking pagination
    const skybankingPrevPage = document.getElementById('skybankingPrevPage');
    const skybankingNextPage = document.getElementById('skybankingNextPage');
    if (skybankingPrevPage) {
        skybankingPrevPage.addEventListener('click', () => {
            if (skybankingCurrentPage > 0) {
                skybankingCurrentPage--;
                loadSkybankingFees();
            }
        });
    }
    if (skybankingNextPage) {
        skybankingNextPage.addEventListener('click', () => {
            if ((skybankingCurrentPage + 1) * pageSize < skybankingTotalFees) {
                skybankingCurrentPage++;
                loadSkybankingFees();
            }
        });
    }
    
    // Location service filters
    document.getElementById('branchApplyFilters').addEventListener('click', applyBranchFilters);
    document.getElementById('branchClearFilters').addEventListener('click', clearBranchFilters);
    document.getElementById('machineApplyFilters').addEventListener('click', applyMachineFilters);
    document.getElementById('machineClearFilters').addEventListener('click', clearMachineFilters);
    document.getElementById('priorityApplyFilters').addEventListener('click', applyPriorityFilters);
    document.getElementById('priorityClearFilters').addEventListener('click', clearPriorityFilters);
    const addPriorityBtn = document.getElementById('addNewPriorityCenter');
    if (addPriorityBtn) addPriorityBtn.addEventListener('click', () => showAddPriorityModal());

    // POI filters + actions
    const poiApply = document.getElementById('poiApplyFilters');
    const poiClear = document.getElementById('poiClearFilters');
    const addNewPoiBtn = document.getElementById('addNewPoi');
    if (poiApply) poiApply.addEventListener('click', applyPoiFilters);
    if (poiClear) poiClear.addEventListener('click', clearPoiFilters);
    if (addNewPoiBtn) addNewPoiBtn.addEventListener('click', showAddPoiModal);
    
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

    // POI pagination
    const poiPrev = document.getElementById('poiPrevPage');
    const poiNext = document.getElementById('poiNextPage');
    if (poiPrev) {
        poiPrev.addEventListener('click', () => {
            if (poiCurrentPage > 0) {
                poiCurrentPage--;
                loadPois();
            }
        });
    }
    if (poiNext) {
        poiNext.addEventListener('click', () => {
            if ((poiCurrentPage + 1) * pageSize < poiTotal) {
                poiCurrentPage++;
                loadPois();
            }
        });
    }
    
    // Retail pagination
    document.getElementById('retailPrevPage').addEventListener('click', () => {
        if (retailCurrentPage > 0) {
            retailCurrentPage--;
            loadRetailAssetCharges();
        }
    });
    
    document.getElementById('retailNextPage').addEventListener('click', () => {
        if ((retailCurrentPage + 1) * retailPageSize < retailTotalCharges) {
            retailCurrentPage++;
            loadRetailAssetCharges();
        }
    });
    
    // Page size selector for retail charges
    document.getElementById('retailPageSize').addEventListener('change', (e) => {
        retailPageSize = parseInt(e.target.value, 10);
        retailCurrentPage = 0; // Reset to first page
        loadRetailAssetCharges();
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
    } else if (tabName === 'skybanking-fees') {
        document.getElementById('skybanking-fees-tab').classList.add('active');
        document.querySelector('.tab-btn[onclick="switchTab(\'skybanking-fees\')"]').classList.add('active');
        loadSkybankingFees();
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
    } else if (tabName === 'pois') {
        document.getElementById('pois-tab').classList.add('active');
        document.querySelector('.tab-btn[onclick="switchTab(\'pois\')"]').classList.add('active');
        loadPois();
    } else if (tabName === 'phonebook') {
        document.getElementById('phonebook-tab').classList.add('active');
        document.querySelector('.tab-btn[onclick="switchTab(\'phonebook\')"]').classList.add('active');
        loadPhonebookStats();
        loadPhonebook();
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
        const errorBody = await response.json().catch(() => ({}));
        let message = 'Request failed';
        if (typeof errorBody.detail === 'string') {
            message = errorBody.detail;
        } else if (errorBody.detail && typeof errorBody.detail.message === 'string') {
            message = errorBody.detail.message;
        } else if (typeof errorBody.message === 'string') {
            message = errorBody.message;
        }
        const err = new Error(message || 'Request failed');
        err.status = response.status;
        err.data = errorBody.detail ?? errorBody;
        throw err;
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
    if (!select) return;
    
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
    const answerEl = document.getElementById('editAnswerText');
    if (answerEl) answerEl.value = rule.answer_text || '';
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
        answer_text: (document.getElementById('editAnswerText') && document.getElementById('editAnswerText').value) ? document.getElementById('editAnswerText').value : null,
        priority: parseInt(document.getElementById('editPriority').value),
        status: document.getElementById('editStatus').value,
        product_line: document.getElementById('editProductLine').value,
        effective_from: document.getElementById('editEffectiveFrom').value,
        effective_to: document.getElementById('editEffectiveTo').value || null,
        remarks: document.getElementById('editRemarks').value || null
    };
    
    try {
        // Skybanking fees use a dedicated API and a different schema.
        // The Skybanking tab reuses this modal, so we must route saves to /api/skybanking-fees.
        if (formData.product_line === 'SKYBANKING') {
            const networkVal = (formData.card_network || '').trim();
            const skyPayload = {
                effective_from: formData.effective_from || null,
                effective_to: formData.effective_to || null,
                charge_type: formData.charge_type || null,
                // Treat "ANY" as unset for Skybanking network.
                network: (!networkVal || networkVal.toUpperCase() === 'ANY') ? null : networkVal,
                product: formData.card_product || null,
                product_name: formData.full_card_name || formData.card_product || null,
                fee_amount: (Number.isFinite(formData.fee_value) ? formData.fee_value : null),
                fee_unit: formData.fee_unit || null,
                fee_basis: formData.fee_basis || null,
                is_conditional: formData.condition_type && formData.condition_type !== 'NONE',
                answer_text: formData.answer_text || null,
                status: formData.status || null,
                remarks: formData.remarks || null
            };

            if (feeId) {
                await apiCall(`/api/skybanking-fees/${feeId}`, {
                    method: 'PUT',
                    body: JSON.stringify(skyPayload)
                });
                showSuccess('Skybanking fee updated successfully!');
            } else {
                await apiCall('/api/skybanking-fees', {
                    method: 'POST',
                    body: JSON.stringify(skyPayload)
                });
                showSuccess('Skybanking fee created successfully!');
            }
        } else {
            if (feeId) {
                // Update existing card-fee rule
                await apiCall(`/api/rules/${feeId}`, {
                    method: 'PUT',
                    body: JSON.stringify(formData)
                });
                showSuccess('Rule updated successfully!');
            } else {
                // Create new card-fee rule
                await apiCall('/api/rules', {
                    method: 'POST',
                    body: JSON.stringify(formData)
                });
                showSuccess('Rule created successfully!');
            }
        }
        
        closeEditModal();
        if (formData.product_line === 'SKYBANKING') {
            loadSkybankingFees();
        } else {
            loadRules();
        }
    } catch (error) {
        const conflictId = error && error.status === 409 && error.data && error.data.existing_charge_id
            ? error.data.existing_charge_id
            : null;
        if (conflictId) {
            errorDiv.textContent = `Error: ${error.message} (Existing ID: ${conflictId})`;
            errorDiv.classList.add('show');
            const shouldOpen = confirm('A matching charge already exists. Open it for editing?');
            if (shouldOpen) {
                await editRetailCharge(conflictId);
            }
            return;
        }
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
    const editBranchModal = document.getElementById('editBranchModal');
    const editMachineModal = document.getElementById('editMachineModal');
    const editPriorityModal = document.getElementById('editPriorityModal');
    
    if (event.target === loginModal) {
        // Don't close login modal on outside click
    }
    if (event.target === editModal) {
        closeEditModal();
    }
    if (event.target === editBranchModal) {
        closeEditBranchModal();
    }
    if (event.target === editMachineModal) {
        closeEditMachineModal();
    }
    if (event.target === editPriorityModal) {
        closeEditPriorityModal();
    }
    const editRetailModal = document.getElementById('editRetailModal');
    if (event.target === editRetailModal) {
        closeEditRetailModal();
    }
}

// Retail Asset Charges Functions
async function loadRetailAssetFilters() {
    try {
        retailFiltersData = await apiCall('/api/retail-asset-filters');
        
        populateSelect('retailFilterLoanProduct', retailFiltersData.loan_products);
        populateSelect('retailFilterChargeType', retailFiltersData.charge_types);
        populateSelect('editRetailLoanProduct', retailFiltersData.loan_products);
        populateSelect('editRetailChargeType', retailFiltersData.charge_types);
    } catch (error) {
        console.error('Error loading retail asset filters:', error);
    }
}

async function loadRetailAssetCharges() {
    const tbody = document.getElementById('retailChargesTableBody');
    tbody.innerHTML = '<tr><td colspan="10" class="loading">Loading...</td></tr>';
    
    try {
        const params = new URLSearchParams({
            limit: retailPageSize,
            offset: retailCurrentPage * retailPageSize,
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
        tbody.innerHTML = `<tr><td colspan="10" class="loading" style="color: red;">Error: ${error.message}</td></tr>`;
    }
}

function renderRetailCharges(charges) {
    const tbody = document.getElementById('retailChargesTableBody');
    
    if (charges.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="loading">No charges found</td></tr>';
        return;
    }
    
    tbody.innerHTML = charges.map((charge, index) => {
        let feeDisplay = '-';
        if (charge.answer_text) {
            feeDisplay = charge.answer_text;
        } else if (charge.fee_text) {
            feeDisplay = charge.fee_text;
        } else if (charge.tier_1_fee_value) {
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
            feeDisplay = charge.original_charge_text;
        }
        
        return `
            <tr data-row-id="${index}">
                <td data-col="expand" class="expandCol">
                    <button class="expandBtn" onclick="toggleRowExpand(${index})" title="Expand/Collapse">▼</button>
                </td>
                <td data-col="actions" class="actionsCell">
                    <div class="actionsWrap">
                        <button class="btn btn-primary btn-small" onclick="editRetailCharge('${charge.charge_id}')">Edit</button>
                        <button class="btn btn-danger btn-small" onclick="deleteRetailCharge('${charge.charge_id}')">Delete</button>
                    </div>
                </td>
                <td data-col="loanProduct" title="${charge.loan_product_name}">
                    <span class="cellText clamp">${charge.loan_product_name}</span>
                </td>
                <td data-col="chargeType" title="${charge.charge_type}">
                    <span class="cellText">${charge.charge_type}</span>
                </td>
                <td data-col="chargeContext" title="${charge.charge_context || '-'}">
                    <span class="cellText">${charge.charge_context || '-'}</span>
                </td>
                <td data-col="description" title="${charge.charge_description}">
                    <span class="cellText clamp">${charge.charge_description}</span>
                </td>
                <td data-col="feeValue" title="${feeDisplay}">
                    <span class="cellText clamp">${feeDisplay}</span>
                </td>
                <td data-col="unit" title="${charge.fee_unit}">
                    <span class="cellText">${charge.fee_unit}</span>
                </td>
                <td data-col="effectiveFrom" title="${charge.effective_from}">
                    <span class="cellText">${charge.effective_from}</span>
                </td>
                <td data-col="status">
                    <span class="status-badge status-${charge.status.toLowerCase()}">${charge.status}</span>
                </td>
            </tr>
        `;
    }).join('');
    
    // After rendering, apply column widths
    if (window.gridCharges) {
        window.gridCharges.applyWidths();
    }
}

// Toggle row expansion
function toggleRowExpand(rowIndex) {
    const row = document.querySelector(`tr[data-row-id="${rowIndex}"]`);
    const btn = row.querySelector('.expandBtn');
    
    if (row.classList.contains('expanded')) {
        row.classList.remove('expanded');
        btn.textContent = '▼';
        btn.classList.remove('expanded');
    } else {
        row.classList.add('expanded');
        btn.textContent = '▲';
        btn.classList.add('expanded');
    }
}

function updateRetailPagination() {
    const prevBtn = document.getElementById('retailPrevPage');
    const nextBtn = document.getElementById('retailNextPage');
    const pageInfo = document.getElementById('retailPageInfo');
    
    prevBtn.disabled = retailCurrentPage === 0;
    nextBtn.disabled = (retailCurrentPage + 1) * retailPageSize >= retailTotalCharges;
    
    const start = retailCurrentPage * retailPageSize + 1;
    const end = Math.min((retailCurrentPage + 1) * retailPageSize, retailTotalCharges);
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
        populateRetailEditForm(charge);
        const editRetailForm = document.getElementById('editRetailForm');
        if (editRetailForm) {
            editRetailForm.dataset.mode = 'edit';
        }
        const modal = document.getElementById('editRetailModal');
        const title = modal ? modal.querySelector('.modal-header h2') : null;
        if (title) title.textContent = 'Edit Retail Asset Charge';
        document.getElementById('editRetailModal').style.display = 'block';
    } catch (error) {
        showError('Failed to load charge: ' + error.message);
    }
}

function resetRetailEditForm() {
    const fields = [
        'editRetailChargeId',
        'editRetailLoanProduct',
        'editRetailLoanProductName',
        'editRetailChargeType',
        'editRetailChargeContext',
        'editRetailChargeTitle',
        'editRetailChargeDescription',
        'editRetailFeeText',
        'editRetailAnswerText',
        'editRetailParseStatus',
        'editRetailAnswerSource',
        'editRetailFeeValue',
        'editRetailMinFeeValue',
        'editRetailMinFeeUnit',
        'editRetailMaxFeeValue',
        'editRetailMaxFeeUnit',
        'editRetailConditionType',
        'editRetailConditionDescription',
        'editRetailOriginalChargeText',
        'editRetailTier1Threshold',
        'editRetailTier1FeeValue',
        'editRetailTier1FeeUnit',
        'editRetailTier1MaxFee',
        'editRetailTier2Threshold',
        'editRetailTier2FeeValue',
        'editRetailTier2FeeUnit',
        'editRetailTier2MaxFee',
        'editRetailEmployeeFeeValue',
        'editRetailEmployeeFeeUnit',
        'editRetailEmployeeFeeDescription',
        'editRetailFeeRateValue',
        'editRetailFeeRateUnit',
        'editRetailFeeAmountValue',
        'editRetailFeeAmountCurrency',
        'editRetailFeePeriod',
        'editRetailFeeAppliesTo',
        'editRetailFeeUnit',
        'editRetailFeeBasis',
        'editRetailStatus',
        'editRetailPriority',
        'editRetailRemarks',
        'editRetailEffectiveFrom',
        'editRetailEffectiveTo'
    ];
    fields.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.tagName === 'SELECT') {
            el.selectedIndex = 0;
        } else {
            el.value = '';
        }
    });

    // Safe defaults for required selects
    const feeUnitEl = document.getElementById('editRetailFeeUnit');
    if (feeUnitEl) feeUnitEl.value = 'BDT';
    const feeBasisEl = document.getElementById('editRetailFeeBasis');
    if (feeBasisEl) feeBasisEl.value = 'PER_AMOUNT';
    const statusEl = document.getElementById('editRetailStatus');
    if (statusEl) statusEl.value = 'ACTIVE';
    const parseStatusEl = document.getElementById('editRetailParseStatus');
    if (parseStatusEl) parseStatusEl.value = 'UNPARSED';
    const answerSourceEl = document.getElementById('editRetailAnswerSource');
    if (answerSourceEl) answerSourceEl.value = '';
    const conditionTypeEl = document.getElementById('editRetailConditionType');
    if (conditionTypeEl) conditionTypeEl.value = 'NONE';
    const priorityEl = document.getElementById('editRetailPriority');
    if (priorityEl) priorityEl.value = 100;

    const errorDiv = document.getElementById('editRetailError');
    if (errorDiv) {
        errorDiv.textContent = '';
        errorDiv.classList.remove('show');
    }

    const toggleAdvanced = document.getElementById('toggleRetailAdvanced');
    const advancedFields = document.getElementById('retailAdvancedFields');
    if (toggleAdvanced) toggleAdvanced.checked = false;
    if (advancedFields) advancedFields.style.display = 'none';
}

function toggleRetailAdvancedFields() {
    const toggle = document.getElementById('toggleRetailAdvanced');
    const advanced = document.getElementById('retailAdvancedFields');
    if (!advanced) return;
    advanced.style.display = toggle && toggle.checked ? 'block' : 'none';
}

function populateRetailEditForm(charge) {
    document.getElementById('editRetailChargeId').value = charge.charge_id;
    const loanProductEl = document.getElementById('editRetailLoanProduct');
    if (loanProductEl) {
        const loanProductValue = charge.loan_product || '';
        if (loanProductValue && !Array.from(loanProductEl.options).some(opt => opt.value === loanProductValue)) {
            const opt = document.createElement('option');
            opt.value = loanProductValue;
            opt.textContent = loanProductValue;
            loanProductEl.appendChild(opt);
        }
        loanProductEl.value = loanProductValue;
    }
    document.getElementById('editRetailLoanProductName').value = charge.loan_product_name || '';
    const chargeTypeEl = document.getElementById('editRetailChargeType');
    if (chargeTypeEl) {
        const chargeTypeValue = charge.charge_type || '';
        if (chargeTypeValue && !Array.from(chargeTypeEl.options).some(opt => opt.value === chargeTypeValue)) {
            const opt = document.createElement('option');
            opt.value = chargeTypeValue;
            opt.textContent = chargeTypeValue;
            chargeTypeEl.appendChild(opt);
        }
        chargeTypeEl.value = chargeTypeValue;
    }
    document.getElementById('editRetailChargeContext').value = charge.charge_context || 'GENERAL';
    document.getElementById('editRetailChargeTitle').value = charge.charge_title || '';
    document.getElementById('editRetailChargeDescription').value = charge.charge_description || '';
    const feeTextEl = document.getElementById('editRetailFeeText');
    if (feeTextEl) feeTextEl.value = charge.fee_text || '';
    const answerTextEl = document.getElementById('editRetailAnswerText');
    if (answerTextEl) answerTextEl.value = charge.answer_text || '';
    const parseStatusEl = document.getElementById('editRetailParseStatus');
    if (parseStatusEl) parseStatusEl.value = charge.parse_status || 'UNPARSED';
    const answerSourceEl = document.getElementById('editRetailAnswerSource');
    if (answerSourceEl) answerSourceEl.value = charge.answer_source || '';
    document.getElementById('editRetailFeeValue').value = charge.fee_value || '';
    const minFeeValueEl = document.getElementById('editRetailMinFeeValue');
    if (minFeeValueEl) minFeeValueEl.value = charge.min_fee_value || '';
    const minFeeUnitEl = document.getElementById('editRetailMinFeeUnit');
    if (minFeeUnitEl) minFeeUnitEl.value = charge.min_fee_unit || '';
    const maxFeeValueEl = document.getElementById('editRetailMaxFeeValue');
    if (maxFeeValueEl) maxFeeValueEl.value = charge.max_fee_value || '';
    const maxFeeUnitEl = document.getElementById('editRetailMaxFeeUnit');
    if (maxFeeUnitEl) maxFeeUnitEl.value = charge.max_fee_unit || '';
    const conditionTypeEl = document.getElementById('editRetailConditionType');
    if (conditionTypeEl) conditionTypeEl.value = charge.condition_type || 'NONE';
    const conditionDescEl = document.getElementById('editRetailConditionDescription');
    if (conditionDescEl) conditionDescEl.value = charge.condition_description || '';
    const originalTextEl = document.getElementById('editRetailOriginalChargeText');
    if (originalTextEl) originalTextEl.value = charge.original_charge_text || '';
    const tier1ThresholdEl = document.getElementById('editRetailTier1Threshold');
    if (tier1ThresholdEl) tier1ThresholdEl.value = charge.tier_1_threshold || '';
    const tier1FeeValueEl = document.getElementById('editRetailTier1FeeValue');
    if (tier1FeeValueEl) tier1FeeValueEl.value = charge.tier_1_fee_value || '';
    const tier1FeeUnitEl = document.getElementById('editRetailTier1FeeUnit');
    if (tier1FeeUnitEl) tier1FeeUnitEl.value = charge.tier_1_fee_unit || '';
    const tier1MaxFeeEl = document.getElementById('editRetailTier1MaxFee');
    if (tier1MaxFeeEl) tier1MaxFeeEl.value = charge.tier_1_max_fee || '';
    const tier2ThresholdEl = document.getElementById('editRetailTier2Threshold');
    if (tier2ThresholdEl) tier2ThresholdEl.value = charge.tier_2_threshold || '';
    const tier2FeeValueEl = document.getElementById('editRetailTier2FeeValue');
    if (tier2FeeValueEl) tier2FeeValueEl.value = charge.tier_2_fee_value || '';
    const tier2FeeUnitEl = document.getElementById('editRetailTier2FeeUnit');
    if (tier2FeeUnitEl) tier2FeeUnitEl.value = charge.tier_2_fee_unit || '';
    const tier2MaxFeeEl = document.getElementById('editRetailTier2MaxFee');
    if (tier2MaxFeeEl) tier2MaxFeeEl.value = charge.tier_2_max_fee || '';
    const employeeFeeValueEl = document.getElementById('editRetailEmployeeFeeValue');
    if (employeeFeeValueEl) employeeFeeValueEl.value = charge.employee_fee_value || '';
    const employeeFeeUnitEl = document.getElementById('editRetailEmployeeFeeUnit');
    if (employeeFeeUnitEl) employeeFeeUnitEl.value = charge.employee_fee_unit || '';
    const employeeFeeDescEl = document.getElementById('editRetailEmployeeFeeDescription');
    if (employeeFeeDescEl) employeeFeeDescEl.value = charge.employee_fee_description || '';
    const feeRateValueEl = document.getElementById('editRetailFeeRateValue');
    if (feeRateValueEl) feeRateValueEl.value = charge.fee_rate_value || '';
    const feeRateUnitEl = document.getElementById('editRetailFeeRateUnit');
    if (feeRateUnitEl) feeRateUnitEl.value = charge.fee_rate_unit || '';
    const feeAmountValueEl = document.getElementById('editRetailFeeAmountValue');
    if (feeAmountValueEl) feeAmountValueEl.value = charge.fee_amount_value || '';
    const feeAmountCurrencyEl = document.getElementById('editRetailFeeAmountCurrency');
    if (feeAmountCurrencyEl) feeAmountCurrencyEl.value = charge.fee_amount_currency || '';
    const feePeriodEl = document.getElementById('editRetailFeePeriod');
    if (feePeriodEl) feePeriodEl.value = charge.fee_period || '';
    const feeAppliesToEl = document.getElementById('editRetailFeeAppliesTo');
    if (feeAppliesToEl) feeAppliesToEl.value = charge.fee_applies_to || '';
    document.getElementById('editRetailFeeUnit').value = charge.fee_unit || 'BDT';
    // Retail Asset fee_basis is a strict Postgres enum (PER_AMOUNT, PER_LOAN, etc.).
    // Default to PER_AMOUNT to avoid invalid enum values (e.g., PER_REQUEST/PER_TXN).
    const feeBasisEl = document.getElementById('editRetailFeeBasis');
    if (feeBasisEl) {
        const basis = (charge.fee_basis || 'PER_AMOUNT');
        feeBasisEl.value = basis;
        // If the existing value isn't in the dropdown, force a safe default.
        if (feeBasisEl.value !== basis) {
            feeBasisEl.value = 'PER_AMOUNT';
        }
    }
    document.getElementById('editRetailStatus').value = charge.status || 'ACTIVE';
    document.getElementById('editRetailPriority').value = charge.priority || 100;
    document.getElementById('editRetailRemarks').value = charge.remarks || '';

    // Handle dates
    if (charge.effective_from) {
        const fromDate = charge.effective_from.split('T')[0];
        document.getElementById('editRetailEffectiveFrom').value = fromDate;
    }
    if (charge.effective_to) {
        const toDate = charge.effective_to.split('T')[0];
        document.getElementById('editRetailEffectiveTo').value = toDate;
    }
}

function closeEditRetailModal() {
    document.getElementById('editRetailModal').style.display = 'none';
    document.getElementById('editRetailError').textContent = '';
    document.getElementById('editRetailError').classList.remove('show');
}

async function handleSaveRetailCharge(e) {
    e.preventDefault();
    const errorDiv = document.getElementById('editRetailError');
    errorDiv.textContent = '';
    errorDiv.classList.remove('show');
    
    const chargeId = document.getElementById('editRetailChargeId').value;
    const editRetailForm = document.getElementById('editRetailForm');
    const mode = editRetailForm ? editRetailForm.dataset.mode : null;
    const formData = {
        loan_product: document.getElementById('editRetailLoanProduct').value || null,
        loan_product_name: document.getElementById('editRetailLoanProductName').value || null,
        charge_type: document.getElementById('editRetailChargeType').value || null,
        charge_context: document.getElementById('editRetailChargeContext').value || 'GENERAL',
        charge_title: document.getElementById('editRetailChargeTitle').value || null,
        charge_description: document.getElementById('editRetailChargeDescription').value || null,
        fee_text: (document.getElementById('editRetailFeeText') && document.getElementById('editRetailFeeText').value) ? document.getElementById('editRetailFeeText').value : null,
        answer_text: (document.getElementById('editRetailAnswerText') && document.getElementById('editRetailAnswerText').value) ? document.getElementById('editRetailAnswerText').value : null,
        parse_status: (document.getElementById('editRetailParseStatus') && document.getElementById('editRetailParseStatus').value) ? document.getElementById('editRetailParseStatus').value : null,
        answer_source: (document.getElementById('editRetailAnswerSource') && document.getElementById('editRetailAnswerSource').value) ? document.getElementById('editRetailAnswerSource').value : null,
        fee_value: document.getElementById('editRetailFeeValue').value ? parseFloat(document.getElementById('editRetailFeeValue').value) : null,
        min_fee_value: document.getElementById('editRetailMinFeeValue').value ? parseFloat(document.getElementById('editRetailMinFeeValue').value) : null,
        min_fee_unit: (document.getElementById('editRetailMinFeeUnit') && document.getElementById('editRetailMinFeeUnit').value) ? document.getElementById('editRetailMinFeeUnit').value : null,
        max_fee_value: document.getElementById('editRetailMaxFeeValue').value ? parseFloat(document.getElementById('editRetailMaxFeeValue').value) : null,
        max_fee_unit: (document.getElementById('editRetailMaxFeeUnit') && document.getElementById('editRetailMaxFeeUnit').value) ? document.getElementById('editRetailMaxFeeUnit').value : null,
        condition_type: (document.getElementById('editRetailConditionType') && document.getElementById('editRetailConditionType').value) ? document.getElementById('editRetailConditionType').value : null,
        condition_description: (document.getElementById('editRetailConditionDescription') && document.getElementById('editRetailConditionDescription').value) ? document.getElementById('editRetailConditionDescription').value : null,
        original_charge_text: (document.getElementById('editRetailOriginalChargeText') && document.getElementById('editRetailOriginalChargeText').value) ? document.getElementById('editRetailOriginalChargeText').value : null,
        tier_1_threshold: document.getElementById('editRetailTier1Threshold').value ? parseFloat(document.getElementById('editRetailTier1Threshold').value) : null,
        tier_1_fee_value: document.getElementById('editRetailTier1FeeValue').value ? parseFloat(document.getElementById('editRetailTier1FeeValue').value) : null,
        tier_1_fee_unit: (document.getElementById('editRetailTier1FeeUnit') && document.getElementById('editRetailTier1FeeUnit').value) ? document.getElementById('editRetailTier1FeeUnit').value : null,
        tier_1_max_fee: document.getElementById('editRetailTier1MaxFee').value ? parseFloat(document.getElementById('editRetailTier1MaxFee').value) : null,
        tier_2_threshold: document.getElementById('editRetailTier2Threshold').value ? parseFloat(document.getElementById('editRetailTier2Threshold').value) : null,
        tier_2_fee_value: document.getElementById('editRetailTier2FeeValue').value ? parseFloat(document.getElementById('editRetailTier2FeeValue').value) : null,
        tier_2_fee_unit: (document.getElementById('editRetailTier2FeeUnit') && document.getElementById('editRetailTier2FeeUnit').value) ? document.getElementById('editRetailTier2FeeUnit').value : null,
        tier_2_max_fee: document.getElementById('editRetailTier2MaxFee').value ? parseFloat(document.getElementById('editRetailTier2MaxFee').value) : null,
        employee_fee_value: document.getElementById('editRetailEmployeeFeeValue').value ? parseFloat(document.getElementById('editRetailEmployeeFeeValue').value) : null,
        employee_fee_unit: (document.getElementById('editRetailEmployeeFeeUnit') && document.getElementById('editRetailEmployeeFeeUnit').value) ? document.getElementById('editRetailEmployeeFeeUnit').value : null,
        employee_fee_description: (document.getElementById('editRetailEmployeeFeeDescription') && document.getElementById('editRetailEmployeeFeeDescription').value) ? document.getElementById('editRetailEmployeeFeeDescription').value : null,
        fee_rate_value: (document.getElementById('editRetailFeeRateValue') && document.getElementById('editRetailFeeRateValue').value) ? parseFloat(document.getElementById('editRetailFeeRateValue').value) : null,
        fee_rate_unit: (document.getElementById('editRetailFeeRateUnit') && document.getElementById('editRetailFeeRateUnit').value) ? document.getElementById('editRetailFeeRateUnit').value : null,
        fee_amount_value: (document.getElementById('editRetailFeeAmountValue') && document.getElementById('editRetailFeeAmountValue').value) ? parseFloat(document.getElementById('editRetailFeeAmountValue').value) : null,
        fee_amount_currency: (document.getElementById('editRetailFeeAmountCurrency') && document.getElementById('editRetailFeeAmountCurrency').value) ? document.getElementById('editRetailFeeAmountCurrency').value : null,
        fee_period: (document.getElementById('editRetailFeePeriod') && document.getElementById('editRetailFeePeriod').value) ? document.getElementById('editRetailFeePeriod').value : null,
        fee_applies_to: (document.getElementById('editRetailFeeAppliesTo') && document.getElementById('editRetailFeeAppliesTo').value) ? document.getElementById('editRetailFeeAppliesTo').value : null,
        fee_unit: document.getElementById('editRetailFeeUnit').value || null,
        fee_basis: document.getElementById('editRetailFeeBasis').value || null,
        status: document.getElementById('editRetailStatus').value || null,
        priority: document.getElementById('editRetailPriority').value ? parseInt(document.getElementById('editRetailPriority').value) : null,
        effective_from: document.getElementById('editRetailEffectiveFrom').value || null,
        effective_to: document.getElementById('editRetailEffectiveTo').value || null,
        remarks: document.getElementById('editRetailRemarks').value || null
    };
    
    try {
        if (!chargeId || mode === 'create') {
            await apiCall('/api/retail-asset-charges', {
                method: 'POST',
                body: JSON.stringify(formData)
            });
            showSuccess('Retail asset charge created successfully!');
        } else {
            await apiCall(`/api/retail-asset-charges/${chargeId}`, {
                method: 'PUT',
                body: JSON.stringify(formData)
            });
            showSuccess('Retail asset charge updated successfully!');
        }
        closeEditRetailModal();
        loadRetailAssetCharges();
    } catch (error) {
        errorDiv.textContent = 'Error: ' + error.message;
        errorDiv.classList.add('show');
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
    resetRetailEditForm();
    const editRetailForm = document.getElementById('editRetailForm');
    if (editRetailForm) {
        editRetailForm.dataset.mode = 'create';
    }
    document.getElementById('editRetailChargeId').value = '';

    const modal = document.getElementById('editRetailModal');
    const title = modal ? modal.querySelector('.modal-header h2') : null;
    if (title) title.textContent = 'Add Retail Asset Charge';
    if (modal) modal.style.display = 'block';
}

// Skybanking Fees Functions
async function loadSkybankingFilters() {
    try {
        skybankingFiltersData = await apiCall('/api/filters');
        
        // Populate skybanking filter dropdowns
        const chargeTypeSelect = document.getElementById('skybankingFilterChargeType');
        const productSelect = document.getElementById('skybankingFilterProduct');
        const networkSelect = document.getElementById('skybankingFilterNetwork');
        
        if (chargeTypeSelect && skybankingFiltersData.charge_types) {
            populateSelect('skybankingFilterChargeType', skybankingFiltersData.charge_types);
        }
        if (productSelect && skybankingFiltersData.card_products) {
            populateSelect('skybankingFilterProduct', skybankingFiltersData.card_products);
        }
        if (networkSelect && skybankingFiltersData.card_networks) {
            populateSelect('skybankingFilterNetwork', skybankingFiltersData.card_networks);
        }
    } catch (error) {
        console.error('Error loading skybanking filters:', error);
    }
}

async function loadSkybankingFees() {
    const tbody = document.getElementById('skybankingFeesTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="10" class="loading">Loading...</td></tr>';
    
    try {
        // Use the dedicated Skybanking fees endpoint
        const params = new URLSearchParams({
            page: skybankingCurrentPage,
            page_size: pageSize
        });
        
        // Add filter parameters (note: parameter names are different for skybanking endpoint)
        if (skybankingCurrentFilters.charge_type) {
            params.append('charge_type', skybankingCurrentFilters.charge_type);
        }
        if (skybankingCurrentFilters.card_product) {
            params.append('product', skybankingCurrentFilters.card_product);
        }
        if (skybankingCurrentFilters.card_network) {
            params.append('network', skybankingCurrentFilters.card_network);
        }
        if (skybankingCurrentFilters.status_filter) {
            params.append('status', skybankingCurrentFilters.status_filter);
        }
        
        const data = await apiCall(`/api/skybanking-fees?${params.toString()}`);
        skybankingTotalFees = data.total || 0;
        
        // Convert the response format to match what renderSkybankingFees expects
        // The API returns items with different field names, so we need to map them
        const fees = (data.items || []).map(item => ({
            fee_id: item.fee_id,
            charge_type: item.charge_type,
            card_product: item.product || item.product_name,
            card_network: item.network,
            fee_value: item.fee_amount,
            fee_unit: item.fee_unit,
            fee_basis: item.fee_basis,
            condition_type: item.is_conditional ? 'CONDITIONAL' : 'NONE',
            status: item.status,
            effective_from: item.effective_from ? item.effective_from.split('T')[0] : ''
        }));
        
        updateSkybankingPagination();
        renderSkybankingFees(fees);
        
        const totalCountEl = document.getElementById('skybankingTotalCount');
        const showingCountEl = document.getElementById('skybankingShowingCount');
        if (totalCountEl) totalCountEl.textContent = `Total: ${skybankingTotalFees}`;
        if (showingCountEl) showingCountEl.textContent = `Showing: ${fees.length}`;
    } catch (error) {
        console.error('Error loading skybanking fees:', error);
        tbody.innerHTML = `<tr><td colspan="10" class="loading" style="color: red;">Error: ${error.message}</td></tr>`;
    }
}

function renderSkybankingFees(fees) {
    const tbody = document.getElementById('skybankingFeesTableBody');
    if (!tbody) return;
    
    if (fees.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="loading">No fees found</td></tr>';
        return;
    }
    
    tbody.innerHTML = fees.map(fee => `
        <tr>
            <td>${fee.charge_type}</td>
            <td>${fee.card_product || '-'}</td>
            <td>${fee.card_network || '-'}</td>
            <td>${formatNumber(fee.fee_value)}</td>
            <td>${fee.fee_unit}</td>
            <td>${fee.fee_basis}</td>
            <td>${fee.condition_type !== 'NONE' ? 'Yes' : 'No'}</td>
            <td><span class="status-badge status-${fee.status.toLowerCase()}">${fee.status}</span></td>
            <td>${fee.effective_from}</td>
            <td class="actions-cell">
                <button class="btn btn-primary btn-small" onclick="editSkybankingFee('${fee.fee_id}')">Edit</button>
                <button class="btn btn-danger btn-small" onclick="deleteSkybankingFee('${fee.fee_id}')">Delete</button>
            </td>
        </tr>
    `).join('');
}

function updateSkybankingPagination() {
    const prevBtn = document.getElementById('skybankingPrevPage');
    const nextBtn = document.getElementById('skybankingNextPage');
    const pageInfo = document.getElementById('skybankingPageInfo');
    
    if (prevBtn) prevBtn.disabled = skybankingCurrentPage === 0;
    if (nextBtn) nextBtn.disabled = (skybankingCurrentPage + 1) * pageSize >= skybankingTotalFees;
    
    if (pageInfo) {
        const start = skybankingCurrentPage * pageSize + 1;
        const end = Math.min((skybankingCurrentPage + 1) * pageSize, skybankingTotalFees);
        pageInfo.textContent = `Page ${skybankingCurrentPage + 1} (${start}-${end} of ${skybankingTotalFees})`;
    }
}

// Edit Skybanking Fee
async function editSkybankingFee(feeId) {
    try {
        const fee = await apiCall(`/api/skybanking-fees/${feeId}`);
        // Convert Skybanking fee format to match the edit form structure
        // Note: Skybanking fees use a different structure, so we'll use the same modal but populate differently
        const ruleData = {
            fee_id: fee.fee_id,
            charge_type: fee.charge_type,
            card_category: 'ANY', // Skybanking doesn't use card categories
            card_network: fee.network || 'ANY',
            card_product: fee.product,
            full_card_name: fee.product_name,
            fee_value: fee.fee_amount || 0,
            fee_unit: fee.fee_unit,
            fee_basis: fee.fee_basis,
            min_fee_value: null,
            min_fee_unit: null,
            max_fee_value: null,
            free_entitlement_count: null,
            condition_type: fee.is_conditional ? 'CONDITIONAL' : 'NONE',
            note_reference: null,
            answer_text: fee.answer_text || null,
            priority: 100,
            status: fee.status,
            product_line: 'SKYBANKING',
            effective_from: fee.effective_from ? fee.effective_from.split('T')[0] : '',
            effective_to: fee.effective_to ? fee.effective_to.split('T')[0] : '',
            remarks: fee.remarks || ''
        };
        populateEditForm(ruleData);
        document.getElementById('editModal').style.display = 'block';
        document.getElementById('modalTitle').textContent = 'Edit Skybanking Fee';
    } catch (error) {
        showError('Failed to load Skybanking fee: ' + error.message);
    }
}

// Delete Skybanking Fee
async function deleteSkybankingFee(feeId) {
    if (!confirm('Are you sure you want to delete this Skybanking fee? It will be marked as INACTIVE.')) {
        return;
    }
    
    try {
        await apiCall(`/api/skybanking-fees/${feeId}`, {
            method: 'DELETE'
        });
        showSuccess('Skybanking fee deleted successfully!');
        loadSkybankingFees();
    } catch (error) {
        showError('Error deleting Skybanking fee: ' + error.message);
    }
}

function applySkybankingFilters() {
    skybankingCurrentFilters = {};
    
    const chargeType = document.getElementById('skybankingFilterChargeType');
    const product = document.getElementById('skybankingFilterProduct');
    const network = document.getElementById('skybankingFilterNetwork');
    const statusFilter = document.getElementById('skybankingFilterStatus');
    
    if (chargeType && chargeType.value) skybankingCurrentFilters.charge_type = chargeType.value;
    if (product && product.value) skybankingCurrentFilters.card_product = product.value;
    if (network && network.value) skybankingCurrentFilters.card_network = network.value;
    if (statusFilter && statusFilter.value) skybankingCurrentFilters.status_filter = statusFilter.value;
    
    skybankingCurrentPage = 0;
    loadSkybankingFees();
}

function clearSkybankingFilters() {
    const chargeType = document.getElementById('skybankingFilterChargeType');
    const product = document.getElementById('skybankingFilterProduct');
    const network = document.getElementById('skybankingFilterNetwork');
    const statusFilter = document.getElementById('skybankingFilterStatus');
    
    if (chargeType) chargeType.value = '';
    if (product) product.value = '';
    if (network) network.value = '';
    if (statusFilter) statusFilter.value = '';
    
    skybankingCurrentFilters = {};
    skybankingCurrentPage = 0;
    loadSkybankingFees();
}

function showAddSkybankingModal() {
    // Clear form
    document.getElementById('editForm').reset();
    document.getElementById('editFeeId').value = '';
    
    // Set defaults for Skybanking
    document.getElementById('editCardCategory').value = 'ANY';
    document.getElementById('editFeeUnit').value = 'BDT';
    document.getElementById('editFeeBasis').value = 'PER_TXN';
    document.getElementById('editConditionType').value = 'NONE';
    document.getElementById('editPriority').value = '100';
    document.getElementById('editStatus').value = 'ACTIVE';
    document.getElementById('editProductLine').value = 'SKYBANKING';
    document.getElementById('editEffectiveFrom').value = new Date().toISOString().split('T')[0];
    
    document.getElementById('editModal').style.display = 'block';
    document.getElementById('modalTitle').textContent = 'Add New Skybanking Fee';
}

// Location Service Functions
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
            tbody.innerHTML = '<tr><td colspan="8" class="no-data">No branches found</td></tr>';
        } else {
            data.locations.forEach(loc => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${loc.code || ''}</td>
                    <td>${loc.name}</td>
                    <td>${loc.address.street}</td>
                    <td>${loc.address.area || ''}</td>
                    <td>${loc.address.city}</td>
                    <td>${loc.address.region}</td>
                    <td>${loc.status || ''}</td>
                    <td class="actions-cell">
                        <button class="btn btn-primary btn-small" onclick="editBranch('${loc.id}')">Edit</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }
 
        document.getElementById('branchPrevPage').disabled = branchCurrentPage === 0;
        document.getElementById('branchNextPage').disabled = (branchCurrentPage + 1) * pageSize >= branchTotalLocations;
    } catch (error) {
        console.error('Error loading branches:', error);
        const tbody = document.getElementById('branchesTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="error">Error loading branches</td></tr>';
    }
}

async function loadMachines() {
    try {
        // If no specific type filter, we need to get all machine types
        // The backend requires a type parameter (atm, crm, rtdm) to return machines
        // So if no type is specified, we'll make separate calls for each machine type and combine them
        let allMachines = [];
        let totalMachines = 0;
        
        if (machineCurrentFilters.type) {
            // Single type filter - make one API call
            const params = new URLSearchParams({
                type: machineCurrentFilters.type,
                limit: pageSize,
                offset: machineCurrentPage * pageSize
            });
            if (machineCurrentFilters.city) params.append('city', machineCurrentFilters.city);
            if (machineCurrentFilters.region) params.append('region', machineCurrentFilters.region);
            if (machineCurrentFilters.search) params.append('search', machineCurrentFilters.search);
            
            const data = await apiCall(`/api/locations?${params.toString()}`);
            allMachines = data.locations || [];
            totalMachines = data.total || 0;
        } else {
            // No type filter - get all machine types by making separate calls for each type
            // This ensures we get all machines regardless of how many branches/priority centers exist
            const machineTypes = ['atm', 'crm', 'rtdm'];
            const allMachinesPromises = machineTypes.map(async (type) => {
                const params = new URLSearchParams({
                    type: type,
                    limit: 1000, // Get all machines of this type
                    offset: 0
                });
                if (machineCurrentFilters.city) params.append('city', machineCurrentFilters.city);
                if (machineCurrentFilters.region) params.append('region', machineCurrentFilters.region);
                if (machineCurrentFilters.search) params.append('search', machineCurrentFilters.search);
                
                const data = await apiCall(`/api/locations?${params.toString()}`);
                return data.locations || [];
            });
            
            const results = await Promise.all(allMachinesPromises);
            allMachines = results.flat(); // Combine all machine types into one array
            totalMachines = allMachines.length;
            
            // Apply pagination to combined results
            const startIdx = machineCurrentPage * pageSize;
            const endIdx = startIdx + pageSize;
            allMachines = allMachines.slice(startIdx, endIdx);
        }
        
        const data = { locations: allMachines, total: totalMachines };
        machineTotalLocations = totalMachines;
        document.getElementById('machineTotalCount').textContent = `Total: ${machineTotalLocations}`;
        document.getElementById('machineShowingCount').textContent = `Showing: ${data.locations.length}`;
        document.getElementById('machinePageInfo').textContent = `Page ${machineCurrentPage + 1}`;
        
        const tbody = document.getElementById('machinesTableBody');
        tbody.innerHTML = '';
        
        if (data.locations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="no-data">No machines found</td></tr>';
        } else {
            data.locations.forEach(loc => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${loc.machine_type || loc.type.toUpperCase()}</td>
                    <td>${loc.machine_count || 1}</td>
                    <td>${loc.address.street}</td>
                    <td>${loc.address.area || ''}</td>
                    <td>${loc.address.city}</td>
                    <td>${loc.address.region}</td>
                    <td class="actions-cell">
                        <button class="btn btn-primary btn-small" onclick="editMachine('${loc.id}')">Edit</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }
 
        document.getElementById('machinePrevPage').disabled = machineCurrentPage === 0;
        document.getElementById('machineNextPage').disabled = (machineCurrentPage + 1) * pageSize >= machineTotalLocations;
    } catch (error) {
        console.error('Error loading machines:', error);
        const tbody = document.getElementById('machinesTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="error">Error loading machines</td></tr>';
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
            tbody.innerHTML = '<tr><td colspan="4" class="no-data">No priority centers found</td></tr>';
        } else {
            data.locations.forEach(loc => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${loc.name}</td>
                    <td>${loc.address.city}</td>
                    <td>${loc.address.region}</td>
                    <td class="actions-cell">
                        <button class="btn btn-primary btn-small" onclick="editPriorityCenter('${loc.id}')">Edit</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }
 
        document.getElementById('priorityPrevPage').disabled = priorityCurrentPage === 0;
        document.getElementById('priorityNextPage').disabled = (priorityCurrentPage + 1) * pageSize >= priorityTotalLocations;
    } catch (error) {
        console.error('Error loading priority centers:', error);
        const tbody = document.getElementById('priorityCentersTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="error">Error loading priority centers</td></tr>';
    }
}

// ===== POIs / LANDMARKS =====
async function loadPois() {
    try {
        const params = new URLSearchParams({
            limit: pageSize,
            offset: poiCurrentPage * pageSize
        });
        if (poiCurrentFilters.search) params.append('search', poiCurrentFilters.search);
        if (poiCurrentFilters.area) params.append('area', poiCurrentFilters.area);
        if (poiCurrentFilters.city) params.append('city', poiCurrentFilters.city);

        const data = await apiCall(`/api/poi-landmarks?${params.toString()}`);
        poiTotal = data.total || 0;
        document.getElementById('poiTotalCount').textContent = `Total: ${poiTotal}`;
        document.getElementById('poiShowingCount').textContent = `Showing: ${(data.items || []).length}`;
        document.getElementById('poiPageInfo').textContent = `Page ${poiCurrentPage + 1}`;

        const tbody = document.getElementById('poisTableBody');
        tbody.innerHTML = '';

        const items = data.items || [];
        if (items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="no-data">No POIs found</td></tr>';
        } else {
            items.forEach(poi => {
                const aliases = Array.isArray(poi.aliases) ? poi.aliases.join(', ') : (poi.aliases || '');
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${poi.name || ''}</td>
                    <td>${aliases}</td>
                    <td>${poi.area || ''}</td>
                    <td>${poi.city || ''}</td>
                    <td>${poi.region || ''}</td>
                    <td>${poi.latitude ?? ''}</td>
                    <td>${poi.longitude ?? ''}</td>
                    <td class="actions-cell">
                        <button class="btn btn-primary btn-small" onclick="editPoi('${poi.id}')">Edit</button>
                        <button class="btn btn-danger btn-small" onclick="deletePoi('${poi.id}')">Delete</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        }

        const prevBtn = document.getElementById('poiPrevPage');
        const nextBtn = document.getElementById('poiNextPage');
        if (prevBtn) prevBtn.disabled = poiCurrentPage === 0;
        if (nextBtn) nextBtn.disabled = (poiCurrentPage + 1) * pageSize >= poiTotal;
    } catch (error) {
        console.error('Error loading POIs:', error);
        const tbody = document.getElementById('poisTableBody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="8" class="error">Error loading POIs</td></tr>';
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

// POI Filters
function applyPoiFilters() {
    poiCurrentFilters = {};
    const search = document.getElementById('poiFilterSearch')?.value;
    const area = document.getElementById('poiFilterArea')?.value;
    const city = document.getElementById('poiFilterCity')?.value;
    if (search) poiCurrentFilters.search = search;
    if (area) poiCurrentFilters.area = area;
    if (city) poiCurrentFilters.city = city;
    poiCurrentPage = 0;
    loadPois();
}

function clearPoiFilters() {
    const s = document.getElementById('poiFilterSearch');
    const a = document.getElementById('poiFilterArea');
    const c = document.getElementById('poiFilterCity');
    if (s) s.value = '';
    if (a) a.value = '';
    if (c) c.value = '';
    poiCurrentFilters = {};
    poiCurrentPage = 0;
    loadPois();
}

// Edit Branch Functions
async function editBranch(branchId) {
    try {
        const branch = await apiCall(`/api/locations/branches/${branchId}`);
        populateBranchEditForm(branch);
        document.getElementById('editBranchModal').style.display = 'block';
    } catch (error) {
        showError('Failed to load branch: ' + error.message);
    }
}

function populateBranchEditForm(branch) {
    document.getElementById('editBranchId').value = branch.id;
    document.getElementById('editBranchCode').value = branch.code || '';
    document.getElementById('editBranchName').value = branch.name || '';
    document.getElementById('editBranchStreet').value = branch.address.street || '';
    document.getElementById('editBranchArea').value = branch.address.area || '';
    document.getElementById('editBranchLatitude').value = branch.address.latitude ?? '';
    document.getElementById('editBranchLongitude').value = branch.address.longitude ?? '';
    document.getElementById('editBranchZipCode').value = branch.address.zip_code || '';
    document.getElementById('editBranchStatus').value = branch.status || 'ACTIVE';
    document.getElementById('editBranchIsHeadOffice').checked = branch.is_head_office || false;
    
    // Populate city and region dropdowns if not already populated
    const citySelect = document.getElementById('editBranchCity');
    const regionSelect = document.getElementById('editBranchRegion');
    
    if (locationFiltersData) {
        if (citySelect.options.length <= 1) {
            locationFiltersData.cities.forEach(city => {
                const option = document.createElement('option');
                option.value = city;
                option.textContent = city;
                citySelect.appendChild(option);
            });
        }
        if (regionSelect.options.length <= 1) {
            locationFiltersData.regions.forEach(region => {
                const option = document.createElement('option');
                option.value = region;
                option.textContent = region;
                regionSelect.appendChild(option);
            });
        }
    }
    
    // Set selected values
    citySelect.value = branch.address.city || '';
    regionSelect.value = branch.address.region || '';
}

function closeEditBranchModal() {
    document.getElementById('editBranchModal').style.display = 'none';
    document.getElementById('editBranchError').textContent = '';
    document.getElementById('editBranchError').classList.remove('show');
}

async function handleSaveBranch(e) {
    e.preventDefault();
    const errorDiv = document.getElementById('editBranchError');
    errorDiv.textContent = '';
    errorDiv.classList.remove('show');
    
    const branchId = document.getElementById('editBranchId').value;
    const latRaw = document.getElementById('editBranchLatitude')?.value;
    const lonRaw = document.getElementById('editBranchLongitude')?.value;
    const formData = {
        branch_code: document.getElementById('editBranchCode').value || null,
        branch_name: document.getElementById('editBranchName').value || null,
        street_address: document.getElementById('editBranchStreet').value || null,
        area: document.getElementById('editBranchArea').value || null,
        latitude: latRaw ? parseFloat(latRaw) : null,
        longitude: lonRaw ? parseFloat(lonRaw) : null,
        city: document.getElementById('editBranchCity').value || null,
        region: document.getElementById('editBranchRegion').value || null,
        zip_code: document.getElementById('editBranchZipCode').value || null,
        status: document.getElementById('editBranchStatus').value || null,
        is_head_office: document.getElementById('editBranchIsHeadOffice').checked
    };
    
    try {
        await apiCall(`/api/locations/branches/${branchId}`, {
            method: 'PUT',
            body: JSON.stringify(formData)
        });
        showSuccess('Branch updated successfully!');
        closeEditBranchModal();
        loadBranches();
    } catch (error) {
        errorDiv.textContent = 'Error: ' + error.message;
        errorDiv.classList.add('show');
    }
}

// Edit Machine Functions
async function editMachine(machineId) {
    try {
        const machine = await apiCall(`/api/locations/machines/${machineId}`);
        populateMachineEditForm(machine);
        document.getElementById('editMachineModal').style.display = 'block';
    } catch (error) {
        showError('Failed to load machine: ' + error.message);
    }
}

function populateMachineEditForm(machine) {
    document.getElementById('editMachineId').value = machine.id;
    document.getElementById('editMachineType').value = (machine.machine_type || machine.type || 'ATM').toUpperCase();
    document.getElementById('editMachineCount').value = machine.machine_count || 1;
    document.getElementById('editMachineStreet').value = machine.address.street || '';
    document.getElementById('editMachineArea').value = machine.address.area || '';
    document.getElementById('editMachineLatitude').value = machine.address.latitude ?? '';
    document.getElementById('editMachineLongitude').value = machine.address.longitude ?? '';
    document.getElementById('editMachineZipCode').value = machine.address.zip_code || '';
    
    // Populate city and region dropdowns if not already populated
    const citySelect = document.getElementById('editMachineCity');
    const regionSelect = document.getElementById('editMachineRegion');
    
    if (locationFiltersData) {
        if (citySelect.options.length <= 1) {
            locationFiltersData.cities.forEach(city => {
                const option = document.createElement('option');
                option.value = city;
                option.textContent = city;
                citySelect.appendChild(option);
            });
        }
        if (regionSelect.options.length <= 1) {
            locationFiltersData.regions.forEach(region => {
                const option = document.createElement('option');
                option.value = region;
                option.textContent = region;
                regionSelect.appendChild(option);
            });
        }
    }
    
    // Set selected values
    citySelect.value = machine.address.city || '';
    regionSelect.value = machine.address.region || '';
}

function closeEditMachineModal() {
    document.getElementById('editMachineModal').style.display = 'none';
    document.getElementById('editMachineError').textContent = '';
    document.getElementById('editMachineError').classList.remove('show');
}

async function handleSaveMachine(e) {
    e.preventDefault();
    const errorDiv = document.getElementById('editMachineError');
    errorDiv.textContent = '';
    errorDiv.classList.remove('show');
    
    const machineId = document.getElementById('editMachineId').value;
    const latRaw = document.getElementById('editMachineLatitude')?.value;
    const lonRaw = document.getElementById('editMachineLongitude')?.value;
    const formData = {
        machine_type: document.getElementById('editMachineType').value || null,
        machine_count: parseInt(document.getElementById('editMachineCount').value) || null,
        street_address: document.getElementById('editMachineStreet').value || null,
        area: document.getElementById('editMachineArea').value || null,
        latitude: latRaw ? parseFloat(latRaw) : null,
        longitude: lonRaw ? parseFloat(lonRaw) : null,
        city: document.getElementById('editMachineCity').value || null,
        region: document.getElementById('editMachineRegion').value || null,
        zip_code: document.getElementById('editMachineZipCode').value || null
    };
    
    try {
        await apiCall(`/api/locations/machines/${machineId}`, {
            method: 'PUT',
            body: JSON.stringify(formData)
        });
        showSuccess('Machine updated successfully!');
        closeEditMachineModal();
        loadMachines();
    } catch (error) {
        errorDiv.textContent = 'Error: ' + error.message;
        errorDiv.classList.add('show');
    }
}

// Edit Priority Center Functions
async function showAddPriorityModal() {
    document.getElementById('priorityModalTitle').textContent = 'Add Priority Center';
    document.getElementById('editPriorityId').value = '';
    document.getElementById('editPriorityName').value = '';

    const citySelect = document.getElementById('editPriorityCity');
    const regionSelect = document.getElementById('editPriorityRegion');
    if (!locationFiltersData) {
        await loadLocationFilters();
    }
    if (locationFiltersData) {
        if (citySelect.options.length <= 1) {
            locationFiltersData.cities.forEach(city => {
                const option = document.createElement('option');
                option.value = city;
                option.textContent = city;
                citySelect.appendChild(option);
            });
        }
        if (regionSelect.options.length <= 1) {
            locationFiltersData.regions.forEach(region => {
                const option = document.createElement('option');
                option.value = region;
                option.textContent = region;
                regionSelect.appendChild(option);
            });
        }
    }

    citySelect.value = '';
    regionSelect.value = '';

    document.getElementById('editPriorityError').textContent = '';
    document.getElementById('editPriorityError').classList.remove('show');
    document.getElementById('editPriorityModal').style.display = 'block';
}

async function editPriorityCenter(priorityId) {
    try {
        const priority = await apiCall(`/api/locations/priority-centers/${priorityId}`);
        if (!locationFiltersData) {
            await loadLocationFilters();
        }
        populatePriorityEditForm(priority);
        document.getElementById('priorityModalTitle').textContent = 'Edit Priority Center';
        document.getElementById('editPriorityModal').style.display = 'block';
    } catch (error) {
        showError('Failed to load priority center: ' + error.message);
    }
}

function populatePriorityEditForm(priority) {
    document.getElementById('editPriorityId').value = priority.id;
    document.getElementById('editPriorityName').value = priority.name || '';
    
    // Populate city and region dropdowns if not already populated
    const citySelect = document.getElementById('editPriorityCity');
    const regionSelect = document.getElementById('editPriorityRegion');
    
    if (locationFiltersData) {
        if (citySelect.options.length <= 1) {
            locationFiltersData.cities.forEach(city => {
                const option = document.createElement('option');
                option.value = city;
                option.textContent = city;
                citySelect.appendChild(option);
            });
        }
        if (regionSelect.options.length <= 1) {
            locationFiltersData.regions.forEach(region => {
                const option = document.createElement('option');
                option.value = region;
                option.textContent = region;
                regionSelect.appendChild(option);
            });
        }
    }
    
    // Set selected values
    citySelect.value = priority.address.city || '';
    regionSelect.value = priority.address.region || '';
}

function closeEditPriorityModal() {
    document.getElementById('editPriorityModal').style.display = 'none';
    document.getElementById('editPriorityError').textContent = '';
    document.getElementById('editPriorityError').classList.remove('show');
}

async function handleSavePriority(e) {
    e.preventDefault();
    const errorDiv = document.getElementById('editPriorityError');
    errorDiv.textContent = '';
    errorDiv.classList.remove('show');
    
    const priorityId = document.getElementById('editPriorityId').value;
    const formData = {
        center_name: document.getElementById('editPriorityName').value || null,
        city: document.getElementById('editPriorityCity').value || null,
        region: document.getElementById('editPriorityRegion').value || null
    };
    
    try {
        if (priorityId) {
            await apiCall(`/api/locations/priority-centers/${priorityId}`, {
                method: 'PUT',
                body: JSON.stringify(formData)
            });
            showSuccess('Priority center updated successfully!');
        } else {
            await apiCall(`/api/locations/priority-centers`, {
                method: 'POST',
                body: JSON.stringify(formData)
            });
            showSuccess('Priority center created successfully!');
        }
        closeEditPriorityModal();
        loadPriorityCenters();
    } catch (error) {
        errorDiv.textContent = 'Error: ' + error.message;
        errorDiv.classList.add('show');
    }
}

// ===== POI EDIT/CREATE =====
function showAddPoiModal() {
    document.getElementById('poiModalTitle').textContent = 'Add POI';
    document.getElementById('editPoiId').value = '';
    document.getElementById('editPoiName').value = '';
    document.getElementById('editPoiAliases').value = '';
    document.getElementById('editPoiArea').value = '';
    document.getElementById('editPoiCity').value = '';
    document.getElementById('editPoiRegion').value = '';
    document.getElementById('editPoiLatitude').value = '';
    document.getElementById('editPoiLongitude').value = '';
    document.getElementById('editPoiError').textContent = '';
    document.getElementById('editPoiError').classList.remove('show');
    document.getElementById('editPoiModal').style.display = 'block';
}

async function editPoi(poiId) {
    try {
        const poi = await apiCall(`/api/poi-landmarks/${poiId}`);
        document.getElementById('poiModalTitle').textContent = 'Edit POI';
        document.getElementById('editPoiId').value = poi.id;
        document.getElementById('editPoiName').value = poi.name || '';
        document.getElementById('editPoiAliases').value = (poi.aliases || []).join(', ');
        document.getElementById('editPoiArea').value = poi.area || '';
        document.getElementById('editPoiCity').value = poi.city || '';
        document.getElementById('editPoiRegion').value = poi.region || '';
        document.getElementById('editPoiLatitude').value = poi.latitude ?? '';
        document.getElementById('editPoiLongitude').value = poi.longitude ?? '';
        document.getElementById('editPoiError').textContent = '';
        document.getElementById('editPoiError').classList.remove('show');
        document.getElementById('editPoiModal').style.display = 'block';
    } catch (error) {
        showError('Failed to load POI: ' + error.message);
    }
}

function closeEditPoiModal() {
    document.getElementById('editPoiModal').style.display = 'none';
    document.getElementById('editPoiError').textContent = '';
    document.getElementById('editPoiError').classList.remove('show');
}

async function handleSavePoi(e) {
    e.preventDefault();
    const errorDiv = document.getElementById('editPoiError');
    errorDiv.textContent = '';
    errorDiv.classList.remove('show');

    const poiId = document.getElementById('editPoiId').value;
    const aliasesRaw = document.getElementById('editPoiAliases').value || '';
    const aliases = aliasesRaw
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);

    const latRaw = document.getElementById('editPoiLatitude').value;
    const lonRaw = document.getElementById('editPoiLongitude').value;

    const payload = {
        name: document.getElementById('editPoiName').value || null,
        aliases,
        area: document.getElementById('editPoiArea').value || null,
        city: document.getElementById('editPoiCity').value || null,
        region: document.getElementById('editPoiRegion').value || null,
        latitude: latRaw ? parseFloat(latRaw) : null,
        longitude: lonRaw ? parseFloat(lonRaw) : null
    };

    try {
        if (poiId) {
            await apiCall(`/api/poi-landmarks/${poiId}`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
            showSuccess('POI updated successfully!');
        } else {
            await apiCall(`/api/poi-landmarks`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });
            showSuccess('POI created successfully!');
        }
        closeEditPoiModal();
        loadPois();
    } catch (error) {
        errorDiv.textContent = 'Error: ' + error.message;
        errorDiv.classList.add('show');
    }
}

async function deletePoi(poiId) {
    if (!confirm('Delete this POI?')) return;
    try {
        await apiCall(`/api/poi-landmarks/${poiId}`, { method: 'DELETE' });
        showSuccess('POI deleted.');
        loadPois();
    } catch (error) {
        showError('Failed to delete POI: ' + error.message);
    }
}

// Export Functions
function exportCardFeesToCSV() {
    try {
        // Build query parameters from current filters
        const params = new URLSearchParams();
        if (currentFilters.charge_type) params.append('charge_type', currentFilters.charge_type);
        if (currentFilters.card_category) params.append('card_category', currentFilters.card_category);
        if (currentFilters.card_network) params.append('card_network', currentFilters.card_network);
        if (currentFilters.card_product) params.append('card_product', currentFilters.card_product);
        if (currentFilters.product_line) params.append('product_line', currentFilters.product_line);
        if (currentFilters.status_filter) params.append('status_filter', currentFilters.status_filter);
        
        const url = `/api/export/rules?${params.toString()}`;
        
        // Use fetch with authentication instead of window.open to ensure proper routing
        fetch(url, {
            headers: {
                'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || 'Export failed: ' + response.statusText);
                });
            }
            return response.blob();
        })
        .then(blob => {
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `card_fees_export_${new Date().toISOString().slice(0,10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        })
        .catch(error => {
            console.error('Error exporting card fees:', error);
            alert('Error exporting card fees: ' + error.message);
        });
    } catch (error) {
        console.error('Error exporting card fees:', error);
        alert('Error exporting card fees. Please try again.');
    }
}

function exportRetailChargesToCSV() {
    try {
        // Build query parameters from current filters
        const params = new URLSearchParams();
        if (retailCurrentFilters.loan_product) params.append('loan_product', retailCurrentFilters.loan_product);
        if (retailCurrentFilters.charge_type) params.append('charge_type', retailCurrentFilters.charge_type);
        if (retailCurrentFilters.status_filter) params.append('status_filter', retailCurrentFilters.status_filter);
        
        const url = `/api/export/retail-asset-charges?${params.toString()}`;
        
        // Use fetch with authentication
        fetch(url, {
            headers: {
                'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || 'Export failed: ' + response.statusText);
                });
            }
            return response.blob();
        })
        .then(blob => {
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `retail_asset_charges_export_${new Date().toISOString().slice(0,10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        })
        .catch(error => {
            console.error('Error exporting retail asset charges:', error);
            alert('Error exporting retail asset charges: ' + error.message);
        });
    } catch (error) {
        console.error('Error exporting retail asset charges:', error);
        alert('Error exporting retail asset charges. Please try again.');
    }
}

function exportSkybankingFeesToCSV() {
    try {
        // Build query parameters from current filters
        const params = new URLSearchParams();
        params.append('product_line', 'SKYBANKING');
        if (skybankingCurrentFilters.charge_type) params.append('charge_type', skybankingCurrentFilters.charge_type);
        if (skybankingCurrentFilters.card_product) params.append('card_product', skybankingCurrentFilters.card_product);
        if (skybankingCurrentFilters.card_network) params.append('card_network', skybankingCurrentFilters.card_network);
        if (skybankingCurrentFilters.status_filter) params.append('status_filter', skybankingCurrentFilters.status_filter);
        
        const url = `/api/export/rules?${params.toString()}`;
        
        // Use fetch with authentication
        fetch(url, {
            headers: {
                'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || 'Export failed: ' + response.statusText);
                });
            }
            return response.blob();
        })
        .then(blob => {
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = `skybanking_fees_export_${new Date().toISOString().slice(0,10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(downloadUrl);
        })
        .catch(error => {
            console.error('Error exporting Skybanking fees:', error);
            alert('Error exporting Skybanking fees: ' + error.message);
        });
    } catch (error) {
        console.error('Error exporting Skybanking fees:', error);
        alert('Error exporting Skybanking fees. Please try again.');
    }
}

function exportBranchesToCSV() {
    try {
        // Build query parameters from current filters
        const params = new URLSearchParams();
        const cityFilter = document.getElementById('branchFilterCity');
        const regionFilter = document.getElementById('branchFilterRegion');
        const searchFilter = document.getElementById('branchFilterSearch');
        
        if (cityFilter && cityFilter.value) params.append('city', cityFilter.value);
        if (regionFilter && regionFilter.value) params.append('region', regionFilter.value);
        if (searchFilter && searchFilter.value) params.append('search', searchFilter.value);
        
        const url = `/api/export/locations/branches?${params.toString()}`;
        
        // Try window.open first (browser will handle auth if user is logged in)
        const newWindow = window.open(url, '_blank');
        
        // If popup was blocked or failed, use fetch as fallback
        if (!newWindow || newWindow.closed || typeof newWindow.closed == 'undefined') {
            // Get credentials from localStorage
            if (!authCredentials) {
                alert('Authentication required to export data.');
                return;
            }
            
            fetch(url, {
                credentials: 'include',
                headers: {
                    'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Export failed: ' + response.statusText);
                }
                return response.blob();
            })
            .then(blob => {
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = `branches_export_${new Date().toISOString().slice(0,10)}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(downloadUrl);
            })
            .catch(error => {
                console.error('Error exporting branches:', error);
                alert('Error exporting branches: ' + error.message);
            });
        }
    } catch (error) {
        console.error('Error exporting branches:', error);
        alert('Error exporting branches. Please try again.');
    }
}

function exportMachinesToCSV() {
    try {
        // Build query parameters from current filters
        const params = new URLSearchParams();
        const typeFilter = document.getElementById('machineFilterType');
        const cityFilter = document.getElementById('machineFilterCity');
        const regionFilter = document.getElementById('machineFilterRegion');
        const searchFilter = document.getElementById('machineFilterSearch');
        
        if (typeFilter && typeFilter.value) params.append('type', typeFilter.value);
        if (cityFilter && cityFilter.value) params.append('city', cityFilter.value);
        if (regionFilter && regionFilter.value) params.append('region', regionFilter.value);
        if (searchFilter && searchFilter.value) params.append('search', searchFilter.value);
        
        const url = `/api/export/locations/machines?${params.toString()}`;
        
        // Try window.open first (browser will handle auth if user is logged in)
        const newWindow = window.open(url, '_blank');
        
        // If popup was blocked or failed, use fetch as fallback
        if (!newWindow || newWindow.closed || typeof newWindow.closed == 'undefined') {
            // Get credentials from localStorage
            if (!authCredentials) {
                alert('Authentication required to export data.');
                return;
            }
            
            fetch(url, {
                credentials: 'include',
                headers: {
                    'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Export failed: ' + response.statusText);
                }
                return response.blob();
            })
            .then(blob => {
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = `machines_export_${new Date().toISOString().slice(0,10)}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(downloadUrl);
            })
            .catch(error => {
                console.error('Error exporting machines:', error);
                alert('Error exporting machines: ' + error.message);
            });
        }
    } catch (error) {
        console.error('Error exporting machines:', error);
        alert('Error exporting machines. Please try again.');
    }
}

function exportPriorityCentersToCSV() {
    try {
        // Build query parameters from current filters
        const params = new URLSearchParams();
        const cityFilter = document.getElementById('priorityFilterCity');
        const regionFilter = document.getElementById('priorityFilterRegion');
        const searchFilter = document.getElementById('priorityFilterSearch');
        
        if (cityFilter && cityFilter.value) params.append('city', cityFilter.value);
        if (regionFilter && regionFilter.value) params.append('region', regionFilter.value);
        if (searchFilter && searchFilter.value) params.append('search', searchFilter.value);
        
        const url = `/api/export/locations/priority-centers?${params.toString()}`;
        
        // Try window.open first (browser will handle auth if user is logged in)
        const newWindow = window.open(url, '_blank');
        
        // If popup was blocked or failed, use fetch as fallback
        if (!newWindow || newWindow.closed || typeof newWindow.closed == 'undefined') {
            // Get credentials from localStorage
            if (!authCredentials) {
                alert('Authentication required to export data.');
                return;
            }
            
            fetch(url, {
                credentials: 'include',
                headers: {
                    'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Export failed: ' + response.statusText);
                }
                return response.blob();
            })
            .then(blob => {
                const downloadUrl = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = `priority_centers_export_${new Date().toISOString().slice(0,10)}.csv`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(downloadUrl);
            })
            .catch(error => {
                console.error('Error exporting priority centers:', error);
                alert('Error exporting priority centers: ' + error.message);
            });
        }
    } catch (error) {
        console.error('Error exporting priority centers:', error);
        alert('Error exporting priority centers. Please try again.');
    }
}

// ============================================================================
// PHONEBOOK FUNCTIONS - Modern Enterprise Directory
// ============================================================================

let phonebookViewMode = 'list'; // 'list' or 'grid'
let phonebookSearchTimeout = null;

// Load phonebook stats
function loadPhonebookStats() {
    fetch('/api/phonebook/stats', {
        headers: { 'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password) }
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('phonebookTotalEmployees').textContent = data.total_employees.toLocaleString();
        document.getElementById('phonebookTotalDepartments').textContent = data.total_departments.toLocaleString();
        document.getElementById('phonebookTotalDesignations').textContent = data.total_designations.toLocaleString();
    })
    .catch(error => console.error('Error loading phonebook stats:', error));
}

// Load phonebook filters
function loadPhonebookFilters() {
    fetch('/api/phonebook/filters', {
        headers: { 'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password) }
    })
    .then(response => response.json())
    .then(data => {
        phonebookFiltersData = data;
        
        const deptSelect = document.getElementById('phonebookFilterDepartment');
        deptSelect.innerHTML = '<option value="">All Departments</option>' + 
            data.departments.map(d => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join('');
        
        const desigSelect = document.getElementById('phonebookFilterDesignation');
        desigSelect.innerHTML = '<option value="">All Designations</option>' + 
            data.designations.map(d => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join('');
    })
    .catch(error => console.error('Error loading phonebook filters:', error));
}

// Load phonebook employees
function loadPhonebook() {
    showPhonebookSkeleton();
    
    let url = `/api/phonebook/employees?page=${phonebookCurrentPage}&limit=${phonebookPageSize}`;
    
    if (phonebookCurrentFilters.search) url += `&search=${encodeURIComponent(phonebookCurrentFilters.search)}`;
    if (phonebookCurrentFilters.department) url += `&department=${encodeURIComponent(phonebookCurrentFilters.department)}`;
    if (phonebookCurrentFilters.designation) url += `&designation=${encodeURIComponent(phonebookCurrentFilters.designation)}`;
    
    fetch(url, {
        headers: { 'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password) }
    })
    .then(response => response.json())
    .then(data => {
        phonebookTotal = data.total;
        renderPhonebook(data.employees);
        updatePhonebookPagination(data);
        updatePhonebookResultsText(data);
        updateClearFiltersVisibility();
    })
    .catch(error => {
        console.error('Error loading phonebook:', error);
        showPhonebookEmpty();
    });
}

// Show skeleton loading
function showPhonebookSkeleton() {
    document.getElementById('pbEmptyState').style.display = 'none';
    document.getElementById('phonebookListBody').innerHTML = `
        <div class="pb-skeleton-list">
            ${Array(5).fill('<div class="pb-skeleton-item"></div>').join('')}
        </div>
    `;
    document.getElementById('phonebookGridBody').innerHTML = '';
}

// Show empty state
function showPhonebookEmpty() {
    document.getElementById('phonebookListBody').innerHTML = '';
    document.getElementById('phonebookGridBody').innerHTML = '';
    document.getElementById('pbEmptyState').style.display = 'flex';
}

// Render phonebook (list or grid)
function renderPhonebook(employees) {
    if (!employees || employees.length === 0) {
        showPhonebookEmpty();
        return;
    }
    
    document.getElementById('pbEmptyState').style.display = 'none';
    
    // Render List View
    document.getElementById('phonebookListBody').innerHTML = employees.map(emp => `
        <div class="pb-list-item" onclick="viewEmployee(${emp.id})">
            <div class="pb-avatar">${getInitials(emp.full_name)}</div>
            <div class="pb-employee-info">
                <div class="pb-employee-name">${escapeHtml(emp.full_name)}</div>
                <div class="pb-employee-title">${escapeHtml(emp.designation || 'No designation')}</div>
                <div class="pb-employee-contact">
                    ${emp.email ? `<a href="mailto:${emp.email}" onclick="event.stopPropagation()">${emp.email}</a>` : ''}
                    ${emp.mobile ? `<a href="tel:${emp.mobile}" onclick="event.stopPropagation()">${emp.mobile}</a>` : ''}
                    ${emp.ip_phone ? `<span>IP: ${emp.ip_phone}</span>` : ''}
                </div>
            </div>
            <div class="pb-list-actions">
                <button class="pb-icon-btn view" onclick="event.stopPropagation(); viewEmployee(${emp.id})" title="View">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
                <button class="pb-icon-btn edit" onclick="event.stopPropagation(); editEmployee(${emp.id})" title="Edit">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="pb-icon-btn delete" onclick="event.stopPropagation(); deleteEmployee(${emp.id})" title="Delete">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
            </div>
        </div>
    `).join('');
    
    // Render Grid View
    document.getElementById('phonebookGridBody').innerHTML = employees.map(emp => `
        <div class="pb-card" onclick="viewEmployee(${emp.id})">
            <div class="pb-card-header">
                <div class="pb-avatar">${getInitials(emp.full_name)}</div>
                <div>
                    <div class="pb-card-name">${escapeHtml(emp.full_name)}</div>
                    <div class="pb-card-title">${escapeHtml(emp.designation || 'No designation')}</div>
                    <div class="pb-card-dept">${escapeHtml(emp.department || '')}</div>
                </div>
            </div>
            <div class="pb-card-contact">
                ${emp.mobile ? `<div class="pb-card-contact-item">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72"/></svg>
                    <a href="tel:${emp.mobile}" onclick="event.stopPropagation()">${emp.mobile}</a>
                </div>` : ''}
                ${emp.email ? `<div class="pb-card-contact-item">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                    <a href="mailto:${emp.email}" onclick="event.stopPropagation()">${emp.email}</a>
                </div>` : ''}
                ${emp.ip_phone ? `<div class="pb-card-contact-item">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
                    <span>IP: ${emp.ip_phone}</span>
                </div>` : ''}
            </div>
            <div class="pb-card-actions" onclick="event.stopPropagation()">
                ${emp.mobile ? `<a href="tel:${emp.mobile}" class="pb-card-action">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72"/></svg>
                    Call
                </a>` : ''}
                ${emp.email ? `<a href="mailto:${emp.email}" class="pb-card-action">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                    Email
                </a>` : ''}
                <button onclick="viewEmployee(${emp.id})" class="pb-card-action">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                    View
                </button>
            </div>
        </div>
    `).join('');
}

// Update results text
function updatePhonebookResultsText(data) {
    const start = (data.page - 1) * phonebookPageSize + 1;
    const end = Math.min(data.page * phonebookPageSize, data.total);
    const text = data.total > 0 ? `Showing ${start}-${end} of ${data.total.toLocaleString()} employees` : 'No employees found';
    document.getElementById('phonebookResultsText').textContent = text;
}

// Update pagination
function updatePhonebookPagination(data) {
    const totalPages = data.total_pages || Math.ceil(data.total / phonebookPageSize);
    document.getElementById('phonebookPageInfo').textContent = `Page ${data.page} of ${Math.max(totalPages, 1)}`;
    document.getElementById('phonebookPrevPage').disabled = data.page <= 1;
    document.getElementById('phonebookNextPage').disabled = data.page >= totalPages;
}

// Update clear filters visibility
function updateClearFiltersVisibility() {
    const hasFilters = phonebookCurrentFilters.search || phonebookCurrentFilters.department || phonebookCurrentFilters.designation;
    const clearBtn = document.getElementById('phonebookClearFilters');
    const clearSearch = document.getElementById('phonebookClearSearch');
    if (clearBtn) clearBtn.style.display = hasFilters ? 'block' : 'none';
    if (clearSearch) clearSearch.style.display = phonebookCurrentFilters.search ? 'block' : 'none';
}

// Clear all filters
function clearPhonebookFilters() {
    document.getElementById('phonebookSearch').value = '';
    document.getElementById('phonebookFilterDepartment').value = '';
    document.getElementById('phonebookFilterDesignation').value = '';
    phonebookCurrentFilters = {};
    phonebookCurrentPage = 1;
    loadPhonebook();
}

// Toggle view mode
function setPhonebookViewMode(mode) {
    phonebookViewMode = mode;
    document.getElementById('pbViewList').classList.toggle('active', mode === 'list');
    document.getElementById('pbViewGrid').classList.toggle('active', mode === 'grid');
    document.getElementById('pbListView').style.display = mode === 'list' ? 'block' : 'none';
    document.getElementById('pbGridView').style.display = mode === 'grid' ? 'block' : 'none';
}

// Get initials
function getInitials(name) {
    if (!name) return '?';
    const parts = name.trim().split(/\s+/).filter(p => p.length > 0);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
}

// Escape HTML
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// View employee
function viewEmployee(id) {
    fetch(`/api/phonebook/employees/${id}`, {
        headers: { 'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password) }
    })
    .then(response => response.json())
    .then(emp => {
        currentViewingEmployee = emp;
        
        // Update profile view
        document.getElementById('viewEmployeeAvatar').textContent = getInitials(emp.full_name);
        document.getElementById('viewEmployeeName').textContent = emp.full_name || 'Unknown';
        document.getElementById('viewEmployeeDesignation').textContent = emp.designation || 'No designation';
        document.getElementById('viewEmployeeDepartment').textContent = emp.department || '';
        
        // Contact info - hide empty fields
        setViewField('viewEmployeeEmail', emp.email, 'mailto:' + emp.email, 'viewRowEmail');
        setViewField('viewEmployeeMobile', emp.mobile, 'tel:' + emp.mobile, 'viewRowMobile');
        setViewFieldText('viewEmployeeTelephone', emp.telephone, 'viewRowTelephone');
        setViewFieldText('viewEmployeeIpPhone', emp.ip_phone, 'viewRowIpPhone');
        setViewFieldText('viewEmployeePabx', emp.pabx, 'viewRowPabx');
        setViewFieldText('viewEmployeeGroupEmail', emp.group_email, 'viewRowGroupEmail');
        
        // Work info
        setViewFieldText('viewEmployeeEmpId', emp.employee_id, 'viewRowEmpId');
        setViewFieldText('viewEmployeeDivision', emp.division, 'viewRowDivision');
        
        // Quick actions
        const callBtn = document.getElementById('viewActionCall');
        const emailBtn = document.getElementById('viewActionEmail');
        if (callBtn) {
            callBtn.href = emp.mobile ? 'tel:' + emp.mobile : '#';
            callBtn.style.display = emp.mobile ? 'flex' : 'none';
        }
        if (emailBtn) {
            emailBtn.href = emp.email ? 'mailto:' + emp.email : '#';
            emailBtn.style.display = emp.email ? 'flex' : 'none';
        }
        
        document.getElementById('phonebookViewModal').style.display = 'flex';
    })
    .catch(error => {
        console.error('Error loading employee:', error);
        alert('Error loading employee details');
    });
}

function setViewField(elementId, value, href, rowId) {
    const el = document.getElementById(elementId);
    const row = document.getElementById(rowId);
    if (el && row) {
        if (value) {
            el.textContent = value;
            el.href = href;
            row.style.display = 'block';
        } else {
            row.style.display = 'none';
        }
    }
}

function setViewFieldText(elementId, value, rowId) {
    const el = document.getElementById(elementId);
    const row = document.getElementById(rowId);
    if (el && row) {
        if (value) {
            el.textContent = value;
            row.style.display = 'block';
        } else {
            row.style.display = 'none';
        }
    }
}

// Close view modal
function closePhonebookViewModal() {
    document.getElementById('phonebookViewModal').style.display = 'none';
    currentViewingEmployee = null;
}

// Edit from view
function editFromView() {
    if (currentViewingEmployee) {
        closePhonebookViewModal();
        editEmployee(currentViewingEmployee.id);
    }
}

// Edit employee
function editEmployee(id) {
    fetch(`/api/phonebook/employees/${id}`, {
        headers: { 'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password) }
    })
    .then(response => response.json())
    .then(emp => {
        document.getElementById('phonebookModalTitle').textContent = 'Edit Employee';
        document.getElementById('phonebookEmployeeId').value = emp.id;
        document.getElementById('phonebookEmpId').value = emp.employee_id || '';
        document.getElementById('phonebookFullName').value = emp.full_name || '';
        document.getElementById('phonebookDesignation').value = emp.designation || '';
        document.getElementById('phonebookDepartment').value = emp.department || '';
        document.getElementById('phonebookDivision').value = emp.division || '';
        document.getElementById('phonebookEmail').value = emp.email || '';
        document.getElementById('phonebookMobile').value = emp.mobile || '';
        document.getElementById('phonebookTelephone').value = emp.telephone || '';
        document.getElementById('phonebookPabx').value = emp.pabx || '';
        document.getElementById('phonebookIpPhone').value = emp.ip_phone || '';
        document.getElementById('phonebookGroupEmail').value = emp.group_email || '';
        document.getElementById('phonebookFormError').textContent = '';
        document.getElementById('phonebookModal').style.display = 'flex';
    })
    .catch(error => {
        console.error('Error loading employee:', error);
        alert('Error loading employee');
    });
}

// Add new employee
function openAddEmployeeModal() {
    document.getElementById('phonebookModalTitle').textContent = 'Add Employee';
    document.getElementById('phonebookEmployeeId').value = '';
    document.getElementById('phonebookForm').reset();
    document.getElementById('phonebookFormError').textContent = '';
    document.getElementById('phonebookModal').style.display = 'flex';
}

// Close modal
function closePhonebookModal() {
    document.getElementById('phonebookModal').style.display = 'none';
}

// Save employee
function saveEmployee(event) {
    event.preventDefault();
    
    const id = document.getElementById('phonebookEmployeeId').value;
    const isEdit = !!id;
    
    const employeeData = {
        employee_id: document.getElementById('phonebookEmpId').value || null,
        full_name: document.getElementById('phonebookFullName').value,
        designation: document.getElementById('phonebookDesignation').value || null,
        department: document.getElementById('phonebookDepartment').value || null,
        division: document.getElementById('phonebookDivision').value || null,
        email: document.getElementById('phonebookEmail').value || null,
        mobile: document.getElementById('phonebookMobile').value || null,
        telephone: document.getElementById('phonebookTelephone').value || null,
        pabx: document.getElementById('phonebookPabx').value || null,
        ip_phone: document.getElementById('phonebookIpPhone').value || null,
        group_email: document.getElementById('phonebookGroupEmail').value || null
    };
    
    fetch(isEdit ? `/api/phonebook/employees/${id}` : '/api/phonebook/employees', {
        method: isEdit ? 'PUT' : 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password)
        },
        body: JSON.stringify(employeeData)
    })
    .then(response => {
        if (!response.ok) return response.json().then(err => { throw new Error(err.detail || 'Error saving'); });
        return response.json();
    })
    .then(() => {
        closePhonebookModal();
        loadPhonebook();
        loadPhonebookStats();
        loadPhonebookFilters();
    })
    .catch(error => {
        document.getElementById('phonebookFormError').textContent = error.message;
    });
}

// Delete employee
function deleteEmployee(id) {
    if (!confirm('Delete this employee?')) return;
    
    fetch(`/api/phonebook/employees/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password) }
    })
    .then(response => {
        if (!response.ok) throw new Error('Error deleting');
        return response.json();
    })
    .then(() => {
        loadPhonebook();
        loadPhonebookStats();
    })
    .catch(error => alert('Error deleting employee'));
}

// Export phonebook
function exportPhonebook() {
    let url = '/api/export/phonebook?';
    if (phonebookCurrentFilters.search) url += `search=${encodeURIComponent(phonebookCurrentFilters.search)}&`;
    if (phonebookCurrentFilters.department) url += `department=${encodeURIComponent(phonebookCurrentFilters.department)}&`;
    if (phonebookCurrentFilters.designation) url += `designation=${encodeURIComponent(phonebookCurrentFilters.designation)}&`;
    
    fetch(url, {
        headers: { 'Authorization': 'Basic ' + btoa(authCredentials.username + ':' + authCredentials.password) }
    })
    .then(response => response.blob())
    .then(blob => {
        const a = document.createElement('a');
        a.href = window.URL.createObjectURL(blob);
        a.download = `phonebook_${new Date().toISOString().slice(0,10)}.csv`;
        a.click();
    })
    .catch(error => alert('Error exporting'));
}

// Setup event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Live search with debounce
    const searchInput = document.getElementById('phonebookSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(phonebookSearchTimeout);
            phonebookSearchTimeout = setTimeout(() => {
                phonebookCurrentFilters.search = this.value;
                phonebookCurrentPage = 1;
                loadPhonebook();
            }, 300);
        });
    }
    
    // Clear search button
    const clearSearch = document.getElementById('phonebookClearSearch');
    if (clearSearch) {
        clearSearch.addEventListener('click', () => {
            document.getElementById('phonebookSearch').value = '';
            phonebookCurrentFilters.search = '';
            phonebookCurrentPage = 1;
            loadPhonebook();
        });
    }
    
    // Filter dropdowns - apply on change
    const deptFilter = document.getElementById('phonebookFilterDepartment');
    const desigFilter = document.getElementById('phonebookFilterDesignation');
    if (deptFilter) {
        deptFilter.addEventListener('change', function() {
            phonebookCurrentFilters.department = this.value;
            phonebookCurrentPage = 1;
            loadPhonebook();
        });
    }
    if (desigFilter) {
        desigFilter.addEventListener('change', function() {
            phonebookCurrentFilters.designation = this.value;
            phonebookCurrentPage = 1;
            loadPhonebook();
        });
    }
    
    // Clear filters
    const clearBtn = document.getElementById('phonebookClearFilters');
    if (clearBtn) clearBtn.addEventListener('click', clearPhonebookFilters);
    
    // Export
    const exportBtn = document.getElementById('exportPhonebook');
    if (exportBtn) exportBtn.addEventListener('click', exportPhonebook);
    
    // Add employee
    const addBtn = document.getElementById('addNewEmployee');
    if (addBtn) addBtn.addEventListener('click', openAddEmployeeModal);
    
    // View toggle
    const viewList = document.getElementById('pbViewList');
    const viewGrid = document.getElementById('pbViewGrid');
    if (viewList) viewList.addEventListener('click', () => setPhonebookViewMode('list'));
    if (viewGrid) viewGrid.addEventListener('click', () => setPhonebookViewMode('grid'));
    
    // Pagination
    const prevBtn = document.getElementById('phonebookPrevPage');
    const nextBtn = document.getElementById('phonebookNextPage');
    if (prevBtn) prevBtn.addEventListener('click', () => { if (phonebookCurrentPage > 1) { phonebookCurrentPage--; loadPhonebook(); } });
    if (nextBtn) nextBtn.addEventListener('click', () => { if (phonebookCurrentPage < Math.ceil(phonebookTotal / phonebookPageSize)) { phonebookCurrentPage++; loadPhonebook(); } });
    
    // Page size
    const pageSizeSelect = document.getElementById('phonebookPageSize');
    if (pageSizeSelect) {
        pageSizeSelect.addEventListener('change', function() {
            phonebookPageSize = parseInt(this.value);
            phonebookCurrentPage = 1;
            loadPhonebook();
        });
    }
    
    // Form submit
    const form = document.getElementById('phonebookForm');
    if (form) form.addEventListener('submit', saveEmployee);
    
    // Close modals on overlay click
    document.querySelectorAll('.pb-modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function() {
            this.parentElement.style.display = 'none';
        });
    });
    
    // Close modals on Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            document.getElementById('phonebookModal').style.display = 'none';
            document.getElementById('phonebookViewModal').style.display = 'none';
        }
    });
});
