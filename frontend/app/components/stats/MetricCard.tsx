import { Card, CardContent } from '@/components/ui/Card';

interface MetricCardProps {
  title: string;
  value: number | string;
  icon?: React.ComponentType<{ className?: string }>;
  description?: string;
}

export function MetricCard({ title, value, icon: Icon, description }: MetricCardProps) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-600">{title}</p>
            <p className="mt-2 text-3xl font-semibold text-gray-900">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
            {description && (
              <p className="mt-1 text-xs text-gray-500">{description}</p>
            )}
          </div>
          {Icon && <Icon className="h-8 w-8 text-gray-400" />}
        </div>
      </CardContent>
    </Card>
  );
}