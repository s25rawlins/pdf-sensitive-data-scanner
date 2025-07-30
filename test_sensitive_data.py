#!/usr/bin/env python3
"""Create a test PDF with sensitive data for testing the scanner."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def create_test_pdf():
    # Create a PDF with various types of sensitive data
    c = canvas.Canvas("test_sensitive_data.pdf", pagesize=letter)
    width, height = letter
    
    # Page 1: Personal Information
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, "Employee Records - Confidential")
    
    c.setFont("Helvetica", 12)
    y_position = height - 1.5*inch
    
    # Add various types of sensitive data
    sensitive_data = [
        "Name: John Doe",
        "SSN: 123-45-6789",
        "Date of Birth: 01/15/1985",
        "Phone: (555) 123-4567",
        "Email: john.doe@example.com",
        "Credit Card: 4532-1234-5678-9012",
        "Bank Account: 123456789",
        "Driver's License: D123-4567-8901",
        "Passport Number: M12345678",
        "Medical Record: MRN-2024-001234",
        "IP Address: 192.168.1.100",
        "Employee ID: EMP-2024-0567",
        "Salary: $85,000",
        "Address: 123 Main St, Anytown, CA 90210"
    ]
    
    for data in sensitive_data:
        c.drawString(1*inch, y_position, data)
        y_position -= 0.3*inch
    
    # Page 2: Financial Information
    c.showPage()
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, "Financial Report - Internal Use Only")
    
    c.setFont("Helvetica", 12)
    y_position = height - 1.5*inch
    
    financial_data = [
        "Account Holder: Jane Smith",
        "Account Number: 9876543210",
        "Routing Number: 021000021",
        "Credit Score: 750",
        "Annual Income: $120,000",
        "Tax ID: 98-7654321",
        "Investment Account: INV-2024-789",
        "Bitcoin Wallet: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "PayPal: jane.smith@paypal.com",
        "Venmo: @janesmith123"
    ]
    
    for data in financial_data:
        c.drawString(1*inch, y_position, data)
        y_position -= 0.3*inch
    
    # Page 3: Medical Information
    c.showPage()
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, "Patient Medical Records")
    
    c.setFont("Helvetica", 12)
    y_position = height - 1.5*inch
    
    medical_data = [
        "Patient: Robert Johnson",
        "DOB: 03/22/1970",
        "SSN: 987-65-4321",
        "Insurance ID: BCBS-123456789",
        "Diagnosis: Type 2 Diabetes",
        "Medications: Metformin 500mg",
        "Allergies: Penicillin",
        "Emergency Contact: (555) 987-6543",
        "Blood Type: O+",
        "Provider: Dr. Sarah Williams"
    ]
    
    for data in medical_data:
        c.drawString(1*inch, y_position, data)
        y_position -= 0.3*inch
    
    # Save the PDF
    c.save()
    print("Created test_sensitive_data.pdf with various types of sensitive information")

if __name__ == "__main__":
    create_test_pdf()
