/**
 * Billipocket Sidebar Component
 * Exact implementation per requirements
 */

(function(window, document) {
  'use strict';

  class BillipocketSidebar {
    constructor(options = {}) {
      this.config = {
        sidebarId: 'bpSidebar',
        edgeId: 'bpEdge', 
        fabId: 'bpFab',
        overlayId: 'bpOverlay',
        mobileBreakpoint: 767.98,
        mediumBreakpoint: 1024,
        ...options
      };

      this.elements = {};
      this.mediaQueries = {};
      this.isInitialized = false;
      this.focusedElementBeforeOpen = null;

      // Bind methods
      this.onResize = this.onResize.bind(this);
      this.onEdgeClick = this.onEdgeClick.bind(this);
      this.onFabClick = this.onFabClick.bind(this);
      this.onOverlayClick = this.onOverlayClick.bind(this);
      this.onKeyDown = this.onKeyDown.bind(this);
      this.onNavLinkClick = this.onNavLinkClick.bind(this);
    }

    init() {
      if (this.isInitialized) {
        console.warn('BillipocketSidebar already initialized');
        return;
      }

      try {
        this.cacheElements();
        this.setupMediaQueries();
        this.bindEvents();
        this.onResize();
        this.updateAriaStates();
        this.isInitialized = true;
        
        console.log('✅ BillipocketSidebar initialized successfully');
      } catch (error) {
        console.error('❌ Failed to initialize BillipocketSidebar:', error);
      }
    }

    cacheElements() {
      this.elements = {
        sidebar: document.getElementById(this.config.sidebarId),
        edge: document.getElementById(this.config.edgeId),
        fab: document.getElementById(this.config.fabId),
        overlay: document.getElementById(this.config.overlayId),
        navLinks: document.querySelectorAll('.bp-nav .nav-link')
      };

      const required = ['sidebar', 'edge', 'fab', 'overlay'];
      const missing = required.filter(key => !this.elements[key]);
      
      if (missing.length > 0) {
        throw new Error(`Missing required elements: ${missing.join(', ')}`);
      }
    }

    setupMediaQueries() {
      this.mediaQueries = {
        mobile: window.matchMedia(`(max-width: ${this.config.mobileBreakpoint}px)`),
        tablet: window.matchMedia(`(min-width: ${this.config.mobileBreakpoint + 0.02}px) and (max-width: ${this.config.mediumBreakpoint}px)`),
        desktop: window.matchMedia(`(min-width: ${this.config.mediumBreakpoint + 0.02}px)`)
      };
    }

    bindEvents() {
      // Media query listeners
      Object.values(this.mediaQueries).forEach(mq => {
        mq.addEventListener('change', this.onResize);
      });

      // Button interactions
      this.elements.edge.addEventListener('click', this.onEdgeClick);
      this.elements.fab.addEventListener('click', this.onFabClick);
      this.elements.overlay.addEventListener('click', this.onOverlayClick);

      // Navigation links (mobile auto-close)
      this.elements.navLinks.forEach(link => {
        link.addEventListener('click', this.onNavLinkClick);
      });

      // Keyboard events
      document.addEventListener('keydown', this.onKeyDown);

      // Window resize with debounce
      window.addEventListener('resize', this.debounce(this.onResize, 100));
    }

    onResize() {
      const { mobile, tablet, desktop } = this.mediaQueries;

      // Remove all mode classes first
      document.body.classList.remove('menu-open', 'no-scroll');

      if (mobile.matches) {
        this.handleMobileMode();
      } else if (tablet.matches) {
        this.handleTabletMode();
      } else if (desktop.matches) {
        this.handleDesktopMode();
      }

      this.updateAriaStates();
    }

    handleMobileMode() {
      // Remove desktop/tablet classes
      document.body.classList.remove('expanded', 'has-collapsed');
      
      // Close sidebar and overlay
      this.elements.sidebar.classList.remove('show');
      this.elements.overlay.classList.remove('show');
      document.body.classList.remove('no-scroll');
      
      // Make sure FAB is visible when closed
      if (!this.elements.sidebar.classList.contains('show')) {
        document.body.classList.remove('menu-open');
      }
    }

    handleTabletMode() {
      // Remove desktop/mobile classes
      document.body.classList.remove('has-collapsed', 'menu-open', 'no-scroll');
      this.elements.sidebar.classList.remove('show');
      this.elements.overlay.classList.remove('show');
      
      // Default to mini mode unless explicitly expanded
      if (!document.body.classList.contains('expanded')) {
        // Keep default mini state
      }
    }

    handleDesktopMode() {
      // Remove tablet/mobile classes
      document.body.classList.remove('expanded', 'menu-open', 'no-scroll');
      this.elements.sidebar.classList.remove('show');
      this.elements.overlay.classList.remove('show');
      
      // Default to expanded unless explicitly collapsed
      if (!document.body.classList.contains('has-collapsed')) {
        // Keep default expanded state
      }
    }

    onEdgeClick(event) {
      event.preventDefault();
      
      const { mobile, tablet, desktop } = this.mediaQueries;

      if (mobile.matches) {
        // Mobile: should not happen (edge is hidden)
        return;
      } else if (tablet.matches) {
        // Tablet: toggle expanded state
        document.body.classList.toggle('expanded');
      } else if (desktop.matches) {
        // Desktop: toggle collapsed state
        document.body.classList.toggle('has-collapsed');
      }

      this.updateAriaStates();
    }

    onFabClick(event) {
      event.preventDefault();

      if (!this.mediaQueries.mobile.matches) return;

      const isOpen = this.elements.sidebar.classList.contains('show');
      
      if (isOpen) {
        this.closeMobileSidebar();
      } else {
        this.openMobileSidebar();
      }
    }

    onOverlayClick(event) {
      event.preventDefault();
      this.closeMobileSidebar();
    }

    onNavLinkClick(event) {
      // Auto-close mobile sidebar on navigation
      if (this.mediaQueries.mobile.matches && this.elements.sidebar.classList.contains('show')) {
        setTimeout(() => {
          this.closeMobileSidebar();
        }, 150);
      }
    }

    onKeyDown(event) {
      // Escape key closes mobile sidebar
      if (event.key === 'Escape' && 
          this.mediaQueries.mobile.matches && 
          this.elements.sidebar.classList.contains('show')) {
        this.closeMobileSidebar();
        this.restoreFocus();
      }
    }

    openMobileSidebar() {
      if (!this.mediaQueries.mobile.matches) return;
      
      // Store currently focused element
      this.focusedElementBeforeOpen = document.activeElement;
      
      // Open sidebar
      this.elements.sidebar.classList.add('show');
      this.elements.overlay.classList.add('show');
      document.body.classList.add('no-scroll', 'menu-open');
      
      // Focus trap (focus first focusable element in sidebar)
      const firstFocusable = this.elements.sidebar.querySelector('a, button, [tabindex="0"]');
      if (firstFocusable) {
        firstFocusable.focus();
      }
      
      this.updateAriaStates();
    }

    closeMobileSidebar() {
      if (!this.elements.sidebar.classList.contains('show')) return;

      this.elements.sidebar.classList.remove('show');
      this.elements.overlay.classList.remove('show');
      document.body.classList.remove('no-scroll', 'menu-open');
      
      this.updateAriaStates();
    }

    restoreFocus() {
      // Restore focus to FAB when sidebar closes
      if (this.mediaQueries.mobile.matches) {
        this.elements.fab.focus();
      } else if (this.focusedElementBeforeOpen) {
        this.focusedElementBeforeOpen.focus();
        this.focusedElementBeforeOpen = null;
      }
    }

    updateAriaStates() {
      const { mobile, tablet, desktop } = this.mediaQueries;

      if (mobile.matches) {
        const isOpen = this.elements.sidebar.classList.contains('show');
        
        // Update FAB
        this.elements.fab.setAttribute('aria-expanded', isOpen.toString());
        this.elements.fab.setAttribute('aria-label', isOpen ? 'Sulge menüü' : 'Ava menüü');
        
        // Update edge (though it's hidden)
        this.elements.edge.setAttribute('aria-expanded', isOpen.toString());
        
        // Update overlay
        this.elements.overlay.setAttribute('aria-hidden', (!isOpen).toString());
        
        // Update icon
        const fabIcon = this.elements.fab.querySelector('i');
        if (fabIcon) {
          fabIcon.className = isOpen ? 'bi bi-chevron-left' : 'bi bi-chevron-right';
        }
        
      } else if (tablet.matches) {
        const isExpanded = document.body.classList.contains('expanded');
        
        // Update edge button
        this.elements.edge.setAttribute('aria-expanded', isExpanded.toString());
        this.elements.edge.setAttribute('aria-label', isExpanded ? 'Sulge menüü' : 'Ava menüü');
        
        // Update FAB (hidden but keep in sync)
        this.elements.fab.setAttribute('aria-expanded', isExpanded.toString());
        
        // Update icon
        const edgeIcon = this.elements.edge.querySelector('i');
        if (edgeIcon) {
          edgeIcon.className = isExpanded ? 'bi bi-chevron-left' : 'bi bi-chevron-right';
        }
        
      } else if (desktop.matches) {
        const isCollapsed = document.body.classList.contains('has-collapsed');
        
        // Update edge button
        this.elements.edge.setAttribute('aria-expanded', (!isCollapsed).toString());
        this.elements.edge.setAttribute('aria-label', isCollapsed ? 'Ava menüü' : 'Sulge menüü');
        
        // Update FAB (hidden but keep in sync)
        this.elements.fab.setAttribute('aria-expanded', (!isCollapsed).toString());
        
        // Update icon
        const edgeIcon = this.elements.edge.querySelector('i');
        if (edgeIcon) {
          edgeIcon.className = isCollapsed ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
        }
      }
    }

    getState() {
      const { mobile, tablet, desktop } = this.mediaQueries;

      if (mobile.matches) {
        return {
          mode: 'mobile',
          isOpen: this.elements.sidebar.classList.contains('show')
        };
      } else if (tablet.matches) {
        return {
          mode: 'tablet',
          isExpanded: document.body.classList.contains('expanded')
        };
      } else {
        return {
          mode: 'desktop',
          isCollapsed: document.body.classList.contains('has-collapsed')
        };
      }
    }

    // Utility: Debounce function
    debounce(func, wait) {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout);
          func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    }

    destroy() {
      if (!this.isInitialized) return;

      // Remove event listeners
      Object.values(this.mediaQueries).forEach(mq => {
        mq.removeEventListener('change', this.onResize);
      });

      this.elements.edge.removeEventListener('click', this.onEdgeClick);
      this.elements.fab.removeEventListener('click', this.onFabClick);
      this.elements.overlay.removeEventListener('click', this.onOverlayClick);

      this.elements.navLinks.forEach(link => {
        link.removeEventListener('click', this.onNavLinkClick);
      });

      document.removeEventListener('keydown', this.onKeyDown);
      window.removeEventListener('resize', this.onResize);

      // Reset state
      document.body.classList.remove('expanded', 'has-collapsed', 'no-scroll', 'menu-open');
      this.elements.sidebar.classList.remove('show');
      this.elements.overlay.classList.remove('show');

      this.isInitialized = false;
      console.log('🗑️ BillipocketSidebar destroyed');
    }
  }

  // Global instance for backward compatibility
  window.billipocketSidebarInstance = null;

  // Legacy API
  window.BilliPocketSidebar = {
    init: function(options) {
      if (window.billipocketSidebarInstance) {
        window.billipocketSidebarInstance.destroy();
      }
      
      window.billipocketSidebarInstance = new BillipocketSidebar(options);
      window.billipocketSidebarInstance.init();
      
      return window.billipocketSidebarInstance;
    }
  };

  // Legacy functions
  window.toggleMobileSidebar = function() {
    if (window.billipocketSidebarInstance) {
      const fab = document.getElementById('bpFab');
      if (fab) fab.click();
    }
  };

  window.closeMobileSidebar = function() {
    if (window.billipocketSidebarInstance) {
      window.billipocketSidebarInstance.closeMobileSidebar();
    }
  };

  window.closeSidebarOnNavigate = function() {
    if (window.innerWidth < 768) {
      window.closeMobileSidebar();
    }
  };

  // Auto-initialization
  function autoInit() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', autoInit);
      return;
    }

    const sidebar = document.getElementById('bpSidebar');
    if (sidebar && !window.billipocketSidebarInstance) {
      window.BilliPocketSidebar.init();
    }
  }

  // Export class
  window.BillipocketSidebar = BillipocketSidebar;

  // Start auto-initialization
  autoInit();

})(window, document);