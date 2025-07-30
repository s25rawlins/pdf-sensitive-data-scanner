import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'PDF Sensitive Data Scanner',
  description: 'Scan PDF files for emails and Social Security Numbers',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-gray-50 flex flex-col">
          <header className="bg-white shadow-sm border-b border-gray-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
              <h1 className="text-2xl font-bold text-gray-900">
                PDF Sensitive Data Scanner
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                Upload PDF files to detect emails and Social Security Numbers
              </p>
            </div>
          </header>
          <main className="flex-1">
            {children}
          </main>
          <footer className="bg-white border-t border-gray-200 py-4">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-sm text-gray-500">
              Powered by FastAPI & ClickHouse
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}