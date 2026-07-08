/**
 * Excel-like Grid System for Retail Asset Charges Table
 * Features: Column resizing, auto-fit, width persistence, row expansion
 */

class ChargesGrid {
    constructor(tableId, storageKey = 'chargesGrid.widths.v2-compact') {
        this.tableId = tableId;
        this.storageKey = storageKey;
        this.table = document.getElementById(tableId);
        
        // Default column widths - COMPACT layout
        this.defaultWidths = {
            expand: 28,
            actions: 100,
            loanProduct: 140,
            chargeType: 110,
            chargeContext: 100,
            description: 200,
            feeValue: 180,
            unit: 55,
            effectiveFrom: 90,
            status: 65
        };
        
        // Min/Max widths per column
        this.minWidths = {
            expand: 28,
            actions: 90,
            loanProduct: 100,
            chargeType: 80,
            chargeContext: 80,
            description: 120,
            feeValue: 120,
            unit: 45,
            effectiveFrom: 80,
            status: 55
        };
        
        this.maxWidths = {
            expand: 28,
            actions: 140,
            loanProduct: 250,
            chargeType: 200,
            chargeContext: 180,
            description: 400,
            feeValue: 400,
            unit: 100,
            effectiveFrom: 140,
            status: 100
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

/**
 * Horizontal Scroll Enhancements
 * - Mouse wheel horizontal scrolling (no Shift key needed when hovering over table)
 * - Scroll shadow indicators
 */
function initHorizontalScroll() {
    const scrollContainers = document.querySelectorAll('.gridScroll');
    
    scrollContainers.forEach(container => {
        // Mouse wheel horizontal scrolling
        container.addEventListener('wheel', (e) => {
            // Only intercept if there's horizontal overflow
            if (container.scrollWidth <= container.clientWidth) return;
            
            // If user is doing vertical scroll and there's vertical content, let it pass
            if (Math.abs(e.deltaY) > Math.abs(e.deltaX) && e.shiftKey === false) {
                // Convert vertical scroll to horizontal when over the table
                e.preventDefault();
                container.scrollLeft += e.deltaY;
            }
            
            updateScrollShadows(container);
        }, { passive: false });
        
        // Track scroll position for shadow indicators
        container.addEventListener('scroll', () => {
            updateScrollShadows(container);
        });
        
        // Initial shadow state
        setTimeout(() => updateScrollShadows(container), 100);
    });
}

function updateScrollShadows(container) {
    const scrollLeft = container.scrollLeft;
    const maxScroll = container.scrollWidth - container.clientWidth;
    
    // Left shadow: show when scrolled right (content exists to the left)
    if (scrollLeft > 5) {
        container.classList.add('scroll-left');
    } else {
        container.classList.remove('scroll-left');
    }
    
    // Right shadow: show when more content exists to the right
    if (scrollLeft < maxScroll - 5) {
        container.classList.add('scroll-right');
    } else {
        container.classList.remove('scroll-right');
    }
}

// Initialize horizontal scroll enhancements
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHorizontalScroll);
} else {
    // Small delay to ensure containers are rendered
    setTimeout(initHorizontalScroll, 200);
}

// Re-initialize when tab is switched (for lazy-loaded content)
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('tab-btn')) {
        setTimeout(initHorizontalScroll, 100);
    }
});

/**
 * Keyboard Navigation for Grid Tables
 * - Page Up/Down: Scroll vertically by page
 * - Home/End: Scroll to top/bottom
 * - Arrow Left/Right: Scroll horizontally
 */
function initKeyboardNavigation() {
    const scrollContainers = document.querySelectorAll('.gridScroll');
    
    scrollContainers.forEach(container => {
        // Make container focusable
        container.setAttribute('tabindex', '0');
        
        container.addEventListener('keydown', (e) => {
            const scrollAmount = 200;
            const pageScrollAmount = container.clientHeight - 50;
            
            switch (e.key) {
                case 'PageDown':
                    e.preventDefault();
                    container.scrollBy({ top: pageScrollAmount, behavior: 'smooth' });
                    break;
                case 'PageUp':
                    e.preventDefault();
                    container.scrollBy({ top: -pageScrollAmount, behavior: 'smooth' });
                    break;
                case 'Home':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        container.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
                    }
                    break;
                case 'End':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        container.scrollTo({ 
                            top: container.scrollHeight, 
                            left: 0, 
                            behavior: 'smooth' 
                        });
                    }
                    break;
                case 'ArrowLeft':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        container.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
                    }
                    break;
                case 'ArrowRight':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        container.scrollBy({ left: scrollAmount, behavior: 'smooth' });
                    }
                    break;
            }
            
            updateScrollShadows(container);
        });
    });
}

// Initialize keyboard navigation
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initKeyboardNavigation);
} else {
    setTimeout(initKeyboardNavigation, 300);
}
