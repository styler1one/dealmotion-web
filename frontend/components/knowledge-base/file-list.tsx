'use client'

import { Icons } from '@/components/icons'
import { Button } from '@/components/ui/button'

interface KnowledgeBaseFile {
  id: string
  filename: string
  file_size: number
  file_type: string
  status: 'uploading' | 'processing' | 'completed' | 'failed'
  chunk_count: number
  error_message?: string
  created_at: string
  processed_at?: string
}

interface FileListProps {
  files: KnowledgeBaseFile[]
  onDelete: (fileId: string) => void
  onRefresh: () => void
}

export function FileList({ files, onDelete, onRefresh }: FileListProps) {
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatTimeAgo = (dateString: string): string => {
    const date = new Date(dateString)
    const now = new Date()
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000)

    if (seconds < 60) return 'Just now'
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`
    return `${Math.floor(seconds / 86400)} days ago`
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <Icons.checkCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
      case 'processing':
      case 'uploading':
        return <Icons.spinner className="h-5 w-5 text-blue-600 dark:text-blue-400 animate-spin" />
      case 'failed':
        return <Icons.alertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
      default:
        return null
    }
  }

  const getStatusText = (file: KnowledgeBaseFile): string => {
    switch (file.status) {
      case 'completed':
        return 'Completed'
      case 'processing':
        return 'Processing'
      case 'uploading':
        return 'Uploading'
      case 'failed':
        return file.error_message || 'Failed'
      default:
        return file.status
    }
  }

  const getFileIcon = (fileType: string) => {
    if (fileType.includes('pdf')) return '📄'
    if (fileType.includes('word') || fileType.includes('document')) return '📝'
    if (fileType.includes('text')) return '📃'
    if (fileType.includes('markdown')) return '📋'
    return '📁'
  }

  if (files.length === 0) {
    return (
      <div className="rounded-lg border-2 border-dashed bg-card p-12 text-center">
        <div className="flex flex-col items-center gap-4">
          <div className="rounded-full bg-muted p-4">
            <Icons.fileText className="h-8 w-8 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-lg font-semibold mb-1">No files uploaded yet</h3>
            <p className="text-sm text-muted-foreground">
              Upload your first document to build your knowledge base
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-lg border bg-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">
          Uploaded Files ({files.length})
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
        >
          <Icons.refresh className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      <div className="space-y-3">
        {files.map((file) => (
          <div
            key={file.id}
            className="flex items-center justify-between p-4 rounded-lg border bg-background hover:bg-accent/50 transition-colors"
          >
            <div className="flex items-center gap-4 flex-1 min-w-0">
              <div className="text-2xl flex-shrink-0">
                {getFileIcon(file.file_type)}
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-medium truncate">{file.filename}</p>
                  {getStatusIcon(file.status)}
                </div>
                
                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  <span>{formatFileSize(file.file_size)}</span>
                  {file.status === 'completed' && (
                    <span>• {file.chunk_count} chunks</span>
                  )}
                  <span>• {formatTimeAgo(file.created_at)}</span>
                </div>
                
                {file.status === 'failed' && file.error_message && (
                  <p className="text-sm text-red-600 dark:text-red-400 mt-1">
                    Error: {file.error_message}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <div className="text-right mr-4">
                <p className={`text-sm font-medium ${
                  file.status === 'completed' ? 'text-green-600 dark:text-green-400' :
                  file.status === 'failed' ? 'text-red-600 dark:text-red-400' :
                  'text-blue-600 dark:text-blue-400'
                }`}>
                  {getStatusText(file)}
                </p>
              </div>
              
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete(file.id)}
                disabled={file.status === 'uploading' || file.status === 'processing'}
              >
                <Icons.trash className="h-4 w-4 text-red-600 dark:text-red-400" />
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
