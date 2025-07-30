'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { CloudArrowUpIcon } from '@heroicons/react/24/outline';
import { Alert } from '@/components/ui/Alert';
import { cn } from '@/lib/utils';
import { MAX_FILE_SIZE, ACCEPTED_FILE_TYPES } from '@/lib/constants';
import { api } from '@/services/api';
import type { UploadResponse } from '@/types';

interface FileDropzoneProps {
  onUploadSuccess?: (response: UploadResponse) => void;
  onUploadError?: (error: string) => void;
}

export function FileDropzone({ onUploadSuccess, onUploadError }: FileDropzoneProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  const handleUpload = useCallback(async (file: File) => {
    setIsUploading(true);
    setUploadStatus({ type: 'info', message: `Uploading ${file.name}...` });

    try {
      const response = await api.uploadPDF(file);
      setUploadStatus({
        type: 'success',
        message: `Successfully processed ${file.name}. Found ${response.findings_count} sensitive items.`,
      });
      onUploadSuccess?.(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Upload failed';
      setUploadStatus({ type: 'error', message });
      onUploadError?.(message);
    } finally {
      setIsUploading(false);
    }
  }, [onUploadSuccess, onUploadError]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      handleUpload(file);
    }
  }, [handleUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    multiple: false,
    disabled: isUploading,
  });

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={cn(
          'relative rounded-lg border-2 border-dashed p-12 text-center transition-colors',
          'hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
          isDragActive && 'border-blue-500 bg-blue-50',
          !isDragActive && 'border-gray-300',
          isUploading && 'cursor-not-allowed opacity-60'
        )}
      >
        <input {...getInputProps()} />
        <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-2 text-sm font-medium text-gray-900">
          {isDragActive ? 'Drop the PDF here' : 'Drag & drop a PDF file here'}
        </p>
        <p className="mt-1 text-xs text-gray-500">or click to select a file</p>
        <p className="mt-2 text-xs text-gray-400">Maximum file size: 50MB</p>
      </div>

      {uploadStatus && (
        <div className="mt-4">
          <Alert
            type={uploadStatus.type}
            message={uploadStatus.message}
          />
        </div>
      )}
    </div>
  );
}
