from datetime import date
from app.models import db, Invoice


class InvoiceStatusTransition:
    """Service class for managing invoice status transitions."""
    
    # Valid statuses - simplified 2-status system
    UNPAID = 'maksmata'
    PAID = 'makstud'
    
    VALID_STATUSES = [UNPAID, PAID]
    
    # Status messages in Estonian
    STATUS_MESSAGES = {
        UNPAID: 'Arve on märgitud maksmata.',
        PAID: 'Arve on märgitud makstud.'
    }
    
    @classmethod
    def can_transition_to(cls, current_status, new_status):
        """
        Check if status transition is allowed.
        
        Args:
            current_status: Current invoice status
            new_status: Desired new status
            
        Returns:
            tuple: (can_change: bool, error_message: str|None)
        """
        # Validate new status
        if new_status not in cls.VALID_STATUSES:
            return False, f'Vigane staatus: {new_status}'
        
        # Same status - no change needed
        if current_status == new_status:
            return True, None
        
        # Allow all status transitions for flexibility
        # (Business requirement: sometimes paid invoices need to be modified)
        
        return True, None
    
    @classmethod
    def can_transition_overdue_to_sent(cls, invoice, new_status):
        """
        No longer needed - simplified 2-status system handles overdue dynamically.
        
        Returns:
            tuple: (can_change: bool, error_message: str|None)
        """
        return True, None
    
    @classmethod
    def transition_invoice_status(cls, invoice, new_status):
        """
        Transition invoice to new status with validation.
        
        Args:
            invoice: Invoice object
            new_status: New status to set
            
        Returns:
            tuple: (success: bool, message: str)
        """
        # Check basic transition rules
        can_change, error_msg = cls.can_transition_to(invoice.status, new_status)
        if not can_change:
            return False, error_msg
        
        # Check overdue specific rules
        can_change_overdue, overdue_error = cls.can_transition_overdue_to_sent(invoice, new_status)
        if not can_change_overdue:
            return False, overdue_error
        
        try:
            # Set new status
            invoice.set_status(new_status)
            
            # Get success message
            success_msg = cls.STATUS_MESSAGES.get(new_status, 'Staatust on muudetud.')
            
            return True, success_msg
            
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, 'Staatuse muutmisel tekkis viga. Palun proovi uuesti.'
    
    @classmethod
    def update_overdue_invoices(cls):
        """
        Update all eligible invoices to overdue status.
        
        Returns:
            int: Number of invoices updated
        """
        return Invoice.update_overdue_invoices()
    
    @classmethod
    def get_valid_transitions(cls, current_status):
        """
        Get list of valid status transitions from current status.
        
        Args:
            current_status: Current invoice status
            
        Returns:
            list: List of valid status transitions
        """
        # Allow all transitions for flexibility (business requirement)
        return cls.VALID_STATUSES
    
    @classmethod
    def get_status_display_name(cls, status):
        """
        Get human-readable display name for status.
        
        Args:
            status: Status code
            
        Returns:
            str: Display name
        """
        display_names = {
            cls.UNPAID: 'Maksmata',
            cls.PAID: 'Makstud'
        }
        return display_names.get(status, status)
    
    @classmethod
    def get_status_css_class(cls, status):
        """
        Get CSS class for status styling.
        
        Args:
            status: Status code
            
        Returns:
            str: CSS class name
        """
        css_classes = {
            cls.UNPAID: 'badge-warning',
            cls.PAID: 'badge-success'
        }
        return css_classes.get(status, 'badge-light')