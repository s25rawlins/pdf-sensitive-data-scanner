import { cn } from '@/lib/utils';
import { 
  CheckCircleIcon, 
  ExclamationTriangleIcon, 
  InformationCircleIcon,
  XCircleIcon 
} from '@heroicons/react/24/outline';

interface AlertProps {
  type: 'success' | 'error' | 'warning' | 'info';
  title?: string;
  message: string;
  className?: string;
}

const alertStyles = {
  success: 'bg-green-50 text-green-800 border-green-200',
  error: 'bg-red-50 text-red-800 border-red-200',
  warning: 'bg-yellow-50 text-yellow-800 border-yellow-200',
  info: 'bg-blue-50 text-blue-800 border-blue-200',
};

const icons = {
  success: CheckCircleIcon,
  error: XCircleIcon,
  warning: ExclamationTriangleIcon,
  info: InformationCircleIcon,
};

export function Alert({ type, title, message, className }: AlertProps) {
  const Icon = icons[type];

  return (
    <div
      className={cn(
        'rounded-lg border p-4 flex items-start space-x-3',
        alertStyles[type],
        className
      )}
      role="alert"
    >
      <Icon className="h-5 w-5 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        {title && <h3 className="font-medium mb-1">{title}</h3>}
        <p className="text-sm">{message}</p>
      </div>
    </div>
  );
}