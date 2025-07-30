export interface Finding {
 finding_id: string;
 document_id: string;
 finding_type: 'email' | 'ssn';
 value: string;
 page_number: number;
 confidence: number;
 context: string | null;
 detected_at: string;
}

export interface Document {
 document_id: string;
 filename: string;
 file_size: number;
 page_count: number;
 upload_timestamp: string;
 processing_time_ms: number;
 status: 'success' | 'failed' | 'processing';
 error_message?: string;
}

export interface DocumentWithFindings extends Document {
 findings: Finding[];
 summary: {
   total: number;
   email?: number;
   ssn?: number;
 };
}

export interface FindingsResponse {
 total: number;
 page: number;
 page_size: number;
 findings: DocumentWithFindings[];
}

export interface UploadResponse {
 document_id: string;
 filename: string;
 status: string;
 page_count: number;
 findings_count: number;
 processing_time_ms: number;
 message: string;
}

export interface Statistics {
 total_documents: number;
 total_findings: number;
 findings_by_type: {
   email: number;
   ssn: number;
 };
 average_processing_time_ms: number;
 total_pages_processed: number;
 documents_with_findings: number;
}