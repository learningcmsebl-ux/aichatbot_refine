/**
 * Excel-like Grid System for Retail Asset Charges Table
 * Features: Column resizing, auto-fit, width persistence, row expansion
 */

class ChargesGrid {
    constructor(tableId, storageKey = 'chargesGrid.widths.v1') {
        this.tableId = tableId;
        this.storageKey = storageKey;
        this.table = document.getElementById(tableId);
        
        // Default column widths
        this.defaultWidths = {
            expand: 40,
            id: 110,
            loanProduct: 220,
            chargeType: 160,
            chargeContext: 160,
            description: 320,
            feeValue: 280,
            unit: 90,
            effectiveFrom: 130,
            status: 100,
            actions: 160
        };
        
        // Min/Max widths per column
        this.minWidths = {
            expand: 40,
            id: 80,
            loanProduct: 120,
            chargeType: 100,
            chargeContext: 100,
            description: 150,
            feeValue: 150,
            unit: 60,
            effectiveFrom: 100,
            status: 80,
            actions: 140
        };
        
        this.maxWidths = {
            expand: 40,
            id: 200,
            loanProduct: 400,
            chargeType: 300,
            chargeContext: 300,
            description: 700,
            feeValue: 700,
            unit: 150,
            effectiveFrom: 200,
            status: 150,
            actions: 200
        };
        
        // Load saved widths or use defaults
        this.widths = this.loadWidths();
        
        // Resize state
        this.resizing = null;
        
        this.init();
    }
    
    init() {
        if (!this.table) {
            console.error(`Table #${this.tableId} not found`);
            return;
        }
        
        // Apply widths to all cells
        this.applyWidths();
        
        // Setup resize handles
        this.setupResizers();
    }
    
    loadWidths() {
        try {
            const saved = localStorage.getItem(this.storageKey);
            if (saved) {
                return { ...this.defaultWidths, ...JSON.parse(saved) };
            }
        } catch (e) {
            console.warn('Failed to load saved widths:', e);
        }
        return { ...this.defaultWidths };
    }
    
    saveWidths() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.widths));
        } catch (e) {
            console.warn('Failed to save widths:', e);
        }
    }
    
    applyWidths() {
        Object.keys(this.widths).forEach(colId => {
            const width = this.widths[colId];
            const cells = this.table.querySelectorAll(`[data-col="${colId}"]`);
            cells.forEach(cell => {
                cell.style.width = width + 'px';
                cell.style.minWidth = width + 'px';
                cell.style.maxWidth = width + 'px';
            });
        });
    }
    
    setupResizers() {
        const headers = this.table.querySelectorAll('th[data-col]');
        
        headers.forEach(th => {
            const colId = th.getAttribute('data-col');
            const resizer = th.querySelector('.colResizer');
            
            if (!resizer) return;
            
            // Double-click to auto-fit
            resizer.addEventListener('dblclick', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.autoFitColumn(colId);
            });
            
            // Drag to resize
            resizer.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.startResize(colId, e.pageX);
            });
        });
    }
    
    startResize(colId, startX) {
        const startWidth = this.widths[colId];
        
        this.resizing = {
            colId,
            startX,
            startWidth
        };
        
        document.body.classList.add('resizing');
        
        const onMouseMove = (e) => {
            if (!this.resizing) return;
            
            const deltaX = e.pageX - this.resizing.startX;
            const newWidth = Math.max(
                this.minWidths[colId],
                Math.min(this.maxWidths[colId], this.resizing.startWidth + deltaX)
            );
            
            this.widths[colId] = newWidth;
            this.applyColumnWidth(colId);
        };
        
        const onMouseUp = () => {
            if (this.resizing) {
                this.saveWidths();
                this.resizing = null;
            }
            document.body.classList.remove('resizing');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }
    
    applyColumnWidth(colId) {
        const width = this.widths[colId];
        const cells = this.table.querySelectorAll(`[data-col="${colId}"]`);
        cells.forEach(cell => {
            cell.style.width = width + 'px';
            cell.style.minWidth = width + 'px';
            cell.style.maxWidth = width + 'px';
        });
    }
    
    autoFitColumn(colId) {
        const cells = this.table.querySelectorAll(`[data-col="${colId}"]`);
        let maxWidth = this.minWidths[colId];
        
        // Create measuring element
        const measurer = document.createElement('div');
        measurer.style.cssText = `
            position: absolute;
            visibility: hidden;
            height: auto;
            width: auto;
            white-space: nowrap;
            font-family: inherit;
            font-size: inherit;
            font-weight: inherit;
            padding: 10px 8px;
        `;
        document.body.appendChild(measurer);
        
        cells.forEach(cell => {
            const text = cell.textContent || '';
            const isHeader = cell.tagName === 'TH';
            
            if (isHeader) {
                measurer.style.fontWeight = '600';
                measurer.style.fontSize = '13px';
                measurer.style.textTransform = 'uppercase';
                measurer.style.letterSpacing = '0.5px';
            } else {
                measurer.style.fontWeight = 'normal';
                measurer.style.fontSize = '14px';
                measurer.style.textTransform = 'none';
                measurer.style.letterSpacing = 'normal';
            }
            
            measurer.textContent = text;
            const width = measurer.offsetWidth + 20; // Add padding
            maxWidth = Math.max(maxWidth, width);
        });
        
        document.body.removeChild(measurer);
        
        // Apply capped width
        const newWidth = Math.min(maxWidth, this.maxWidths[colId]);
        this.widths[colId] = newWidth;
        this.applyColumnWidth(colId);
        this.saveWidths();
    }
    
    resetWidths() {
        this.widths = { ...this.defaultWidths };
        this.applyWidths();
        this.saveWidths();
    }
}

// Initialize grid when DOM is ready
function initChargesGrid() {
    // Wait for table to exist
    const checkTable = setInterval(() => {
        const table = document.getElementById('retailChargesTable');
        if (table && table.classList.contains('gridTable')) {
            clearInterval(checkTable);
            window.gridCharges = new ChargesGrid('retailChargesTable');
            console.log('Charges grid initialized');
        }
    }, 100);
    
    // Stop checking after 5 seconds
    setTimeout(() => clearInterval(checkTable), 5000);
}

// Auto-initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initChargesGrid);
} else {
    initChargesGrid();
}
