'use client';

import { useState } from 'react';
import { FileDropzone } from '@/components/upload/FileDropzone';
import { FindingCard } from '@/components/findings/FindingCard';
import { MetricCard } from '@/components/stats/MetricCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { Alert } from '@/components/ui/Alert';
import { 
  DocumentTextIcon, 
  MagnifyingGlassIcon, 
  EnvelopeIcon, 
  IdentificationIcon,
  PhoneIcon 
} from '@heroicons/react/24/outline';
import { useFindings } from '@/hooks/useFindings';
import { useStats } from '@/hooks/useStats';
import type { UploadResponse } from '@/types';

export default function Home() {
  const [recentUpload, setRecentUpload] = useState<UploadResponse | null>(null);
  const { findings, isLoading: findingsLoading, isError: findingsError, mutate } = useFindings();
  const { stats, isLoading: statsLoading } = useStats();

  const handleUploadSuccess = (response: UploadResponse) => {
    setRecentUpload(response);
    mutate(); // Refresh findings
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="space-y-8">
        {/* Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle>Upload PDF Document</CardTitle>
          </CardHeader>
          <CardContent>
            <FileDropzone onUploadSuccess={handleUploadSuccess} />
          </CardContent>
        </Card>

        {/* Recent Upload */}
        {recentUpload && (
          <Alert
            type="success"
            title="Upload Complete"
            message={`${recentUpload.filename} processed successfully. Found ${recentUpload.findings_count} sensitive items across ${recentUpload.page_count} pages.`}
          />
        )}

        {/* Statistics */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {statsLoading ? (
              <>
                <Skeleton className="h-32" />
                <Skeleton className="h-32" />
                <Skeleton className="h-32" />
                <Skeleton className="h-32" />
              </>
            ) : stats ? (
              <>
                <MetricCard
                  title="Total Documents"
                  value={stats.total_documents}
                  icon={DocumentTextIcon}
                />
                <MetricCard
                  title="Total Findings"
                  value={stats.total_findings}
                  icon={MagnifyingGlassIcon}
                />
                <MetricCard
                  title="Emails Found"
                  value={stats.findings_by_type.email}
                  icon={EnvelopeIcon}
                />
                <MetricCard
                  title="SSNs Found"
                  value={stats.findings_by_type.ssn || 0}
                  icon={IdentificationIcon}
                />
                {stats.findings_by_type.phone !== undefined && (
                  <MetricCard
                    title="Phone Numbers Found"
                    value={stats.findings_by_type.phone}
                    icon={PhoneIcon}
                  />
                )}
              </>
            ) : null}
          </div>
        </div>

        {/* Findings */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Findings</h2>
          {findingsError ? (
            <Alert type="error" message="Failed to load findings. Please try again." />
          ) : findingsLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-32" />
              ))}
            </div>
          ) : findings && findings.findings.length > 0 ? (
            <div className="space-y-6">
              {findings.findings.map((document) => (
                <Card key={document.document_id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base">{document.filename}</CardTitle>
                      <span className="text-sm text-gray-500">
                        {document.page_count} pages • {document.findings.length} findings
                      </span>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {document.findings.map((finding) => (
                        <FindingCard key={finding.finding_id} finding={finding} />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="text-center py-12">
                <p className="text-gray-500">No findings yet. Upload a PDF to get started.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
