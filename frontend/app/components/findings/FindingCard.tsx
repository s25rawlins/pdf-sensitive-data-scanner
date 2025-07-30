import { EnvelopeIcon, IdentificationIcon, PhoneIcon } from '@heroicons/react/24/outline';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';
import type { Finding } from '@/types';

interface FindingCardProps {
  finding: Finding;
}

const typeConfig = {
  email: {
    icon: EnvelopeIcon,
    label: 'Email',
    color: 'text-purple-600',
  },
  ssn: {
    icon: IdentificationIcon,
    label: 'SSN',
    color: 'text-orange-600',
  },
  phone: {
    icon: PhoneIcon,
    label: 'Phone',
    color: 'text-blue-600',
  },
};

export function FindingCard({ finding }: FindingCardProps) {
  const config = typeConfig[finding.finding_type];
  const Icon = config.icon;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start space-x-3">
        <Icon className={cn('h-5 w-5 flex-shrink-0', config.color)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <Badge variant="default">{config.label}</Badge>
            <span className="text-xs text-gray-500">Page {finding.page_number}</span>
          </div>
          <p className="text-sm font-mono text-gray-900 break-all">{finding.value}</p>
          <div className="mt-2 text-xs text-gray-500">
            Confidence: {(finding.confidence * 100).toFixed(0)}%
          </div>
        </div>
      </div>
    </div>
  );
}
